"""The demo's Python side (``demo_bridge.py``), offline: the chain step by step
in fake mode; the Claude-account mode replaying the page's answers until it
needs a new one; errors that name the step and the field; and the bundle the
page loads."""

import hashlib
import json

import pytest

import build_bundle
import demo_bridge
from demo_bridge import key_of, run
from pipeline import fake_answers


def request(employee_count=5, seed_reference=True):
    data = json.loads(demo_bridge.defaults())
    req = data["request"]
    req["config"]["employeeCount"] = employee_count
    req["seedEmployees"] = [data["reference"]] if seed_reference else None
    return json.dumps(req)


def claude_run(req, step, answer=fake_answers.answer):
    """Play the page: run, answer each new prompt (here with the fake), run again."""
    answers, asked = {}, []
    while True:
        out = json.loads(run(req, "claude", step, json.dumps(answers)))
        if out["status"] != "need_answer":
            return out, asked
        asked.append(out["stage"])
        reply = answer(out["prompt"])
        answers[out["key"]] = {"text": reply if isinstance(reply, str) else json.dumps(reply),
                               "model": "claude-sonnet-5-5", "ms": 1200}


# --- fake mode, step by step -----------------------------------------------

def test_each_step_runs_the_chain_up_to_a_step_that_returns_cases():
    req = request()
    personas = json.loads(run(req, "fake", "personas"))
    assert personas["status"] == "ok"
    assert [t["stage"] for t in personas["trace"]] == ["personas", "cm_id"]
    events = json.loads(run(req, "fake", "events"))
    assert [t["stage"] for t in events["trace"] if t["kind"] == "code"] == [
        "cm_id", "plot", "dates_participants"]
    documents = json.loads(run(req, "fake", "documents"))
    assert set(documents["outputs"]) >= {"cm_id", "plot", "event_content", "dates_participants",
                                         "document_plan", "document_text", "fill"}
    assert len(documents["result"]["cases"]) == 5


def test_the_reference_employee_keeps_his_number_and_facts():
    out = json.loads(run(request(), "fake", "personas"))
    jan = out["outputs"]["cm_id"]["employees"][0]
    assert (jan["employeeNumber"], jan["name"], jan["hireDate"], jan["salary"]) == (
        "100101", "Jan de Vries", "2021-03-01", "4350.00")
    assert len(out["outputs"]["personas"]["employees"]) == 4      # only the generated ones


def test_every_llm_call_shows_its_prompt_answer_and_trace_line():
    out = json.loads(run(request(), "fake", "documents"))
    assert {c["stage"] for c in out["calls"]} == {"personas", "event_content", "document_text"}
    for call in out["calls"]:
        attempt = call["attempts"][-1]
        assert attempt["prompt"].startswith(demo_bridge.SYSTEM_START)
        assert attempt["answer"] and attempt["error"] is None
        assert call["trace"]["kind"] == "llm" and call["trace"]["stage"] == call["stage"]


def test_document_texts_show_the_placeholders_and_a_filled_preview():
    texts = json.loads(run(request(), "fake", "documents"))["outputs"]["document_text"]["texts"]
    jan = next(t for t in texts if t["employeeNumber"] == "100101")
    assert "{{personas.P001.name}}" in jan["text"] and "Jan de Vries" in jan["filled"]
    assert "{{" not in jan["filled"] and jan["problems"] == []


# --- the viewer's Claude account, replayed -----------------------------------

def test_claude_mode_asks_for_each_new_prompt_and_ends_like_fake_mode():
    req = request()
    out, asked = claude_run(req, "documents")
    assert out["status"] == "ok"
    assert asked == ["personas", "event_content", "document_text", "document_text",
                     "document_text", "document_text", "document_text"]
    fake = json.loads(run(req, "fake", "documents"))
    assert out["result"]["cases"] == fake["result"]["cases"]


def test_while_asking_the_calls_so_far_keep_their_stage():
    req = request()
    answers = {}
    for _ in range(3):                              # personas, event content, then ask again
        out = json.loads(run(req, "claude", "documents", json.dumps(answers)))
        answers[out["key"]] = {"text": json.dumps(fake_answers.answer(out["prompt"]))}
    assert out["status"] == "need_answer" and out["stage"] == "document_text"
    assert [c["stage"] for c in out["calls"]] == ["personas", "event_content"]


def test_claude_mode_estimates_tokens_and_keeps_the_page_time():
    out, _ = claude_run(request(), "personas")
    call = out["calls"][0]
    assert call["inputTokens"] == round(len(call["attempts"][0]["prompt"]) / 4)
    assert call["attempts"][0]["ms"] == 1200


def test_a_bad_answer_gets_the_retry_through_the_page():
    def answer(prompt):
        reply = fake_answers.answer(prompt)
        if "previous answer was not valid" not in prompt and '"task": "personas"' in prompt:
            reply["employees"] = reply["employees"][:1]          # too few: retried
        return reply
    out, asked = claude_run(request(), "personas", answer)
    assert out["status"] == "ok" and asked == ["personas", "personas"]
    call = out["calls"][0]
    assert call["retries"] == 1 and "asked for 4, got 1" in call["attempts"][0]["error"]


def test_an_error_from_the_page_stops_the_run_with_its_kind():
    req = request()
    first = json.loads(run(req, "claude", "personas"))
    answers = {first["key"]: {"error": {"kind": "setup", "message": "Claude is not allowed here."}}}
    out = json.loads(run(req, "claude", "personas", json.dumps(answers)))
    assert out["status"] == "error" and out["error"]["stage"] == "personas"
    assert "Claude is not allowed here." in out["error"]["message"]
    assert out["calls"][0]["ok"] is False


def test_a_bad_request_is_refused_with_the_field():
    data = json.loads(request())
    data["config"]["id"] = "X"
    out = json.loads(run(json.dumps(data), "fake", "personas"))
    assert out["status"] == "error" and out["error"]["kind"] == "validation"


# --- the bundle the page loads ------------------------------------------------

def test_the_bundle_holds_every_module_the_demo_imports():
    files = build_bundle.bundle_files()
    for path in ("pipeline/chain.py", "pipeline/generation.py", "pipeline/placeholders.py",
                 "case_model/lookup.py", "generator/Second_demo_generator/demo_bridge.py",
                 "pipeline/fixtures/run_request.json"):
        assert path in files
    assert not any(p.startswith("pdf_template_studio") for p in files)


def test_pyodide_is_copied_with_pydantic_and_its_dependencies_only(tmp_path):
    source = tmp_path / "release"
    source.mkdir()
    wheels = {"pydantic": ["typing-extensions", "pydantic_core"], "pydantic-core": ["typing-extensions"],
              "typing-extensions": [], "numpy": []}
    lock = {"info": {"version": "0.29.3"}, "packages": {}}
    for name, depends in wheels.items():
        file_name = f"{name.replace('-', '_')}-1.0-py3-none-any.whl"
        data = f"wheel of {name}".encode()
        (source / file_name).write_bytes(data)
        lock["packages"][name] = {"name": name.replace("pydantic-core", "pydantic_core"),
                                  "file_name": file_name, "depends": depends,
                                  "sha256": hashlib.sha256(data).hexdigest()}
    (source / "pyodide-lock.json").write_text(json.dumps(lock))
    for name in build_bundle.PYODIDE_CORE:
        (source / name).write_bytes(b"core")
    out = tmp_path / "site"
    written = build_bundle.fetch_pyodide(str(source), out)
    assert "python_stdlib.zip.wasm" in written                # the host serves no .zip
    assert (out / "pydantic_core-1.0-py3-none-any.whl.wasm").exists()
    assert not any("numpy" in name for name in written)
    assert set(json.loads((out / "pyodide-lock.json").read_text())["packages"]) == {
        "pydantic", "pydantic-core", "typing-extensions"}


def test_a_wheel_that_does_not_match_its_sha256_is_refused(tmp_path):
    (tmp_path / "pydantic-1.0-py3-none-any.whl").write_bytes(b"changed")
    (tmp_path / "pyodide-lock.json").write_text(json.dumps({"info": {}, "packages": {"pydantic": {
        "name": "pydantic", "file_name": "pydantic-1.0-py3-none-any.whl", "depends": [],
        "sha256": hashlib.sha256(b"original").hexdigest()}}}))
    for name in build_bundle.PYODIDE_CORE:
        (tmp_path / name).write_bytes(b"core")
    with pytest.raises(SystemExit, match="sha256"):
        build_bundle.fetch_pyodide(str(tmp_path), tmp_path / "out")
