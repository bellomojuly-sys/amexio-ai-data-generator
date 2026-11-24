"""H4 — case model v1.2: who signs an event (BR-16 Q1, pipeline contract v1.1 §6)."""

import json

import pytest
from pydantic import ValidationError
from case_model import Case, CaseModel, Money
from case_model.ingest import ingest_employees, ingest_storylines
from case_model.storage import load_case, save_case


def _jan():
    """Jan de Vries (P001) hired on 2021-03-01, with his manager M. Bakker (P002)."""
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    employer = case.add_organisation(name="Acme Logistics B.V.", kind="employer")
    jan = case.add_persona(name="Jan de Vries", role="employee", organisation_id=employer)
    manager = case.add_persona(name="M. Bakker", role="manager", organisation_id=employer)
    case.add_employment(
        persona_id=jan, organisation_id=employer, position="Software Developer",
        department="IT", start_date="2021-03-01", contract_type="Permanent", hours=40,
        salary=Money(amount="4350.00", currency="EUR"),
    )
    case.add_event(type="hire", date="2021-03-01", participant_ids=[jan])
    return case, jan, manager


def test_an_appraisal_signed_by_the_manager_is_kept():
    case, jan, manager = _jan()
    case.add_event(type="appraisal", date="2025-06-30", participant_ids=[jan, manager],
                   year=2025, rating="Meets expectations", signed_by=manager)
    assert case.build().events["EVT-002"].signed_by == "P002"


def test_adding_an_event_signed_by_an_unknown_persona_fails():
    case, jan, manager = _jan()
    with pytest.raises(ValueError, match=r"Unknown persona: P009 \(field signed_by\)"):
        case.add_event(type="appraisal", date="2025-06-30", participant_ids=[jan],
                       year=2025, rating="Meets expectations", signed_by="P009")
    assert "EVT-002" not in case.events


def test_a_case_read_from_json_with_an_unknown_signer_fails(tmp_path):
    case, jan, manager = _jan()
    case.add_event(type="appraisal", date="2025-06-30", participant_ids=[jan, manager],
                   year=2025, rating="Meets expectations", signed_by=manager)
    data = case.build().model_dump(mode="json")
    data["events"]["EVT-002"]["signed_by"] = "P009"
    with pytest.raises(ValidationError, match="EVT-002 is signed by unknown persona 'P009'"):
        Case.model_validate(data)


def test_a_case_without_signer_is_saved_as_in_v11(tmp_path):
    case, jan, manager = _jan()
    built = case.build()
    save_case(built, tmp_path)
    events = json.loads((tmp_path / "storyline.json").read_text(encoding="utf-8"))["events"]
    assert "signed_by" not in events["EVT-001"]
    assert load_case(tmp_path) == built


def test_a_signer_survives_save_and_load(tmp_path):
    case, jan, manager = _jan()
    case.add_event(type="appraisal", date="2025-06-30", participant_ids=[jan, manager],
                   year=2025, rating="Meets expectations", signed_by=manager)
    built = case.build()
    save_case(built, tmp_path)
    assert load_case(tmp_path).events["EVT-002"].signed_by == "P002"


# Through ingest: the storylines input carries signedBy (step 5 sets it).

def _employees():
    return {"company": {"employerName": "Acme Logistics B.V. (fictional)"},
            "employees": [{"firstName": "Jan", "lastName": "de Vries", "department": "IT",
                           "position": "Software Developer", "hireDate": "2021-03-01",
                           "contractType": "Permanent", "hoursPerWeek": 40,
                           "startSalary": 4350, "managerName": "M. Bakker (fictional)"}]}


def _story(signed_by):
    return {"storylines": [{"employeeId": "100101", "appraisals": [
        {"year": 2025, "rating": "Meets expectations", "signedBy": signed_by}]}]}


def test_ingest_keeps_signed_by():
    cases, _ = ingest_employees(_employees())
    cases, _ = ingest_storylines(cases, _story("P002"))
    appraisal = next(e for e in cases[0].events.values() if e.type == "appraisal")
    assert appraisal.signed_by == "P002"
    assert cases[0].personas["P002"].name == "M. Bakker (fictional)"


def test_ingest_refuses_a_signer_the_case_does_not_hold():
    cases, _ = ingest_employees(_employees())
    with pytest.raises(ValueError, match=r"Unknown persona: P009 \(field signed_by\)"):
        ingest_storylines(cases, _story("P009"))
