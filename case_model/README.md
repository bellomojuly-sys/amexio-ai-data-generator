Case model — module contract

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

## Not built yet

Organisations, employment data (position, department, salary), documents and their metadata, placeholders, saving to files. Do not depend on them yet. Planned for sprint 2 and 3.

## Tests

```bash
python3 -m pytest -v
```