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
import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from case_model.lookup import UnknownPath, get_fact
from pipeline import fake_answers
from pipeline.chain import STAGES, ChainError, Stage, run_chain
from pipeline.contracts import RunRequest
from pipeline.llm import BaseLLMClient, Completion, FakeLLM, ProviderError
from pipeline.placeholders import PLACEHOLDER, text_problems

RUN_ID = "GEN-2026-0001"
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
    try:
        request = RunRequest.model_validate_json(request_json)
    except ValueError as exc:
        return _dumps({"status": "error", "outputs": {}, "calls": [], "trace": [],
                       "error": {"kind": "validation", "stage": "request",
                                 "message": str(exc), "field": None}})
    answers = json.loads(answers_json or "{}")
    llm = FakeLLM(fake_answers.answer) if mode == "fake" else ReplayLLM(answers)
    outputs: dict = {}
    current = {"stage": None}
    marks: list[tuple[str, int]] = []        # (stage, number of LLM calls before it)
    stages = []
    for stage in STAGES:
        stages.append(Stage(stage.name, stage.kind, _capture(stage, outputs, current, marks, llm),
                            stage.output_type))
        if stage.name == STEPS[step]:
            break
    try:
        result = run_chain(request, llm=llm, stages=stages, run_id=RUN_ID, seed=seed)
    except NeedAnswer as need:
        return _dumps({"status": "need_answer", "key": need.key, "prompt": need.prompt,
                       "stage": current["stage"], "outputs": _views(outputs),
                       "calls": _calls(llm, None, answers, marks), "trace": []})
    except ChainError as error:
        return _dumps({"status": "error", "error": error.body().error.model_dump(),
                       "outputs": _views(outputs), "calls": _calls(llm, error.trace, answers, marks),
                       "trace": [t.model_dump() for t in error.trace]})
    return _dumps({"status": "ok", "outputs": _views(outputs),
                   "calls": _calls(llm, result.trace, answers, marks),
                   "trace": [t.model_dump() for t in result.trace],
                   "result": result.model_dump(mode="json")})


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
    """**Demo stand-in for Fill (Valentin).** Each placeholder replaced by its
    fact, read with ``get_fact``; dates as "1 March 2021", amounts as
    "4,350.00". The real Fill and its formats (AX-025) are not built yet."""
    def fact(match):
        try:
            value = get_fact(case, match.group(1))
        except UnknownPath:
            return match.group(0)
        if isinstance(value, dt.date):
            return f"{value.day} {value.strftime('%B')} {value.year}"
        if isinstance(value, Decimal):
            return f"{value:,.2f}"
        return str(value)
    return PLACEHOLDER.sub(fact, text)


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
