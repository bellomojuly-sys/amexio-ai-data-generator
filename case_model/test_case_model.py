import pytest
from case_model import CaseModel


def test_ids_are_assigned_by_code():
    case = CaseModel("CLM-10045")
    first = case.add_persona(name="Sanne Example", role="claimant", salutation="Ms")
    second = case.add_persona(name="Tom Sample", role="claim_handler", salutation="Mr")
    assert first == "P001"
    assert second == "P002"

def test_event_references_persona_by_id():
    case = CaseModel("CLM-10045")
    claimant = case.add_persona(name="Sanne Example", role="claimant", salutation="Ms")
    event_id = case.add_event(
        type="incident",
        label="Collision",
        date="2026-03-04",
        participant_ids=[claimant],
        summary="Rear-end collision at a traffic light.",
    )
    assert event_id == "EVT-001"
    assert case.events["EVT-001"].participant_ids == ["P001"]

def test_unknown_persona_is_refused():
    case = CaseModel("CLM-10045")
    with pytest.raises(ValueError):
        case.add_event(
            type="incident",
            label="Collision",
            date="2026-03-04",
            participant_ids=["P404"],
            summary="Rear-end collision at a traffic light.",
        )
    assert case.events == {}
