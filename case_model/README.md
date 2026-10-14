# Case model — module contract (version 1)

Owner: Giulia Bellomo. Status: v1 (14 October 2026).

## What it is for

The case model is the single place where the facts of one dossier live: who is
involved, how they are employed, what happened, and the documents that record
it. Other modules do not keep their own copy of a name, a date or an amount —
they read it from here. **The case model stores facts; it does not generate
text.** Writing document bodies is the generation module's job.

## How to use it

```python
from case_model import CaseModel, Money

case = CaseModel("100101")
case.set_dossier(employee_number="100101", folder_title="Personeelsdossier Jan de Vries")

employer = case.add_organisation(name="AMEXIO B.V.", kind="employer")       # "ORG-01"
jan = case.add_persona(name="Jan de Vries", role="employee", salutation="Mr")  # "P001"
officer = case.add_persona(name="Petra Jansen", role="hr_officer", salutation="Ms",
                           organisation_id=employer)                          # "P002"

case.add_employment(persona_id=jan, organisation_id=employer, position="Software Developer",
                    department="Engineering", start_date="2021-03-01",
                    contract_type="permanent", hours=40,
                    salary=Money(amount="3850.00", currency="EUR"))

evt = case.add_event(type="hiring", label="Contract signed", date="2021-03-01",
                     participant_ids=[jan, officer], summary="Jan starts as developer.")   # "EVT-001"

case.add_document(type="employment_contract", event_id=evt, participant_ids=[jan, officer],
                  text="[stub]",
                  metadata={"employee_id": "100101", "document_type": "employment_contract",
                            "document_date": "2021-03-01", "confidential": True,
                            "tags": ["contract", "hr"]})                      # "DOC-001"

dossier = case.build()   # a validated Case — every link checked in one call
```

## The parts

| Part | What it holds | ID |
|---|---|---|
| Persona | a person; a professional persona points at an organisation | `P001` |
| Organisation | a company or body (the employer, an agency) | `ORG-01` |
| Employment | a person's job at an organisation (position, salary as `Money`, …) | — (linked) |
| Event | something that happened, on a date, with participants | `EVT-001` |
| Document | a record tied to an event, with five metadata fields | `DOC-001` |
| Dossier | dossier-level facts (employee number, folder title, description) | — |
| Case | one object that holds all of the above | — |

Document metadata carries AMEXIO's five attributes: `employee_id`,
`document_type`, `document_date`, `confidential`, `tags`.

## What you get back

- `add_*` methods return the new ID; `build()` returns a validated `Case`.
- Read a fact through its ID: `case.personas["P001"].name`, `case.events["EVT-001"].date`.
- A built `Case` exposes `dossier`, `personas`, `organisations`, `employments`,
  `events`, `documents`.

## ID and format rules (M02)

- **AX-011 — one ID pattern per type.** `persona P001`, `organisation ORG-01`,
  `vehicle V001`, `event EVT-001`, `document DOC-001`; the employee number is
  six digits (`100101`). A value in the wrong shape is refused.
- **AX-012 — IDs come from the case model, not the caller.** Passing `id=` raises.
- **AX-013 — dates are ISO 8601.** `"12/03/2026"` is refused.
- **AX-014 — amounts are a number plus a currency** (`Money`). The text
  `"€3,240.00"` is refused.

## The reference dossier

`build_reference_case()` returns the HR reference dossier 100101 (Jan de Vries):
a small set of hand-entered facts used as a regression fixture and for
save/load. It is test data — document `text` is a one-line stub, not generated
prose.

```python
from case_model.reference_dossier import build_reference_case
case = build_reference_case()
```

## Saving and loading

A case is written as four JSON files and read back into an equal case:
`case.json` (case number + dossier facts), `cast.json` (personas,
organisations, employments), `storyline.json` (events), `documents.json`.

```python
from case_model.storage import save_case, load_case
save_case(case, "runs/100101")
assert load_case("runs/100101") == case
```

## What it refuses

- An ID from the caller (AX-012).
- An unknown participant, organisation or event — the link is checked when the
  part is added and again when the `Case` is built.
- A date that is not ISO 8601 (AX-013); an amount as formatted text (AX-014).
- A dossier without an employee number, or a missing required field — a
  validation error names the field.

## Not built yet

Fact lookup and placeholders, change propagation, versioned run storage, run
configuration and the review interface. Planned for sprint 3 onward (M04+).

## Tests

```bash
python3 -m pytest -v
```
