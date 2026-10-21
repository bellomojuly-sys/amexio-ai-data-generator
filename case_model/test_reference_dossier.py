"""AX-016, AX-017 — the HR reference dossier 100101 loads and is coherent.
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

def test_reference_dossier_matches_golden():
    # AX-019 — the fixture is the regression anchor. Its full exported form is
    # frozen in reference_dossier.golden.json, so changing any fact above (a
    # name, a date, an amount, a participant) makes this fail on purpose.
    # Regenerate the snapshot only when the change is intended:
    #     python3 -m case_model.reference_dossier
    exported = build_reference_case().model_dump(mode="json")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert exported == golden
