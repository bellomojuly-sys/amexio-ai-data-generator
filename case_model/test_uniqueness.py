"""AX-015 — uniqueness test over 100 dossiers: 0 duplicate IDs."""

from case_model import CaseModel, Money


def _build_dossier(n):
    """A small but complete dossier, built the same way every time."""
    employee_number = f"{100000 + n:06d}"
    case = CaseModel(employee_number)
    case.set_dossier(employee_number=employee_number)

    org = case.add_organisation(name=f"Company {n}")
    people = [
        case.add_persona(name=f"Person {n}-{i}", role="employee")
        for i in range(3)
    ]
    case.add_employment(
        persona_id=people[0], organisation_id=org, position="Dev", department="Eng",
        start_date="2021-03-01", contract_type="Permanent", hours=40,
        salary=Money(amount="3000.00", currency="EUR"),
    )
    events = [
        case.add_event(type="training", date="2021-03-01", course=f"Course {i}",
                       duration_days=1, provider_id=org, participant_ids=[people[0]])
        for i in range(5)
    ]
    for i, evt in enumerate(events):
        case.add_document(
            type="training_certificate", event_id=evt, participant_ids=[people[0]],
            metadata={"employee_id": employee_number, "document_type": "training_certificate",
                      "document_date": "2021-03-01", "confidential": False, "tags": []},
        )
    return case.build()


def test_no_duplicate_ids_over_100_dossiers():
    cases = [_build_dossier(n) for n in range(100)]

    # Case numbers are unique across the batch.
    numbers = [c.case_number for c in cases]
    assert len(numbers) == len(set(numbers)) == 100

    # Within every dossier, no ID is handed out twice — across all types.
    global_pairs = set()
    for case in cases:
        ids = (
            list(case.personas)
            + list(case.organisations)
            + list(case.events)
            + list(case.documents)
        )
        assert len(ids) == len(set(ids)), f"duplicate id inside case {case.case_number}"
        for i in ids:
            global_pairs.add((case.case_number, i))

    # Each (case number, id) pair is unique across the whole batch.
    assert len(global_pairs) == sum(
        len(c.personas) + len(c.organisations) + len(c.events) + len(c.documents)
        for c in cases
    )
