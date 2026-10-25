"""BR-05 — typed events; BR-06 — the rules between events."""

import pytest
from case_model import CaseModel, Money
from case_model.reference_dossier import build_reference_case
from case_model.storage import load_case, save_case


def _jan():
    """Jan de Vries hired on 2021-03-01, with a training provider and a manager."""
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    employer = case.add_organisation(name="Acme Logistics B.V.", kind="employer")
    provider = case.add_organisation(name="Training Academy", kind="training_provider")
    jan = case.add_persona(name="Jan de Vries", role="employee", organisation_id=employer)
    manager = case.add_persona(name="M. Bakker", role="manager", organisation_id=employer)
    case.add_employment(
        persona_id=jan, organisation_id=employer, position="Software Developer",
        department="IT", start_date="2021-03-01", contract_type="Permanent", hours=40,
        salary=Money(amount="4350.00", currency="EUR"),
    )
    case.add_event(type="hire", date="2021-03-01", participant_ids=[jan])
    return case, jan, manager, provider


# BR-05 — one class per type, each with its own facts.

def test_each_type_keeps_its_own_facts():
    case, jan, manager, provider = _jan()
    case.add_event(type="contract_change", date="2022-03-01", participant_ids=[jan],
                   reason="Annual salary review",
                   new_salary=Money(amount="4480.00", currency="EUR"))
    case.add_event(type="training", date="2026-02-20", participant_ids=[jan],
                   course="Secure Coding Fundamentals", duration_days=2, provider_id=provider)
    case.add_event(type="appraisal", date="2026-06-30", participant_ids=[jan, manager],
                   year=2026, rating="Exceeds expectations")
    case.add_event(type="medical_check", date="2026-04-14", participant_ids=[jan],
                   result="Fit for work")
    case.add_event(type="absence", date="2023-11-06", end_date="2023-11-17",
                   participant_ids=[jan])
    built = case.build()
    assert built.events["EVT-002"].new_salary.amount == Money(amount="4480", currency="EUR").amount
    assert built.events["EVT-003"].course == "Secure Coding Fundamentals"
    assert built.events["EVT-004"].rating == "Exceeds expectations"
    assert built.events["EVT-005"].result == "Fit for work"
    assert str(built.events["EVT-006"].end_date) == "2023-11-17"

def test_appraisal_without_rating_is_refused():
    case, jan, manager, _ = _jan()
    with pytest.raises(ValueError, match="rating"):
        case.add_event(type="appraisal", date="2026-06-30", participant_ids=[jan, manager],
                       year=2026)
    assert len(case.events) == 1

def test_rating_outside_the_list_is_refused():
    case, jan, manager, _ = _jan()
    with pytest.raises(ValueError):
        case.add_event(type="appraisal", date="2026-06-30", participant_ids=[jan, manager],
                       year=2026, rating="Great")
    assert len(case.events) == 1

def test_unknown_event_type_is_refused():
    case, jan, _, _ = _jan()
    with pytest.raises(ValueError):
        case.add_event(type="payroll", date="2021-03-25", participant_ids=[jan])
    assert len(case.events) == 1

def test_training_with_unknown_provider_is_refused():
    case, jan, _, _ = _jan()
    with pytest.raises(ValueError, match="ORG-99"):
        case.add_event(type="training", date="2026-02-20", participant_ids=[jan],
                       course="Secure Coding Fundamentals", duration_days=2,
                       provider_id="ORG-99")
    assert len(case.events) == 1

def test_save_and_load_keep_the_type_specific_facts(tmp_path):
    case = build_reference_case()
    save_case(case, tmp_path)
    loaded = load_case(tmp_path)
    assert loaded == case
    training = next(e for e in loaded.events.values() if e.type == "training")
    assert training.course == "Secure Coding Fundamentals"


# BR-06 — the events tell a possible story. Each rule: one deliberate break.

def test_hire_date_must_match_the_employment_start():
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    employer = case.add_organisation(name="Acme Logistics B.V.", kind="employer")
    jan = case.add_persona(name="Jan de Vries", role="employee")
    case.add_employment(
        persona_id=jan, organisation_id=employer, position="Software Developer",
        department="IT", start_date="2021-03-01", contract_type="Permanent", hours=40,
        salary=Money(amount="4350.00", currency="EUR"),
    )
    case.add_event(type="hire", date="2021-04-01", participant_ids=[jan])
    with pytest.raises(ValueError, match="employment starts on 2021-03-01"):
        case.build()

def test_two_hires_are_refused():
    case, jan, _, _ = _jan()
    case.add_event(type="hire", date="2021-03-01", participant_ids=[jan])
    with pytest.raises(ValueError, match="at most one hire"):
        case.build()

def test_nothing_happens_before_the_hire():
    case, jan, _, _ = _jan()
    case.add_event(type="medical_check", date="2020-12-01", participant_ids=[jan],
                   result="Fit for work")
    with pytest.raises(ValueError, match="before the hire"):
        case.build()

def test_nothing_happens_after_the_last_working_day():
    case, jan, _, _ = _jan()
    case.add_event(type="termination", date="2024-08-31", participant_ids=[jan],
                   reason="Resignation")
    case.add_event(type="medical_check", date="2024-10-01", participant_ids=[jan],
                   result="Fit for work")
    with pytest.raises(ValueError, match="after the last working day"):
        case.build()

def test_absence_cannot_run_past_the_last_working_day():
    case, jan, _, _ = _jan()
    case.add_event(type="absence", date="2024-08-26", end_date="2024-09-06",
                   participant_ids=[jan])
    case.add_event(type="termination", date="2024-08-31", participant_ids=[jan],
                   reason="Resignation")
    with pytest.raises(ValueError, match="after the last working day"):
        case.build()

def test_absence_cannot_end_before_it_starts():
    case, jan, _, _ = _jan()
    case.add_event(type="absence", date="2023-11-17", end_date="2023-11-06",
                   participant_ids=[jan])
    with pytest.raises(ValueError, match="before it starts"):
        case.build()
