import pytest
from case_model import Case, CaseModel, Dossier, Money


def _case_with_dossier():
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    return case


# AX-012 / AX-001 — IDs are assigned by code, counting up, per type.

def test_ids_are_assigned_by_code():
    case = _case_with_dossier()
    first = case.add_persona(name="Sanne Example", role="claimant", salutation="Ms")
    second = case.add_persona(name="Tom Sample", role="claim_handler", salutation="Mr")
    assert first == "P001"
    assert second == "P002"

def test_event_references_persona_by_id():
    case = _case_with_dossier()
    claimant = case.add_persona(name="Sanne Example", role="claimant", salutation="Ms")
    event_id = case.add_event(
        type="incident", label="Collision", date="2026-03-04",
        participant_ids=[claimant], summary="Rear-end collision.",
    )
    assert event_id == "EVT-001"
    assert case.events["EVT-001"].participant_ids == ["P001"]

def test_unknown_persona_is_refused():
    case = _case_with_dossier()
    with pytest.raises(ValueError):
        case.add_event(
            type="incident", label="Collision", date="2026-03-04",
            participant_ids=["P404"], summary="Rear-end collision.",
        )
    assert case.events == {}

def test_caller_supplied_id_is_refused():
    # AX-012
    case = _case_with_dossier()
    with pytest.raises(ValueError):
        case.add_persona(id="P001", name="Sanne", role="claimant", salutation="Ms")
    assert case.personas == {}

def test_non_iso_date_is_refused():
    # AX-013
    case = _case_with_dossier()
    pid = case.add_persona(name="Sanne", role="claimant", salutation="Ms")
    with pytest.raises(Exception):
        case.add_event(
            type="incident", label="Collision", date="12/03/2026",
            participant_ids=[pid], summary="Rear-end collision.",
        )
    assert case.events == {}


# AX-006 — organisations, and professional personas that point at them.

def test_persona_points_at_a_known_organisation():
    case = _case_with_dossier()
    org = case.add_organisation(name="AMEXIO B.V.", kind="employer")
    assert org == "ORG-01"
    officer = case.add_persona(name="Petra", role="hr_officer", salutation="Ms", organisation_id=org)
    assert case.personas[officer].organisation_id == "ORG-01"

def test_unknown_organisation_is_refused():
    case = _case_with_dossier()
    with pytest.raises(ValueError):
        case.add_persona(name="Petra", role="hr_officer", salutation="Ms", organisation_id="ORG-99")


# AX-007 — employment links a persona to an organisation; a salary is Money.

def test_employment_links_persona_and_organisation():
    case = _case_with_dossier()
    org = case.add_organisation(name="AMEXIO B.V.")
    jan = case.add_persona(name="Jan", role="employee", salutation="Mr")
    job = case.add_employment(
        persona_id=jan, organisation_id=org, position="Dev", department="Eng",
        start_date="2021-03-01", contract_type="permanent", hours=40,
        salary=Money(amount="3850.00", currency="EUR"),
    )
    assert job.persona_id == "P001" and job.organisation_id == "ORG-01"

def test_employment_missing_field_fails():
    case = _case_with_dossier()
    org = case.add_organisation(name="AMEXIO B.V.")
    jan = case.add_persona(name="Jan", role="employee", salutation="Mr")
    with pytest.raises(Exception):
        case.add_employment(
            persona_id=jan, organisation_id=org, position="Dev",
            # department missing
            start_date="2021-03-01", contract_type="permanent", hours=40,
            salary=Money(amount="3850.00", currency="EUR"),
        )


# AX-008 — documents tie to an event and carry the five metadata fields.

def test_document_with_unknown_event_is_refused():
    case = _case_with_dossier()
    jan = case.add_persona(name="Jan", role="employee", salutation="Mr")
    with pytest.raises(ValueError):
        case.add_document(
            type="payslip", event_id="EVT-404", participant_ids=[jan],
            text="[stub]",
            metadata={"employee_id": "100101", "document_type": "payslip",
                      "document_date": "2021-03-31", "confidential": True, "tags": []},
        )


# AX-009 — dossier-level facts; without an employee number it fails.

def test_dossier_needs_an_employee_number():
    with pytest.raises(Exception):
        Dossier(folder_title="No number")

def test_employee_number_must_be_six_digits():
    with pytest.raises(ValueError):
        Dossier(employee_number="123")


# AX-010 — a full Case validates in one call; broken links are refused.

def test_full_case_validates_in_one_call():
    case = _case_with_dossier()
    org = case.add_organisation(name="AMEXIO B.V.")
    jan = case.add_persona(name="Jan", role="employee", salutation="Mr")
    officer = case.add_persona(name="Petra", role="hr_officer", salutation="Ms", organisation_id=org)
    evt = case.add_event(type="hiring", label="Signed", date="2021-03-01",
                         participant_ids=[jan, officer], summary="Starts.")
    case.add_document(type="employment_contract", event_id=evt, participant_ids=[jan],
                      text="[stub]",
                      metadata={"employee_id": "100101", "document_type": "employment_contract",
                                "document_date": "2021-03-01", "confidential": True, "tags": []})
    built = case.build()
    assert isinstance(built, Case)
    assert built.case_number == "100101"

def test_case_refuses_document_pointing_at_missing_event():
    # Build a Case directly with an inconsistent link.
    from case_model import Document, DocumentMetadata, Event, Persona
    with pytest.raises(ValueError):
        Case(
            case_number="100101",
            dossier=Dossier(employee_number="100101"),
            personas={"P001": Persona(id="P001", name="Jan", role="employee", salutation="Mr")},
            documents={"DOC-001": Document(
                id="DOC-001", type="payslip", event_id="EVT-404", participant_ids=["P001"],
                text="[stub]",
                metadata=DocumentMetadata(employee_id="100101", document_type="payslip",
                                          document_date="2021-03-31", confidential=True),
            )},
        )

def test_build_without_dossier_fails():
    case = CaseModel("100101")
    with pytest.raises(ValueError):
        case.build()
