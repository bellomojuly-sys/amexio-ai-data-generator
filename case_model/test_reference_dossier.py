"""AX-016, AX-017 — the HR reference dossier 100101 loads and is coherent (v1.1: AMEXIO's 100101, built through ingest).
AX-019 — and its exported form is frozen, so a deliberate break fails."""

import json

from case_model.reference_dossier import GOLDEN_PATH, build_reference_case


def test_reference_dossier_loads_without_error():
    # AX-016 — it validates in one call.
    case = build_reference_case()
    assert case.case_number == "100101"
    assert case.dossier.employee_number == "100101"

def test_every_event_participant_exists():
    # AX-016 — every participant ID is a persona the case holds.
    case = build_reference_case()
    for event in case.events.values():
        for pid in event.participant_ids:
            assert pid in case.personas

def test_it_is_amexio_employee_100101():
    # D1 — the reference is AMEXIO's own employee, not a hand-written story.
    case = build_reference_case()
    employee = next(p for p in case.personas.values() if p.role == "employee")
    job = case.employments[0]
    assert employee.name == "Jan de Vries"
    assert (job.department, job.position) == ("IT", "Software Developer")
    assert str(job.salary.amount) == "4350.00"

def test_events_behind_amexios_documents():
    # Contract <- hire, training certificate <- training, medical check <-
    # medical_check, appraisal <- appraisal. The payslip recurs: no event (D3a).
    case = build_reference_case()
    assert sorted(e.type for e in case.events.values()) == [
        "appraisal", "hire", "medical_check", "training",
    ]

def test_reference_dossier_matches_golden():
    # AX-019 — the fixture is the regression anchor. Its full exported form is
    # frozen in reference_dossier.golden.json, so changing any fact above (a
    # name, a date, an amount, a participant) makes this fail on purpose.
    # Regenerate the snapshot only when the change is intended:
    #     python3 -m case_model.reference_dossier
    exported = build_reference_case().model_dump(mode="json")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert exported == golden
