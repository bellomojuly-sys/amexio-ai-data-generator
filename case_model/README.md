## Case model — module contract

Owner: Giulia Bellomo. Status: first slice (7 October 2026).

## What it is for

The case model is the single place where the facts of one dossier live: who is involved and what happened. Other modules do not keep their own copy of a name or a date. They ask the case model.

## How to use it

Run from the repository root:

```python
from case_model.case_model import CaseModel

case = CaseModel("100101")
```

### Add a persona

```python
employee = case.add_persona(name="Jan de Vries", role="employee", salutation="Mr")
# returns "P001"
```

| Field | Required | Type |
|---|---|---|
| name | yes | text |
| role | yes | text |
| salutation | yes | text |
| date_of_birth | no | date, ISO format `YYYY-MM-DD` |
| address | no | text |

### Add an event

```python
event = case.add_event(
    type="hiring",
    label="Employment contract signed",
    date="2021-03-01",
    participant_ids=[employee],
    summary="Jan de Vries starts as Software Developer.",
)
# returns "EVT-001"
```

| Field | Required | Type |
|---|---|---|
| type | yes | text |
| label | yes | text |
| date | yes | date, ISO format `YYYY-MM-DD` |
| participant_ids | yes | list of persona IDs |
| summary | yes | text |

## What you get back

- `add_persona` and `add_event` return the new ID as text.
- Read a fact through the ID: `case.personas["P001"].name`, `case.events["EVT-001"].date`.
- An event holds persona IDs, never names: `case.events["EVT-001"].participant_ids` is `["P001"]`.

## What it refuses

- **An ID from the caller.** IDs are assigned by code (`P001`, `EVT-001`), never by the LLM and never by another module. Passing `id=` raises an error.
- **An unknown participant.** `add_event` raises `ValueError("Unknown persona: P404")` and the event is not stored.
- **A date that is not a real date.** `date="yesterday"` raises a validation error.
- **A missing required field.** It raises a validation error that names the field.

## Also available (8 October 2026)

All of them return the new ID and follow the same rules: IDs come from code, references must exist.

```python
employer = case.add_organisation(name="Acme Logistics B.V.", type="employer")   # "ORG-01"
manager = case.add_persona(name="M. Bakker", role="manager", salutation="Mr",
                           organisation_id=employer)                          # refused if the ID is unknown
job = case.add_employment(persona_id=employee, organisation_id=employer,
                          position="Software Developer", department="IT",
                          start_date="2021-03-01", contract_type="Permanent",
                          hours_per_week=40, gross_monthly_salary=4350)       # "EMP-001"
doc = case.add_document(type="employment_contract", title="Employment Contract",
                        event_id=event, participant_ids=[employee],
                        metadata={"employee_id": "100101",
                                  "document_type": "Employment Contract",
                                  "document_date": "2021-03-01",
                                  "confidential": True,
                                  "tags": ["contract", "legal"]})            # "DOC-001"
```

- `add_employment` refuses an unknown persona or organisation, a missing field, and a salary written as text (`"EUR 4.350"`).
- `add_document` refuses an unknown event or participant. `text` is optional: generation fills it later. `metadata` holds the five attributes of AMEXIO's `import.xml`; dates must be `YYYY-MM-DD`.

## Not built yet

Dossier-level facts, one Case object that validates everything at once, ID format checks, placeholders, saving to files. Do not depend on them yet. Planned for sprint 2 and 3.

## Tests

```bash
python3 -m pytest -v
```
