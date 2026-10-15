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

## Traceability

Every closed microphase can be traced to a commit and checked from the terminal, from the repository root. Run a check with `python3 -m pytest -v -k "<selector>"`; open a commit with `git show <commit> --stat`.

AX-006 → AX-014 were first built step by step (my own commits `fced31a`, `dc337b6`, `72236b6` of 8 October in the team repo [amexio-ai-data-generator](https://github.com/bellomojuly-sys/amexio-ai-data-generator); branches `sprint2-m01-remaining-entities`, `ax-010-case-container`, `sprint-2-m02-id-format-rules` here) and then consolidated into v1 in commit `729d331`.

| Step | Commit (v1) | Proof | Check in the terminal |
|---|---|---|---|
| AX-001 → AX-003 | `6313d49` | IDs come from code; an event stores participant IDs; an unknown persona is refused | `-k "ids_are_assigned_by_code or event_references_persona or unknown_persona"` (3) |
| AX-004 | `6313d49` | The code lives in the team repository, folder `case_model/` | `git show 6313d49 --stat` |
| AX-005 | `81cb937` | Module contract: what comes in, what goes out, what is refused | this README |
| AX-006 | `729d331` | A persona points at a known organisation; an unknown one fails | `-k "known_organisation or unknown_organisation"` (2) |
| AX-007 | `729d331` | Employment links persona and organisation; a missing field fails | `-k "employment"` (2) |
| AX-008 | `729d331` | A document with an unknown event fails; metadata has AMEXIO's five fields | `-k "unknown_event or metadata_has"` (2) |
| AX-009 | `729d331` | A dossier needs a six-digit employee number | `-k "employee_number"` (3) |
| AX-010 | `729d331` | A full Case validates in one call; broken links fail | `-k "full_case or missing_event or build_without_dossier"` (3) |
| AX-011 | `729d331` | One ID pattern per type; wrong patterns fail | `-k "pattern or well_formed or five_types or example_id or next_id or non_string or unknown_type"` (22) |
| AX-012 | `729d331` | An ID written by the caller (or an LLM) is refused | `-k "caller"` (3) |
| AX-013 | `729d331` | "12/03/2026" fails; only ISO 8601 dates | `-k "non_iso_date"` (1) |
| AX-014 | `729d331` | "EUR 4.350" fails; amounts are number + currency | `-k "money or amount or thousands or currency"` (5) |
| AX-015 | `c6cfe17` | 100 dossiers, 0 duplicate IDs | `-k "uniqueness"` (1) |
| AX-016, AX-017 | `03c2084` | Reference dossier 100101 loads; every participant exists; five documents with event and participant | `-k "test_reference_dossier"` (4) |
| AX-018 | `12c9a2d` | Saved to four JSON files and loaded back equal | `-k "test_storage"` (4) |

All 54 tests: `python3 -m pytest -v`.
