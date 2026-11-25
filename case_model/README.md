# Case model — module contract (version 2.1)

Owner: Giulia Bellomo. Status: v2.1 (25 November 2026): the lists come from a
domain configuration, so the case model works for any domain; HR is the first.
v2.1 adds case facts, domain metadata, employment and organisation kinds per
domain, and the generator of fact values.
v1.2 added `signed_by`; v1.1 is tag `v1.1`, v1 is tag `v1`. What changed and
why: [v1 → v1.1](#v1--v11), [v1.1 → v1.2](#v11--v12), [v1.2 → v2.0](#v12--v20).

## What it is for

The case model is the single place where the facts of one dossier live: who is
involved, how they are employed, what happened, and the documents that record
it. Other modules do not keep their own copy of a name, a date or an amount —
they read it from here. **The case model stores facts; it does not generate
text.** Writing document bodies is the generation module's job.

## How to use it

From the generator's JSON (the usual way, see [Ingest](#ingest--the-generators-json-goes-in-v11)):

```bash
python -m case_model.ingest employees.json storylines.json --out runs/batch-01
```

Or step by step, in code:

```python
from case_model import CaseModel, Money

case = CaseModel("100101")
case.set_dossier(employee_number="100101", folder_title="100101 Jan de Vries")

employer = case.add_organisation(name="Acme Logistics B.V.", kind="employer")   # "ORG-01"
provider = case.add_organisation(name="Training Academy", kind="training_provider")  # "ORG-02"
jan = case.add_persona(name="Jan de Vries", role="employee", organisation_id=employer)  # "P001"
manager = case.add_persona(name="M. Bakker", role="manager", organisation_id=employer)  # "P002"

case.add_employment(persona_id=jan, organisation_id=employer, position="Software Developer",
                    department="IT", start_date="2021-03-01", contract_type="Permanent",
                    hours=40, salary=Money(amount="4350.00", currency="EUR"))

hire = case.add_event(type="hire", date="2021-03-01", participant_ids=[jan])      # "EVT-001"
case.add_event(type="appraisal", date="2026-06-30", participant_ids=[jan, manager],
               year=2026, rating="Exceeds expectations")                         # "EVT-002"

case.add_document(type="employment_contract", event_id=hire, participant_ids=[jan],
                  metadata={"employee_id": "100101", "document_type": "employment_contract",
                            "document_date": "2021-03-01", "confidential": True,
                            "tags": ["contract", "hr"]})                        # "DOC-001"

dossier = case.build()   # a validated Case — every link and rule checked in one call
```

## The parts

| Part | What it holds | ID |
|---|---|---|
| Persona | a person; a professional persona points at an organisation | `P001` |
| Organisation | a company or body (the employer, an agency) | `ORG-01` |
| Employment | a person's job at an organisation (position, salary as `Money`, …) | — (linked) |
| Event | something that happened, on a date, with participants — one class per type (below) | `EVT-001` |
| Document | a record tied to an event (none for payslips), with five metadata fields; `text` optional | `DOC-001` |
| Dossier | dossier-level facts (employee number, folder title, description) | — |
| Case | one object that holds all of the above | — |

Document metadata carries AMEXIO's five attributes: `employee_id`,
`document_type`, `document_date`, `confidential`, `tags`.

**Events (v1.1).** Every event has `id`, `type`, `date`, `participant_ids` and
optional `label`, `summary`, and since v1.2 an optional `signed_by`: the persona
who signs the event's documents (a persona of the case). The `type` picks the class and its own facts:

| `type` | Own facts |
|---|---|
| `hire` | — (the agreed terms are in `Employment`) |
| `contract_change` | `reason`; optional `new_salary` (Money), `new_position`, `new_contract_type`, `new_hours` |
| `training` | `course`, `duration_days`, `provider_id` (an Organisation) |
| `appraisal` | `year`, `rating`; optional `comment` |
| `medical_check` | `result` |
| `absence` | optional `end_date` (dates only, never a cause) |
| `termination` | `reason`; optional `notice_date` |

**Closed value sets (v1.1).** `contract_type`: Permanent, Temporary.
`document_type`: employment_contract, payslip, medical_check,
performance_appraisal, training_certificate (AMEXIO) and contract_amendment,
annual_income_statement, absence_report, termination_letter (proposed).
`rating`: Below / Meets / Exceeds expectations. `result`: Fit for work, Fit for
work with adjustments. Termination `reason`: Resignation, End of temporary
contract, Mutual agreement, Retirement. Persona `role`: employee, manager,
hr_officer, examiner.

## Stored or derived (v1.1)

The field-by-field analysis of AMEXIO's five PDFs ("AMEXIO Full Dossier Format
Analysis") sorts every printed value into *generate*, *reuse*, *calculate*,
*constant* or *conditional*. The case model stores only the facts (generate
and conditional values). Calculated and constant values are derived when a
document is written, so each fact has one copy (D3b) — the same choice as the
generator's `plan()`. Two cases are fixed here:

- **Payslip period.** A payslip has no event (D3a). Its period is the month and
  year of `metadata.document_date`: `2026-09-25` prints "Payslip September
  2026" and "Period: September 2026". The payment date (the 25th), wage tax and
  net salary are not stored; they are derived from the period, the salary in
  `Employment` and the run configuration.
- **Training certificate title.** The title depends on the course: "Training
  Certificate" by default, "Training Certificate Health & Safety" for a health
  and safety course (AMEXIO's employee 100103). This is a template rule; the
  case model stores only `course` on the `training` event.

Other derived values follow the same rule: next medical check (examination
date + interval), appraisal review period (year + review cycle), document
titles, header and footer, file names. The rules and their parameters belong to
the run configuration and placeholders (M04), not to the case model.

## What you get back

- `add_*` methods return the new ID; `build()` returns a validated `Case`.
- Read a fact through its ID: `case.personas["P001"].name`, `case.events["EVT-001"].date`.
- A built `Case` exposes `dossier`, `personas`, `organisations`, `employments`,
  `events`, `documents`.

## ID and format rules (M02)

- **AX-011 — one ID pattern per type.** `persona P001`, `organisation ORG-01`,
  `event EVT-001`, `document DOC-001`; the employee number is six digits
  (`100101`). A value in the wrong shape is refused — also with a trailing
  newline or non-ASCII digits (AX-011a), and also in a case read from JSON
  (AX-011b).
- **AX-012 — IDs come from the case model, not the caller.** Passing `id=` raises.
- **AX-013 — dates are ISO 8601.** `"12/03/2026"` is refused.
- **AX-014 — amounts are a number plus a currency** (`Money`). The text
  `"€3,240.00"` is refused.

## Ingest — the generator's JSON goes in (v1.1)

The generator asks the LLM for two JSON objects, in the shapes its prompts fix,
and sends them here unchanged (camelCase names). The case model creates the
cases, assigns every ID, normalizes the values and records each correction
(decision D4).

```python
from case_model.ingest import ingest_employees, ingest_storylines, ingest_files

cases, corrections = ingest_employees(employees_json)            # one case per employee
cases, more = ingest_storylines(cases, storylines_json)          # their events
cases, corrections = ingest_files("employees.json", "storylines.json", out_dir="runs/b1")
```

- `employees.json`: `{"company": {"employerName", "trainingProvider", "examiner",
  "absenceService", "directorName"}, "employees": [{"firstName", "lastName",
  "department", "position", "isManager", "hireDate", "contractType",
  "hoursPerWeek", "startSalary", "managerName"?}]}`. The first employee gets
  number `100101` (or `first_number`), the next `100102`, in list order.
- `storylines.json`: `{"storylines": [{"employeeId", "events": [...],
  "appraisals": [...]}]}`, with the event shapes of the generator's prompt.
- A department's manager is the employee marked `isManager` there; the
  managers themselves report to `directorName`; `managerName` overrides both.
- An appraisal without a `date` is dated 30 June of its `year`.
- Output folder: one case folder per employee (`runs/b1/100101/case.json`, …)
  and `corrections.json`.

## JSON Schemas for the generator (v1.1)

`case_model/schema/` holds `input.employees.schema.json`,
`input.storylines.schema.json` and `case.schema.json`, generated with
`python3 -m case_model.schema`. A test fails when they no longer match the
code. A schema carries the shape only: the rules between parts hold only
through `load_case`.

## The reference dossier

`build_reference_case()` returns the HR reference dossier 100101 (Jan de Vries).
Since v1.1 it is **AMEXIO's own employee 100101** (decision D1), built by
ingesting AMEXIO's example in the generator's JSON shapes
(`fixtures/generator/amexio_example/`). Its values follow the generator's
AMEXIO preset and are provisional until each one is checked against AMEXIO's
PDFs (BR-00); it holds no documents until then.

```python
from case_model.reference_dossier import build_reference_case
case = build_reference_case()
```

**AX-019 — the reference dossier is the regression anchor.** Its full exported
form is frozen in `reference_dossier.golden.json`, and
`test_reference_dossier_matches_golden` checks the fixture against it on every
run (and on every push, through CI). Change any fact — a name, a date, an
amount, a participant — and the test fails on purpose. When the change is
intended, regenerate the snapshot:

```bash
python3 -m case_model.reference_dossier
```

## Generation and export read through the module (AX-020)

Generation and export do not keep their own copy of a fact; they read the
dossier through this module. A built `Case` is the read surface — `dossier`,
`personas`, `organisations`, `employments`, `events`, `documents`, and
`case.model_dump(mode="json")` for a plain, serialisable snapshot — and
`storage.save_case` / `load_case` move a whole case to and from JSON. Facts
stay here; writing document bodies is the generation module's job.

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
- An event signed by a persona the case does not hold (`signed_by`, v1.2).
- A part that is still referenced cannot disappear: a case whose JSON lost a
  persona, organisation or event that something points at is refused (AX-069).

Every refusal names the entity and the field, e.g. `Event EVT-003 references
unknown persona 'P002' (field participant_ids)` (AX-070).
- A date that is not ISO 8601 (AX-013); an amount as formatted text (AX-014).
- A dossier without an employee number, or a missing required field — a
  validation error names the field.
- A value outside a closed list, an event without its own facts, or an event
  of an unknown type.
- A story that cannot happen: two hires, a hire on another day than the
  employment start, anything before the hire or after the last working day,
  an absence that ends before it starts.
- A non-recurring document without an event; metadata that names another
  document type or another employee.
- From the generator: an `id`, a field the shape does not name, a storyline
  for an employee that has no case.

## v1 → v1.1

| Change | Why | Test |
|---|---|---|
| Typed events (7 types) | facts such as a rating had no field (D2) | `test_events.py` |
| Rules between events | a case must tell a possible story | `test_events.py` (BR-06) |
| Closed value sets; `salutation` optional | AMEXIO prints from fixed lists; the generator sends no salutation | `-k "outside_the_list or salutation or role"` |
| Documents: `event_id` optional for recurring types, `text` optional | one copy of each fact (D3a, D3b) | `-k "payslip or contract_without or metadata_"` |
| Strict ID patterns, checked on load | AX-011a, AX-011b | `-k "pattern or malformed"` |
| `vehicle` ID type removed | insurance leftover; the domain is HR | `-k "four_types"` |
| Ingest of the generator's JSON + command | the generator's data passes through the case model (D4) | `test_ingest.py` |
| Reference dossier = AMEXIO's 100101, through ingest | D1 | `test_reference_dossier.py` |
| JSON Schemas; fixtures test | the browser demo builds its types from them (BR-10, BR-11) | `test_fixtures.py` |

## Filling a text (M04, AX-023 … AX-025)

The Fill step (step 8, Valentin) writes a document text by replacing each
`{{ path }}` with a fact of the case. `case_model.fill` guarantees three things:

```python
from case_model import fact_paths, fill_text, format_fact
fact_paths(case)        # every path that prints one fact: offer these in the prompt
fill_text(case, "Dear {{ personas.P001.name }}, salary {{ employments.P001.salary }}.")
# "Dear Jan de Vries, salary EUR 4.350."
fill_text(case, text, {"employments.P001.salary": "eurPlain"})   # format from the template field
```

- **AX-023 — every placeholder resolves.** `fact_paths` lists only paths that
  resolve to one printable value; internal IDs (`id`, `persona_id`,
  `signed_by`, …) are never offered.
- **AX-024 — or the run stops.** `fill_text` raises `UnresolvedPlaceholders`
  naming every placeholder at once that is unknown, has no value, names several
  values, points at an internal ID, or is malformed. Never a silent blank.
- **AX-025 — formatted only when printed.** `format_fact` uses AMEXIO's formats,
  the same as the generator's `src/spec/format.ts`: `date` 14-04-2026,
  `monthYear` September 2026, `eurGrouped` EUR 4.350, `eurPlain` EUR 4350,
  `days` 2 days. Without a format, a date prints as `date` and an amount as
  `eurGrouped`. The case keeps ISO dates and numeric amounts.

## Ingest for any domain (v2.1, GD-05)

`ingest_cases(domain, data, first_number, number_format, seed, out_dir)` reads
one JSON shape for every domain (`schema/input.cases.schema.json`), **without
IDs**: personas and organisations have a local key (`"holder"`, `"insurer"`)
that events and documents use; an event may have a `key` for documents.

```python
from case_model import ingest_cases
cases, corrections = ingest_cases("building_permit", data, first_number=1,
                                  number_format="BP-{:05d}", out_dir="runs/permits")
```

- Code assigns every ID and the case number (`number_format`, checked against
  the domain's pattern); an `id` anywhere is refused.
- Events are numbered in date order; references, participants and `signed_by`
  are translated from local keys; an unknown key is refused naming its place.
- Code fills a document's `employee_id`, `document_type` and, from its event,
  `document_date`; missing case facts are generated by their rule.
- A value written differently from a closed list is corrected and returned as
  a `CaseCorrection`; nothing is saved unless every case is valid.
- The HR ingest of Robin's generator (`ingest_employees`, `ingest_storylines`)
  stays as it is. Tests: `test_ingest_any.py`.

## v2.0 → v2.1: case facts and the rest of the configuration

| A domain configuration may also hold | What it does | HR |
|---|---|---|
| `case_facts` | facts of the whole case (a policy number, a "fact" field of a template), stored once in `case.facts`, read as `facts.<name>` by every document | none |
| `metadata_fields` | document metadata beyond AMEXIO's five attributes; any other key is refused | none |
| `uses_employment` | only such a domain may hold `Employment` | yes |
| `organisation_kinds` | the kinds an organisation may have (None = free) | free |
| field `min`, `max`, `currency` | bounds and currency of a value; also the rule facts are generated from | — |

```python
from case_model.facts import generate_facts
facts = generate_facts(domain, random.Random(seed), given={"policy_number": "HP-2019-0777"})
case.set_facts(**facts.model_dump())
```

`generate_facts` makes every declared fact by its rule (a value from the list,
an amount or a date between min and max); a given value (a constant of the
approved configuration) wins and is checked; free text is never generated (it
is the LLM's to write). Tests: `test_facts.py`.

## v1.2 → v2.0: any domain

Until v1.2 the HR lists were code. Since v2.0 they are a `DomainConfig`
(`case_model/domain.py`); HR is `case_model.domains.HR`, the same lists as
before, and every HR file is saved byte for byte as before.

| A domain configuration holds | HR |
|---|---|
| `roles` | employee, manager, hr_officer, examiner |
| `event_types`: per type its fields, each with a `format` (text, date, money, integer, number, persona, organisation), `required`, closed `values`, `gt`, `ends_period`, `label` | the 7 types of v1.1 |
| `document_types`, each `recurring` or not | the 9 types; payslip and annual income statement recurring |
| `rules`: `first_event` (at most one, nothing before it), `first_event_starts_employment`, `last_event` (at most one, nothing after it), `last_event_label` | hire, termination ("last working day") |
| `case_number_pattern` | six digits |

```python
from case_model import CaseModel, DomainConfig, register_domain
register_domain(DomainConfig.model_validate(config_json))   # checked first: a malformed one is refused
case = CaseModel("CL000123", domain="insurance_claim")
```

- From the configuration the code builds one event class per type
  (`AppraisalEvent`, `ClaimFiledEvent`, …): fields are typed, a field the type
  does not define is refused, a reference field must point at a persona or
  organisation of the case.
- A case carries its `domain`; `case.json` writes it only when it is not HR.
- `case.schema.json` is HR's typed schema (the demo's types);
  `domain.schema.json` is the shape of a domain configuration.
- Tests: `test_domains.py` (HR = v1.2's lists, malformed configurations, a
  second domain with its own timeline, rules, save/load and fill).

## v1.1 → v1.2

| Change | Why | Test |
|---|---|---|
| Optional `signed_by` (persona ID) on every event; `signedBy` in the storylines input | who signs an appraisal when the manager has left (BR-16 Q1, pipeline contract §6); set by step 5 Dates & participants | `test_signed_by.py` |

A v1.1 case still loads and is saved byte for byte as before: an empty
`signed_by` is not written.

## Fact lookup (AX-022)

Read one stored fact from a built `Case` by a dotted path, the same path a
document template names in a `{{ … }}` placeholder (AX-021, see
`docs/PIPELINE_CONTRACT.md`):

```python
from case_model import get_fact
get_fact(case, "personas.P001.name")            # "Jan de Vries"
get_fact(case, "employments.P001.salary.amount")  # Decimal("4350.00")
```

Path grammar is `collection.id.field…`: `dossier.<field>`, `personas.<id>.…`,
`organisations.<id>.…`, `events.<id>.…`, `documents.<id>.…`, and
`employments.<persona_id>.…` (the list is addressed by persona id; one
employment per persona). An unknown collection, id or field raises `UnknownPath`
with a clear message — never a silent blank. Traversal only reaches declared
case-model fields, so a path cannot read a method or a value's attribute.

## Not built yet

Placeholder resolution over a whole document, change propagation, versioned run
storage, run configuration and the review interface. Planned for sprint 3 onward
(M04+).

## Tests

```bash
python3 -m pytest -v
```

GitHub Actions (`.github/workflows/tests.yml`) runs the whole suite on every
push and pull request, so a change that drifts the reference dossier (AX-019) is
caught in CI, not only locally.

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
| AX-016, AX-017 | `03c2084` | Reference dossier 100101 loads; every participant exists; five documents with event and participant | `-k "test_reference_dossier"` (5) |
| AX-018 | `12c9a2d` | Saved to four JSON files and loaded back equal | `-k "test_storage"` (4) |
| AX-019 | this commit | The reference dossier is frozen as a golden snapshot; a deliberate break fails, and CI runs it on every push | `-k "matches_golden"` (1) |
| AX-020 | tag `v1` | Case model v1 is tagged for integration; generation and export read the dossier through the module | `git show v1 --stat` |

All 100 tests (v1.1): `python3 -m pytest -v`.
