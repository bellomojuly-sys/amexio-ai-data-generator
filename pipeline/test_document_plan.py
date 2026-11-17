"""Step 6 · Document plan (contract v1.1 §7): one planned document per event
that gets LLM text, with code keys D01, D02, …"""

from case_model.ingest import ingest_employees, ingest_storylines
from pipeline.contracts import CmIdOutput
from pipeline.document_plan import document_plan, plan_case


def _jan(amexio_employees):
    cases, _ = ingest_employees(amexio_employees)
    cases, _ = ingest_storylines(cases[:1], {"storylines": [{"employeeId": "100101", "events": [
        {"type": "training", "date": "2022-05-10", "course": "Secure Coding", "durationDays": 2},
        {"type": "contract_change", "date": "2023-01-01", "reason": "Annual salary review",
         "newSalary": 4500},
        {"type": "medical_check", "date": "2023-03-01", "result": "Fit for work"},
    ], "appraisals": [{"year": 2022, "rating": "Meets expectations"}]}]})
    return cases[0]


def test_only_llm_text_documents_are_planned(amexio_employees):
    plan = plan_case(_jan(amexio_employees))
    assert [(d.doc, d.type) for d in plan.documents] == [
        ("D01", "performance_appraisal"), ("D02", "contract_amendment")]


def test_each_document_points_to_its_event(amexio_employees):
    case = _jan(amexio_employees)
    for d in plan_case(case).documents:
        assert d.event_id in case.events
        assert {"performance_appraisal": "appraisal",
                "contract_amendment": "contract_change"}[d.type] == case.events[d.event_id].type


def test_a_case_with_only_a_hire_has_an_empty_plan(amexio_employees):
    cases, _ = ingest_employees(amexio_employees)
    plan = document_plan(CmIdOutput(cases=cases))
    assert [p.documents for p in plan.plans] == [[], [], [], []]
