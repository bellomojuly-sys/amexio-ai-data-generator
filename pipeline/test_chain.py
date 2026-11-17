"""The chain (contract v1.1 §3): steps 1–8 in fixed order, offline with the fake
LLM. The output loads with ``load_case``; a step that fails or returns the wrong
shape stops the run, names the step and saves nothing (rule 5)."""

import pytest

from case_model.storage import load_case
from pipeline.chain import STAGES, ChainError, Stage, run_chain
from pipeline.contracts import RunRequest, TraceLine
from pipeline.llm import FakeLLM

STEP_NAMES = ["personas", "cm_id", "plot", "event_content", "dates_participants",
              "document_plan", "document_text", "fill"]


def test_the_chain_has_the_eight_steps_in_contract_order():
    assert [s.name for s in STAGES] == STEP_NAMES


def test_a_fake_run_gives_valid_cases_that_load(run_request, tmp_path):
    result = run_chain(run_request, out_dir=tmp_path)
    assert result.status == "ok" and len(result.cases) == 10
    assert all(len(c.events) > 1 for c in result.cases)           # hire + the plot
    for case in result.cases:
        assert load_case(tmp_path / case.case_number) == case


def test_the_trace_has_a_line_per_code_step_and_per_llm_call(run_request):
    result = run_chain(run_request, run_id="GEN-2026-0042")
    assert all(isinstance(t, TraceLine) and t.run_id == "GEN-2026-0042" for t in result.trace)
    code = [t.stage for t in result.trace if t.kind == "code"]
    assert code == ["cm_id", "plot", "dates_participants", "document_plan", "fill"]
    llm = [t.stage for t in result.trace if t.kind == "llm"]
    assert llm.count("personas") == 1                    # 10 employees, batch 25
    assert llm.count("event_content") == 2               # 10 employees, batch 5
    assert llm.count("document_text") == sum(
        1 for c in result.cases if any(e.type in ("appraisal", "termination", "contract_change")
                                       for e in c.events.values()))


def test_the_reference_seed_keeps_its_facts(request_data, amexio_employees):
    request_data["seedEmployees"] = amexio_employees["employees"][:1]
    result = run_chain(RunRequest.model_validate(request_data))
    jan = result.cases[0]
    assert jan.case_number == "100101"
    assert jan.personas["P001"].name == "Jan de Vries"
    assert str(jan.employments[0].start_date) == "2021-03-01"
    assert jan.employments[0].salary.amount == 4350


def test_a_run_of_seeds_only_makes_no_personas_call(request_data, amexio_employees):
    request_data["config"]["employeeCount"] = 4
    request_data["seedEmployees"] = amexio_employees["employees"]
    result = run_chain(RunRequest.model_validate(request_data))
    assert [c.case_number for c in result.cases] == ["100101", "100102", "100103", "100104"]
    assert not any(t.stage == "personas" for t in result.trace)


def test_a_wrong_shape_stops_the_chain_and_names_the_step(run_request, tmp_path):
    broken = [*STAGES[:2], Stage("plot", "code", lambda s: "not an outline", STAGES[2].output_type)]
    with pytest.raises(ChainError, match="expected PlotOutline, got str") as exc:
        run_chain(run_request, out_dir=tmp_path, stages=broken)
    assert exc.value.stage == "plot"
    assert list(tmp_path.iterdir()) == []                # nothing half-written


def test_two_bad_llm_answers_stop_the_run_naming_the_field(run_request, tmp_path):
    bad = FakeLLM([{"employees": [{"firstName": "A"}]}] * 2)
    with pytest.raises(ChainError) as exc:
        run_chain(run_request, llm=bad, out_dir=tmp_path)
    assert exc.value.stage == "personas" and exc.value.kind == "llm"
    assert exc.value.field == "employees.0.lastName"
    assert list(tmp_path.iterdir()) == []
    body = exc.value.body().model_dump()
    assert body["error"]["stage"] == "personas" and body["error"]["field"] == "employees.0.lastName"
    assert exc.value.trace[-1].ok is False and exc.value.trace[-1].retries == 1


def test_a_run_without_an_llm_needs_fake_llm(request_data):
    request_data["options"]["fake_llm"] = False
    with pytest.raises(ChainError, match="options.fake_llm is false"):
        run_chain(RunRequest.model_validate(request_data))


def test_a_cm_id_refusal_stops_the_chain_with_the_field(run_request):
    wrong = FakeLLM([{"employees": [{"firstName": "A", "lastName": "B", "department": "Sales",
                                     "position": "x"}] * 10}])
    with pytest.raises(ChainError) as exc:
        run_chain(run_request, llm=wrong)
    assert exc.value.stage == "cm_id" and exc.value.kind == "validation"
    assert exc.value.field == "employees.0.department"
