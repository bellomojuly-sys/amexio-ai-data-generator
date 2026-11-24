"""AX-069 — nothing points to a missing ID; AX-070 — every refusal names the entity and the field.

A case is only ever changed by building or loading it again, so "deleting" an
entity means a case whose JSON no longer holds it. Each test removes one part
that something still references and checks that the case is refused, naming
who points at it and through which field.
"""

import pytest
from pydantic import ValidationError
from case_model import Case, CaseModel, Money


def _jan():
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    employer = case.add_organisation(name="Acme Logistics B.V.", kind="employer")       # ORG-01
    provider = case.add_organisation(name="Training Academy", kind="training_provider")  # ORG-02
    jan = case.add_persona(name="Jan de Vries", role="employee", organisation_id=employer)  # P001
    manager = case.add_persona(name="M. Bakker", role="manager", organisation_id=employer)  # P002
    case.add_employment(persona_id=jan, organisation_id=employer, position="Software Developer",
                        department="IT", start_date="2021-03-01", contract_type="Permanent",
                        hours=40, salary=Money(amount="4350.00", currency="EUR"))
    hire = case.add_event(type="hire", date="2021-03-01", participant_ids=[jan])       # EVT-001
    case.add_event(type="training", date="2024-02-20", participant_ids=[jan],          # EVT-002
                   course="Secure Coding Fundamentals", duration_days=2, provider_id=provider)
    case.add_event(type="appraisal", date="2025-06-30", participant_ids=[jan, manager],  # EVT-003
                   year=2025, rating="Meets expectations", signed_by=manager)
    case.add_document(type="employment_contract", event_id=hire, participant_ids=[jan],  # DOC-001
                      metadata={"employee_id": "100101", "document_type": "employment_contract",
                                "document_date": "2021-03-01", "confidential": True})
    return case.build().model_dump(mode="json")


def _refused(data):
    with pytest.raises(ValidationError) as error:
        Case.model_validate(data)
    return str(error.value)


def test_the_full_case_is_valid():
    Case.model_validate(_jan())


# AX-069 — remove a part that is still referenced: the case is refused.

def test_removing_the_manager_refuses_the_appraisal_that_involves_him():
    data = _jan()
    del data["personas"]["P002"]
    message = _refused(data)
    assert "Event EVT-003 references unknown persona 'P002' (field participant_ids)" in message


def test_removing_the_signer_refuses_the_event():
    data = _jan()
    data["events"]["EVT-003"]["participant_ids"] = ["P001"]
    del data["personas"]["P002"]
    assert "Event EVT-003 is signed by unknown persona 'P002' (field signed_by)" in _refused(data)


def test_removing_the_employee_refuses_the_employment():
    data = _jan()
    del data["personas"]["P001"]
    assert "Employment points at unknown persona 'P001' (field persona_id)" in _refused(data)


def test_removing_the_employer_refuses_the_personas_that_work_there():
    data = _jan()
    del data["organisations"]["ORG-01"]
    assert "Persona P001 points at unknown organisation 'ORG-01' (field organisation_id)" in _refused(data)


def test_removing_the_training_provider_refuses_the_training():
    data = _jan()
    del data["organisations"]["ORG-02"]
    assert "Event EVT-002 points at unknown training provider 'ORG-02' (field provider_id)" in _refused(data)


def test_removing_the_hire_refuses_its_contract():
    data = _jan()
    del data["events"]["EVT-001"]
    assert "Document DOC-001 references unknown event 'EVT-001' (field event_id)" in _refused(data)


def test_removing_a_document_participant_refuses_the_document():
    data = _jan()
    data["documents"]["DOC-001"]["participant_ids"] = ["P009"]
    assert "Document DOC-001 references unknown persona 'P009' (field participant_ids)" in _refused(data)


# AX-070 — the refusals of the builder and of the rules between events name the field too.

def test_the_builder_names_the_field_of_a_missing_reference():
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    with pytest.raises(ValueError, match=r"Unknown organisation: ORG-09 \(field organisation_id\)"):
        case.add_persona(name="Jan de Vries", role="employee", organisation_id="ORG-09")
    with pytest.raises(ValueError, match=r"Unknown persona: P009 \(field participant_ids\)"):
        case.add_event(type="hire", date="2021-03-01", participant_ids=["P009"])
    with pytest.raises(ValueError, match=r"Unknown event: EVT-009 \(field event_id\)"):
        case.add_document(type="employment_contract", event_id="EVT-009", participant_ids=[],
                          metadata={"employee_id": "100101", "document_type": "employment_contract",
                                    "document_date": "2021-03-01", "confidential": True})


def test_an_event_before_the_hire_names_the_event_and_the_field():
    data = _jan()
    data["events"]["EVT-002"]["date"] = "2020-01-10"
    assert "Event EVT-002 (training, 2020-01-10) happens before the hire on 2021-03-01 (field date)" in _refused(data)


def test_two_hires_name_both_events():
    data = _jan()
    data["events"]["EVT-002"] = {"id": "EVT-002", "type": "hire", "date": "2021-03-01",
                                 "participant_ids": ["P001"]}
    assert "found 2: EVT-001, EVT-002 (field type)" in _refused(data)


def test_a_wrong_employee_number_names_the_field():
    data = _jan()
    data["dossier"]["employee_number"] = "10010"
    assert "(field employee_number)" in _refused(data)
