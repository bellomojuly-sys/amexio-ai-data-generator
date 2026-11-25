"""The demo's Python side: the backend's own chain, step by step, for the page.

The page (``site/index.html``) runs this module in the browser with Pyodide,
next to the repo's ``pipeline/`` and ``case_model/`` packages, so the demo runs
the same code as the backend. It calls::

    run(request_json, mode, step, answers_json, seed) -> JSON string

for each step of v1's flow. ``step`` says how far the chain runs; it always
stops after a step that returns cases, the only place ``run_chain`` can stop:

| Demo step | Chain steps (contract v1.1 §3) |
|---|---|
| ``personas`` | 1 personas, 2 cm_id |
| ``events`` | ... 3 plot, 4 event_content, 5 dates_participants |
| ``documents`` | ... 6 document_plan, 7 document_text, 8 fill |

**Modes.** ``fake`` answers every LLM call with ``pipeline.fake_answers`` (the
contract's ``options.fake_llm``). ``claude`` answers it with the viewer's
Claude account, through the page. The LLM client's ``complete()`` cannot wait
for the page's asynchronous call, so ``ReplayLLM`` answers from the answers
the page has collected; a prompt with no answer yet stops the run with
``need_answer``. The page asks Claude and runs again. With the same request,
seed and answers the chain sends the same prompts, so each run replays up to
the first new prompt. Nothing in ``pipeline/`` changes for this.

Every run starts from the request again, so nothing is half-written: a run
that fails returns what each step produced so far and the error, and saves
nothing (rule 5).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from case_model.fill import UnresolvedPlaceholders, fill_text
from case_model.storage import save_case
from pipeline import fake_answers
from pipeline.chain import STAGES, ChainError, Stage, run_chain
from pipeline.contracts import RunRequest
from pipeline.llm import BaseLLMClient, Completion, FakeLLM, ProviderError
from pipeline.placeholders import text_problems

RUN_ID = "GEN-2026-0001"
PACKAGE = "hr-dossier-import"   # v1's import package folder (its DEFAULT_TARGET.packageName; v1 is frozen)
MODEL = "claude-sonnet-5-5"      # Model Selection document; the page asks for it by name
STEPS = {"personas": "cm_id", "events": "dates_participants", "documents": "fill"}
CHARS_PER_TOKEN = 4              # the Claude-account route reports no tokens: an estimate

# Whose each chain step is (contract §11b), and which are stand-ins today.
OWNERS = {"personas": "Robin", "cm_id": "Giulia", "plot": "Giulia",
          "event_content": "Robin", "dates_participants": "Valentin",
          "document_plan": "Giulia", "document_text": "Robin", "fill": "Valentin"}
STUBS = {"dates_participants", "fill"}
SYSTEM_START = "You generate synthetic test data"   # how every generation prompt begins

# The repo's root: the page lays the files out the same way in the browser.
ROOT = Path(__file__).resolve().parent.parent.parent
REQUEST_FIXTURE = ROOT / "pipeline" / "fixtures" / "run_request.json"
AMEXIO_FIXTURE = ROOT / "case_model" / "fixtures" / "generator" / "amexio_example" / "employees.json"


# --- The viewer's Claude account, replayed ------------------------------------

def key_of(prompt: str) -> str:
    """The key the page files an answer under."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / CHARS_PER_TOKEN)) if text else 0


class NeedAnswer(BaseException):
    """No answer for this prompt yet: the page asks Claude, then runs again.
    A ``BaseException``, so neither ``complete_as`` nor ``run_chain`` treats it
    as a failed call: the run simply stops here."""

    def __init__(self, key: str, prompt: str):
        super().__init__(key)
        self.key = key
        self.prompt = prompt


class ReplayLLM(BaseLLMClient):
    """An LLM client whose answers come from the page (the viewer's Claude
    account). ``answers`` maps ``key_of(prompt)`` to ``{"text", "model"}``, or
    to ``{"error": {"kind", "message"}}`` when the page's call failed. Tokens
    are estimated from the characters: the page's call reports none."""

    def __init__(self, answers: dict, model: str = MODEL):
        super().__init__()
        self.answers = answers
        self.model = model

    def complete(self, prompt: str) -> Completion:
        key = key_of(prompt)
        entry = self.answers.get(key)
        if entry is None:
            raise NeedAnswer(key, prompt)
        if "error" in entry:
            raise ProviderError(entry["error"]["message"], entry["error"]["kind"])
        return Completion(text=entry["text"], model=entry.get("model") or self.model,
                          input_tokens=estimate_tokens(prompt),
                          output_tokens=estimate_tokens(entry["text"]))


# --- One run --------------------------------------------------------------------

def defaults() -> str:
    """The starting request (contract §3 fixture) and AMEXIO's reference employee."""
    request = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
    amexio = json.loads(AMEXIO_FIXTURE.read_text(encoding="utf-8"))
    return json.dumps({"request": request, "reference": amexio["employees"][0]})


def run(request_json: str, mode: str, step: str, answers_json: str = "{}", seed: int = 0) -> str:
    """Run the chain up to ``step`` and say what happened, as JSON."""
    o = _execute(request_json, mode, step, answers_json, seed)
    if o["status"] == "invalid":
        return _dumps({"status": "error", "outputs": {}, "calls": [], "trace": [],
                       "error": {"kind": "validation", "stage": "request",
                                 "message": o["message"], "field": None}})
    calls = _calls(o["llm"], o["trace"], o["answers"], o["marks"])
    if o["status"] == "need_answer":
        return _dumps({"status": "need_answer", "key": o["need"].key, "prompt": o["need"].prompt,
                       "stage": o["stage"], "outputs": _views(o["outputs"]), "calls": calls,
                       "trace": []})
    trace = [t.model_dump() for t in o["trace"]]
    if o["status"] == "error":
        return _dumps({"status": "error", "error": o["error"].body().error.model_dump(),
                       "outputs": _views(o["outputs"]), "calls": calls, "trace": trace})
    return _dumps({"status": "ok", "outputs": _views(o["outputs"]), "calls": calls,
                   "trace": trace, "result": o["result"].model_dump(mode="json")})


def _execute(request_json: str, mode: str, step: str, answers_json: str, seed: int) -> dict:
    """One run of the chain up to ``step``, with every Python object kept."""
    try:
        request = RunRequest.model_validate_json(request_json)
    except ValueError as exc:
        return {"status": "invalid", "message": str(exc)}
    answers = json.loads(answers_json or "{}")
    llm = FakeLLM(fake_answers.answer) if mode == "fake" else ReplayLLM(answers)
    o = {"request": request, "answers": answers, "llm": llm, "outputs": {}, "trace": [],
         "marks": [], "stage": None, "result": None, "error": None, "need": None}
    current = {"stage": None}
    stages = []
    for stage in STAGES:          # marks: (stage, number of LLM calls before it)
        stages.append(Stage(stage.name, stage.kind,
                            _capture(stage, o["outputs"], current, o["marks"], llm),
                            stage.output_type))
        if stage.name == STEPS[step]:
            break
    try:
        o["result"] = run_chain(request, llm=llm, stages=stages, run_id=RUN_ID, seed=seed)
        o["status"], o["trace"] = "ok", o["result"].trace
    except NeedAnswer as need:
        o["status"], o["need"] = "need_answer", need
    except ChainError as error:
        o["status"], o["error"], o["trace"] = "error", error, error.trace
    o["stage"] = current["stage"]
    return o


# --- Export: the files of a run, as one ZIP -------------------------------------

def export_files(request_json: str, mode: str, step: str, answers_json: str = "{}",
                 seed: int = 0, model: str = MODEL) -> str:
    """The files of a run up to ``step``, as JSON ``{path: text}`` with paths
    inside the run's folder. Runs the chain again with the same answers, so it
    sends nothing new to Claude.

    One folder per case in the case model's own format (``save_case``), plus
    the run request, the corrections, the trace, every LLM call with its
    prompts and answers, the steps' outputs and the document texts with their
    filled preview. The page adds AMEXIO's import package (PDFs and
    ``import.xml``), made from ``cases/`` by v1's export (``v1_export/``)."""
    return json.dumps(_export_files(request_json, mode, step, answers_json, seed, model),
                      ensure_ascii=False)


def export_zip(request_json: str, mode: str, step: str, answers_json: str = "{}",
               seed: int = 0, model: str = MODEL) -> bytes:
    """``export_files`` as a ZIP, under the run's folder, without the import
    package (which the page makes in JavaScript)."""
    files = _export_files(request_json, mode, step, answers_json, seed, model)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, text in sorted(files.items()):
            archive.writestr(f"{RUN_ID}/{path}", text)
    return buffer.getvalue()


def _export_files(request_json: str, mode: str, step: str, answers_json: str,
                  seed: int, model: str) -> dict[str, str]:
    o = _execute(request_json, mode, step, answers_json, seed)
    if o["status"] != "ok":
        reason = o.get("message") or (str(o["error"]) if o["error"] else "a prompt has no answer yet")
        raise ValueError(f"nothing to export: the run did not finish ({reason})")
    result = o["result"]
    files: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for case in result.cases:
            folder = Path(tmp) / case.case_number
            save_case(filled_case(case), folder)
            for path in sorted(folder.iterdir()):
                files[f"cases/{case.case_number}/{path.name}"] = path.read_text(encoding="utf-8")

    def as_json(value) -> str:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n"

    files["run_request.json"] = as_json(json.loads(request_json))
    files["corrections.json"] = as_json([c.model_dump() for c in result.corrections])
    files["trace.json"] = as_json([t.model_dump() for t in result.trace])
    files["llm_calls.json"] = as_json(_calls(o["llm"], result.trace, o["answers"], o["marks"]))
    names = {"personas": "personas_in", "plot": "plot_outline", "event_content": "event_content_in",
             "document_plan": "document_plan"}
    for stage, name in names.items():
        if o["outputs"].get(stage) is not None:
            files[f"steps/{name}.json"] = as_json(_dump(o["outputs"][stage]))
    if "document_text" in o["outputs"]:
        files["document_texts.json"] = as_json(_texts(o["outputs"]))
    files["README.txt"] = _readme(result, mode, model, step, seed, sorted(files))
    return files


EVENT_TEXTS = ("summary", "label", "comment", "reason")


def filled_case(case):
    """**Demo stand-in for Fill (Valentin), on the events.** Part 2's texts
    (summary, comment, reason) are saved on the events with their placeholders,
    and no step fills them yet (open point 1). The exported case folders get
    them filled with the case model's ``fill_text``, so a reader such as the v1
    demo gets plain text; a placeholder Fill refuses stops the export. The
    chain's own texts stay in ``steps/event_content_in.json``."""
    data = case.model_dump(mode="json")
    for event in data["events"].values():
        for name in EVENT_TEXTS:
            if isinstance(event.get(name), str):
                event[name] = fill_text(case, event[name])
    return type(case).model_validate(data)


def _readme(result, mode: str, model: str, step: str, seed: int, paths: list[str]) -> str:
    made_by = f"Claude ({model}) on the viewer's Claude account" if mode == "claude" else \
        "the fake model (pipeline/fake_answers.py, options.fake_llm)"
    reached = {"personas": "1-2 (Personas, CM ID)", "events": "1-5 (up to Dates & participants)",
               "documents": "1-8 (all)"}[step]
    lines = [
        f"{RUN_ID}: a run of the AMEXIO dossier generator v2 (pipeline contract v1.1)",
        "",
        f"Exported: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"LLM: {made_by}",
        f"Chain steps run: {reached}; seed {seed}; {len(result.cases)} cases",
        "",
        "cases/NNNNNN/        one folder per case, as case_model.storage.save_case writes it",
        "                     (case.json, cast.json, storyline.json, documents.json), with the",
        "                     placeholders in the events' texts filled (demo stand-in for Fill).",
        f"{PACKAGE}/   AMEXIO's import package made from these cases: import.xml and one",
        "                     PDF per document in files/. Demo stand-in for Export (step 9,",
        "                     Stylianos): the page runs v1's export, unchanged, on cases/, as",
        "                     v1's Configure step does with Open case ZIP. Only for a run",
        "                     through all steps, and only when v1's checks find no error.",
        "package_check.json   whether the package was made, v1's checks (errors and warnings)",
        "                     and the documents per type",
        "run_request.json     the request the chain ran (POST /runs, contract section 3)",
        "corrections.json     values the case model corrected on the way in",
        "trace.json           one line per code step and per LLM call (contract section 8)",
        "llm_calls.json       every LLM call: each attempt's prompt, answer and refusal",
        "steps/               each step's output at its boundary (the contract's JSON shapes)",
        "document_texts.json  the document texts with their placeholders, and a filled preview",
        "",
        "Stand-ins: Dates & participants and Fill are Valentin's stubs. The filled texts (the",
        "events' texts in cases/, the filled preview) come from the case model's fill_text,",
        "which Fill will call, in AMEXIO's formats (01-03-2021, EUR 4.350). In Claude mode the",
        "tokens in trace.json are estimates (characters / 4): the page's Claude call reports none.",
        "",
        "The PDFs are v1's. The chain's cases hold no documents yet (Fill is a stub), so v1",
        "plans each dossier from the cases' events, as it always has: three years up to the",
        "as-of date. They print the cases' facts and Part 2's texts (an appraisal's comment, a",
        "change's reason); Part 3's sections are not printed yet: they are in",
        "document_texts.json.",
        "",
        "Files of the run (the package lists its own in its README.md):",
        *[f"  {p}" for p in paths + ["README.txt"]],
    ]
    return "\n".join(lines) + "\n"


def _capture(stage: Stage, outputs: dict, current: dict, marks: list, llm: BaseLLMClient):
    def func(state):
        current["stage"] = stage.name
        marks.append((stage.name, len(llm.calls)))
        value = stage.func(state)
        outputs[stage.name] = value
        return value
    return func


def _calls(llm: BaseLLMClient, trace, answers: dict, marks: list) -> list[dict]:
    """Every LLM call with its attempts (prompt, answer, what code refused) and
    its trace line. The chain writes one llm trace line per call, in order; a
    run that stopped for a new prompt has no trace yet, so the stage of each
    call comes from where the steps began."""
    lines = [t for t in (trace or []) if t.kind == "llm"]
    calls = []
    for i, call in enumerate(llm.calls):
        line = lines[i] if i < len(lines) else None
        stage = next((name for name, start in reversed(marks) if start <= i), None)
        calls.append({
            "stage": stage,
            "ok": call.ok, "model": call.model, "ms": call.ms, "retries": call.retries,
            "inputTokens": call.input_tokens, "outputTokens": call.output_tokens,
            "error": call.error,
            "attempts": [{"prompt": a.prompt, "answer": a.answer, "error": a.error,
                          "ms": (answers.get(key_of(a.prompt)) or {}).get("ms")}
                         for a in call.attempts],
            "trace": line.model_dump() if line else None,
        })
    return calls


# --- What the page shows per step --------------------------------------------

def _dump(model) -> object:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True) if model else None


def _employees(cm) -> list[dict]:
    rows = []
    for case in cm.cases:
        job = case.employments[0]
        employee = case.personas[job.persona_id]
        manager = next((p for p in case.personas.values() if p.role == "manager"), None)
        rows.append({"employeeNumber": case.case_number, "name": employee.name,
                     "department": job.department, "position": job.position,
                     "hireDate": str(job.start_date), "contract": job.contract_type,
                     "hours": job.hours, "salary": f"{job.salary.amount}",
                     "manager": manager.name if manager else None,
                     "personaId": employee.id})
    return rows


def _events(cm) -> list[dict]:
    rows = []
    for case in cm.cases:
        for event in case.events.values():
            details = event.model_dump(mode="json", exclude_none=True,
                                       exclude={"id", "date", "type", "participant_ids"})
            rows.append({"employeeNumber": case.case_number, "eventId": event.id,
                         "type": event.type, "date": str(event.date),
                         "participants": [case.personas[p].name for p in event.participant_ids],
                         "details": details})
    return rows


def fill_preview(case, text: str) -> str:
    """**Demo stand-in for Fill (Valentin)**, whose step is still a stub: the
    text as the case model's ``fill_text`` fills it (AX-024), the function Fill
    will call, in AMEXIO's formats (AX-025: dates "01-03-2021", amounts
    "EUR 4.350"). Where Fill would stop, the preview says why instead."""
    try:
        return fill_text(case, text)
    except UnresolvedPlaceholders as exc:
        return "Fill would stop here: " + "; ".join(f"{{{{{p}}}}}: {why}"
                                                    for p, why in exc.problems.items())


def _texts(outputs: dict) -> list[dict]:
    texts = outputs.get("document_text")
    dated = outputs.get("dates_participants")
    plan = outputs.get("document_plan")
    if texts is None or dated is None or plan is None:
        return []
    cases = {c.case_number: c for c in dated.cases}
    planned = {(p.employee_number, d.doc): d for p in plan.plans for d in p.documents}
    rows = []
    for case_texts in texts.texts:
        case = cases[case_texts.employee_number]
        for document in case_texts.documents:
            planned_doc = planned.get((case_texts.employee_number, document.doc))
            for section, text in document.sections.items():
                rows.append({"employeeNumber": case_texts.employee_number, "doc": document.doc,
                             "type": planned_doc.type if planned_doc else None,
                             "eventId": planned_doc.event_id if planned_doc else None,
                             "section": section, "text": text,
                             "filled": fill_preview(case, text),
                             "problems": text_problems(text, case)})
    return rows


def _views(outputs: dict) -> dict:
    views: dict = {}
    if "personas" in outputs:
        views["personas"] = _dump(outputs["personas"])
    if "cm_id" in outputs:
        cm = outputs["cm_id"]
        views["cm_id"] = {"employees": _employees(cm),
                          "corrections": [c.model_dump() for c in cm.corrections]}
    for name in ("plot", "event_content", "document_plan"):
        if name in outputs:
            views[name] = _dump(outputs[name])
    if "dates_participants" in outputs:
        cm = outputs["dates_participants"]
        views["dates_participants"] = {"events": _events(cm),
                                       "corrections": [c.model_dump() for c in cm.corrections]}
    if "document_text" in outputs:
        views["document_text"] = {"texts": _texts(outputs)}
    if "fill" in outputs:
        views["fill"] = {"cases": len(outputs["fill"].cases)}
    return views


def _dumps(value) -> str:
    def default(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, (dt.date, Decimal)):
            return str(obj)
        raise TypeError(f"cannot write {type(obj).__name__} as JSON")
    return json.dumps(value, default=default, ensure_ascii=False)
