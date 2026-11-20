"""Contract v1.1 boundary models: each accepts the contract's own example and
refuses each broken rule for the right reason (F1)."""

import pytest
from pydantic import ValidationError

from pipeline.contracts import (
    CaseDocumentPlan,
    DocumentTextsIn,
    EventContentIn,
    PersonasIn,
    PlotOutline,
    RunConfig,
    RunRequest,
    TraceLine,
    check_document_texts,
    check_event_content,
)

OUTLINE = {"outlines": [{"employeeNumber": "100101", "slots": [
    {"slot": "S01", "type": "training", "durationDays": 2},
    {"slot": "S02", "type": "appraisal", "year": 2025, "rating": "Meets expectations"},
    {"slot": "S03", "type": "contract_change", "change": "promotion",
     "newPosition": "Senior Software Developer"},
    {"slot": "S04", "type": "medical_check"},
]}]}

CONTENT = {"content": [{"employeeNumber": "100101", "slots": [
    {"slot": "S01", "summary": "Two-day secure coding course.", "course": "Secure Coding Fundamentals"},
    {"slot": "S02", "summary": "Solid year, steady delivery.",
     "comment": "{{personas.P001.name}} delivered the sprint goals reliably."},
    {"slot": "S03", "summary": "Promoted.", "reason": "Promotion"},
    {"slot": "S04", "summary": "Routine check."},
]}]}

PLAN = {"employeeNumber": "100101", "documents": [
    {"doc": "D01", "type": "performance_appraisal", "eventId": "EVT-004",
     "sections": ["feedback", "summary"]},
    {"doc": "D02", "type": "contract_amendment", "eventId": "EVT-005", "sections": ["cover_letter"]},
]}

TEXTS = {"employeeNumber": "100101", "documents": [
    {"doc": "D01", "sections": {"feedback": "On {{events.EVT-004.date}} ...", "summary": "..."}},
    {"doc": "D02", "sections": {"cover_letter": "..."}},
]}


def _errors(exc):
    return " ".join(str(e) for e in exc.value.errors())


# --- RunRequest / RunConfig ---------------------------------------------------

def test_run_request_accepts_the_contract_example(run_request):
    assert run_request.config.employee_count == 10
    assert run_request.options.fake_llm is True
    assert str(run_request.config.as_of_date) == "2026-10-31"


def test_run_request_refuses_an_id_anywhere(request_data):
    request_data["config"]["departments"][0]["id"] = "DEP-1"
    with pytest.raises(ValidationError, match="IDs are assigned by the case model"):
        RunRequest.model_validate(request_data)


def test_run_config_refuses_an_unknown_field(request_data):
    request_data["config"]["leaverShare"] = 0.1
    with pytest.raises(ValidationError, match="leaverShare"):
        RunConfig.model_validate(request_data["config"])


def test_run_config_refuses_a_share_above_one(request_data):
    request_data["config"]["temporaryShare"] = 1.5
    with pytest.raises(ValidationError) as exc:
        RunConfig.model_validate(request_data["config"])
    assert exc.value.errors()[0]["loc"] == ("temporaryShare",)


def test_run_config_refuses_salary_min_above_max(request_data):
    request_data["config"]["departments"][0]["positions"][0]["salaryMin"] = 9000
    with pytest.raises(ValidationError, match="salaryMin 9000 is above salaryMax"):
        RunConfig.model_validate(request_data["config"])


def test_run_config_refuses_a_non_iso_as_of_date(request_data):
    request_data["config"]["asOfDate"] = "31/10/2026"
    with pytest.raises(ValidationError) as exc:
        RunConfig.model_validate(request_data["config"])
    assert exc.value.errors()[0]["loc"] == ("asOfDate",)


def test_run_request_refuses_more_seeds_than_employees(request_data, amexio_employees):
    request_data["config"]["employeeCount"] = 3
    request_data["seedEmployees"] = amexio_employees["employees"]   # 4 seeds
    with pytest.raises(ValidationError, match="more than employeeCount 3"):
        RunRequest.model_validate(request_data)


# --- PersonasIn (fix 1) -------------------------------------------------------

def test_personas_accept_names_department_and_position():
    p = PersonasIn.model_validate({"employees": [
        {"firstName": "Sanne", "lastName": "Jansen", "department": "IT",
         "position": "Software Developer"}]})
    assert p.employees[0].first_name == "Sanne"


@pytest.mark.parametrize("fact", ["contractType", "hoursPerWeek", "isManager",
                                  "hireDate", "startSalary"])
def test_personas_refuse_a_fact_the_llm_may_not_write(fact):
    employee = {"firstName": "Sanne", "lastName": "Jansen", "department": "IT",
                "position": "Software Developer", fact: "x"}
    with pytest.raises(ValidationError, match=fact):
        PersonasIn.model_validate({"employees": [employee]})


def test_personas_refuse_an_id():
    with pytest.raises(ValidationError, match="IDs are assigned"):
        PersonasIn.model_validate({"employees": [{"id": "P001", "firstName": "A",
                                                  "lastName": "B", "department": "IT",
                                                  "position": "x"}]})


# --- PlotOutline (§5) ---------------------------------------------------------

def test_plot_outline_accepts_the_contract_example():
    outline = PlotOutline.model_validate(OUTLINE)
    assert [s.type for s in outline.outlines[0].slots] == [
        "training", "appraisal", "contract_change", "medical_check"]


def test_plot_outline_refuses_an_unknown_event_type():
    data = {"outlines": [{"employeeNumber": "100101",
                          "slots": [{"slot": "S01", "type": "party"}]}]}
    with pytest.raises(ValidationError, match="party"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_hire_as_a_slot():
    data = {"outlines": [{"employeeNumber": "100101",
                          "slots": [{"slot": "S01", "type": "hire"}]}]}
    with pytest.raises(ValidationError, match="hire"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_an_id():
    data = {"outlines": [{"employeeNumber": "100101",
                          "slots": [{"slot": "S01", "type": "medical_check", "id": "EVT-001"}]}]}
    with pytest.raises(ValidationError, match="IDs are assigned"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_a_date():
    data = {"outlines": [{"employeeNumber": "100101",
                          "slots": [{"slot": "S01", "type": "medical_check", "date": "2025-01-01"}]}]}
    with pytest.raises(ValidationError, match="date"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_a_training_longer_than_five_days():
    data = {"outlines": [{"employeeNumber": "100101",
                          "slots": [{"slot": "S01", "type": "training", "durationDays": 6}]}]}
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(data)
    assert "durationDays" in str(exc.value.errors()[0]["loc"])


def test_plot_outline_refuses_a_rating_outside_the_list():
    data = {"outlines": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "type": "appraisal", "year": 2025, "rating": "Great"}]}]}
    with pytest.raises(ValidationError, match="Meets expectations"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_a_promotion_without_new_position():
    data = {"outlines": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "type": "contract_change", "change": "promotion"}]}]}
    with pytest.raises(ValidationError, match="a promotion needs newPosition"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_an_event_after_the_termination():
    data = {"outlines": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "type": "termination", "reason": "Resignation"},
        {"slot": "S02", "type": "medical_check"}]}]}
    with pytest.raises(ValidationError, match="nothing may come after the termination"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_two_slots_with_the_same_key():
    data = {"outlines": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "type": "medical_check"}, {"slot": "S01", "type": "absence"}]}]}
    with pytest.raises(ValidationError, match="slot 'S01' appears twice"):
        PlotOutline.model_validate(data)


def test_plot_outline_refuses_more_than_ten_slots():
    slots = [{"slot": f"S{i:02d}", "type": "absence"} for i in range(1, 12)]
    with pytest.raises(ValidationError, match="at most 10"):
        PlotOutline.model_validate({"outlines": [{"employeeNumber": "100101", "slots": slots}]})


# H3: one refusal per §5 rule that only the schema snapshot caught, or nothing.

def _one_slot(slot):
    return {"outlines": [{"employeeNumber": "100101", "slots": [{"slot": "S01", **slot}]}]}


def _locs(exc):
    return [".".join(str(p) for p in e["loc"]) for e in exc.value.errors()]


def test_plot_outline_refuses_an_outline_without_slots():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate({"outlines": [{"employeeNumber": "100101", "slots": []}]})
    assert _locs(exc) == ["outlines.0.slots"]
    assert "at least 1" in _errors(exc)


def test_plot_outline_refuses_a_slot_key_not_made_by_code():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate({"outlines": [{"employeeNumber": "100101", "slots": [
            {"slot": "first", "type": "medical_check"}]}]})
    assert _locs(exc) == ["outlines.0.slots.0.medical_check.slot"]


def test_plot_outline_refuses_a_participant():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(_one_slot({"type": "appraisal", "year": 2025,
                                              "rating": "Meets expectations",
                                              "signedBy": "P002"}))
    assert _locs(exc) == ["outlines.0.slots.0.appraisal.signedBy"]


def test_plot_outline_refuses_an_id_under_another_name():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(_one_slot({"type": "medical_check", "eventId": "EVT-001"}))
    assert _locs(exc) == ["outlines.0.slots.0.medical_check.eventId"]


def test_plot_outline_refuses_a_termination_reason_outside_the_list():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(_one_slot({"type": "termination", "reason": "Bored"}))
    assert _locs(exc) == ["outlines.0.slots.0.termination.reason"]


def test_plot_outline_refuses_a_contract_change_kind_outside_the_list():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(_one_slot({"type": "contract_change", "change": "demotion"}))
    assert _locs(exc) == ["outlines.0.slots.0.contract_change.change"]


def test_plot_outline_refuses_a_new_position_without_a_promotion():
    with pytest.raises(ValidationError, match="newPosition only on a promotion"):
        PlotOutline.model_validate(_one_slot({"type": "contract_change", "change": "salary_review",
                                              "newPosition": "IT Manager"}))


def test_plot_outline_refuses_a_training_of_zero_days():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate(_one_slot({"type": "training", "durationDays": 0}))
    assert _locs(exc) == ["outlines.0.slots.0.training.durationDays"]


def test_plot_outline_refuses_two_terminations():
    with pytest.raises(ValidationError, match="more than one termination"):
        PlotOutline.model_validate({"outlines": [{"employeeNumber": "100101", "slots": [
            {"slot": "S01", "type": "termination", "reason": "Resignation"},
            {"slot": "S02", "type": "termination", "reason": "Resignation"}]}]})


def test_plot_outline_refuses_two_outlines_for_one_employee():
    case = OUTLINE["outlines"][0]
    with pytest.raises(ValidationError, match="employeeNumber '100101' appears twice"):
        PlotOutline.model_validate({"outlines": [case, case]})


def test_plot_outline_refuses_an_empty_run():
    with pytest.raises(ValidationError) as exc:
        PlotOutline.model_validate({"outlines": []})
    assert _locs(exc) == ["outlines"]


# --- EventContentIn + check_event_content (§5, fix 3) -------------------------

def test_event_content_accepts_the_contract_example():
    check_event_content(PlotOutline.model_validate(OUTLINE),
                        EventContentIn.model_validate(CONTENT))


def test_event_content_refuses_a_missing_slot():
    content = EventContentIn.model_validate(CONTENT)
    content.content[0].slots.pop()
    with pytest.raises(ValueError, match="slot S04 not answered"):
        check_event_content(PlotOutline.model_validate(OUTLINE), content)


def test_event_content_refuses_an_unknown_slot():
    content = EventContentIn.model_validate(CONTENT)
    content.content[0].slots[3].slot = "S09"
    with pytest.raises(ValueError, match="unknown slot S09"):
        check_event_content(PlotOutline.model_validate(OUTLINE), content)


def test_event_content_refuses_a_training_without_course():
    content = EventContentIn.model_validate(CONTENT)
    content.content[0].slots[0].course = None
    with pytest.raises(ValueError, match="S01: course is missing"):
        check_event_content(PlotOutline.model_validate(OUTLINE), content)


def test_event_content_refuses_text_a_type_does_not_take():
    content = EventContentIn.model_validate(CONTENT)
    content.content[0].slots[3].comment = "The check found nothing."   # medical_check
    with pytest.raises(ValueError, match="S04: comment is not written for a medical_check"):
        check_event_content(PlotOutline.model_validate(OUTLINE), content)


def test_event_content_refuses_a_duration_from_the_llm():
    data = {"content": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "summary": "x", "course": "y", "durationDays": 3}]}]}
    with pytest.raises(ValidationError, match="durationDays"):
        EventContentIn.model_validate(data)


# --- CaseDocumentPlan / DocumentTextsIn (§7, fix 4) ---------------------------

def test_document_plan_accepts_the_contract_example():
    plan = CaseDocumentPlan.model_validate(PLAN)
    assert [d.doc for d in plan.documents] == ["D01", "D02"]


def test_document_plan_refuses_a_templated_document_type():
    data = {"employeeNumber": "100101", "documents": [
        {"doc": "D01", "type": "payslip", "eventId": "EVT-001", "sections": ["body"]}]}
    with pytest.raises(ValidationError, match="payslip is templated"):
        CaseDocumentPlan.model_validate(data)


def test_document_texts_accept_the_planned_sections():
    check_document_texts(CaseDocumentPlan.model_validate(PLAN),
                         DocumentTextsIn.model_validate(TEXTS))


def test_document_texts_refuse_a_section_that_was_not_planned():
    texts = DocumentTextsIn.model_validate(TEXTS)
    texts.documents[1].sections["postscript"] = "..."
    with pytest.raises(ValueError, match="D02: sections .* differ from the plan"):
        check_document_texts(CaseDocumentPlan.model_validate(PLAN), texts)


def test_document_texts_refuse_a_missing_document():
    texts = DocumentTextsIn.model_validate(TEXTS)
    texts.documents.pop()
    with pytest.raises(ValueError, match="doc D02 not written"):
        check_document_texts(CaseDocumentPlan.model_validate(PLAN), texts)


# --- TraceLine (§8) -----------------------------------------------------------

def test_trace_line_accepts_the_contract_example():
    line = TraceLine.model_validate({
        "run_id": "GEN-2026-0001", "stage": "event_content", "kind": "llm", "ok": True,
        "ms": 8421, "model": "m", "input_tokens": 3120, "output_tokens": 2480,
        "retries": 0, "cost_eur": 0.047, "error": None})
    assert line.retries == 0


def test_trace_line_refuses_tokens_on_a_code_step():
    with pytest.raises(ValidationError, match="a code step has no model, token"):
        TraceLine.model_validate({"run_id": "GEN-2026-0001", "stage": "plot", "kind": "code",
                                  "ok": True, "ms": 3, "input_tokens": 10})


def test_trace_line_refuses_a_malformed_run_id():
    with pytest.raises(ValidationError) as exc:
        TraceLine.model_validate({"run_id": "run-1", "stage": "plot", "kind": "code",
                                  "ok": True, "ms": 3})
    assert exc.value.errors()[0]["loc"] == ("run_id",)
