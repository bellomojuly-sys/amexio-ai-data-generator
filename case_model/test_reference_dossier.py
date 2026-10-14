"""AX-016, AX-017 — the HR reference dossier 100101 loads and is coherent."""

from case_model.reference_dossier import build_reference_case


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

def test_five_documents_each_with_event_and_a_participant():
    # AX-017 — five documents, each with its event ID and at least one participant.
    case = build_reference_case()
    assert len(case.documents) == 5
    for document in case.documents.values():
        assert document.event_id in case.events
        assert len(document.participant_ids) >= 1
        for pid in document.participant_ids:
            assert pid in case.personas

def test_metadata_has_the_five_fields():
    case = build_reference_case()
    meta = case.documents["DOC-001"].metadata
    assert meta.employee_id == "100101"
    assert meta.document_type
    assert meta.document_date is not None
    assert isinstance(meta.confidential, bool)
    assert isinstance(meta.tags, list)
