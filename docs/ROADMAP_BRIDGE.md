# Roadmap — case model v1.1 and generator bridge

Owner: Giulia Bellomo (case model). Counterpart: Robin Schekkerman (generator,
branch `Demo-Generator`, `generator/demo_dossier_generator/`).
Written 24 October 2026. Milestone **M03b**, inserted between M03 and M04.

## Goal

The case model is the single source of the facts, and Robin's generator works
on it in both directions:

- **① Read (the main goal):** the demo loads a case and renders its PDFs and
  `import.xml` from the case's facts, not from its own objects.
- **② Write:** when the demo generates new employees with the AI, it saves
  them as cases, so they pass through the case model (and later the review UI).

Done means:

1. The demo reads the reference case 100101 and renders AMEXIO's 5 PDFs and
   its `import.xml` entries identical to AMEXIO's files. This proves the case
   holds every fact AMEXIO prints.
2. The generator exports one case folder per employee (`case.json`,
   `cast.json`, `storyline.json`, `documents.json`) and `load_case` accepts
   every folder; CI runs `load_case` on the generator's fixtures on every push.
3. Dossier 100101 written by the generator from AMEXIO's example carries the
   same facts as the reference case.

Values that a rule computes (wage tax, net pay, next medical check) are not
stored: the generator's rules compute them from the case's facts (D3b).

## Handoff sprint — 24 October (a few hours)

The smallest piece that lets Robin start his side today: the case model
accepts his LLM JSON **exactly as his prompts produce it** (`src/ai/prompts.ts`),
creates the cases, and gives back case folders plus two JSON Schemas. Giulia
writes the code; for repetitive parts she writes the first two and the rest is
completed after review. Work on branch `case-model-v1.1`.

**Provisional defaults** (taken to hand off today; confirm with Robin):
D5 closed list of 9 document types · D6 the *input* keeps Robin's camelCase
unchanged, the `Case` stays snake_case · D7 provider = `Organisation`,
examiner = `Persona` · D8 file exchange now, Pyodide later · D9 the seeded
plot stays in the generator; the case model stores its results as facts.

### Giulia — before the handoff

**Status 24 Oct:** T0–T9 done on branch `case-model-v1.1` (100 tests green; a deliberate break of four rules fails the right test each time). T10: `docs/HANDOFF_ROBIN.md` written; commit, push and PR are Giulia's. The reference values are provisional until BR-00.

| # | Task | Done when | Time | Covers |
|---|---|---|---|---|
| T0 | Confirm the defaults above; create branch `case-model-v1.1` | Branch exists; defaults noted in the Decision Log as provisional | 10 min | BR-01 |
| T1 | Closed value sets (`Literal`): contract type, document type, rating, medical result, termination reason, persona role; `Persona.salutation` optional (Robin's JSON has none) | `"permanent"` fails, `"Permanent"` passes; a persona without salutation passes | 30 min | BR-04 |
| T2 | Typed events: 7 classes in a discriminated union on `type` (write `hire` and `appraisal`, then the other five) | Appraisal without `rating` fails; unknown type fails; save/load keeps the extra fields | 60 min | BR-05 |
| T3 | Event rules: `hire.date` = `Employment.start_date`, exactly one `hire`, nothing after `termination`, `absence.end_date` ≥ `date` | One break per rule fails with a clear message | 30 min | BR-06 |
| T4 | Documents: `event_id` optional only for `payslip` and `annual_income_statement`; `text` optional | Contract without event fails; payslip without event passes | 15 min | BR-08 |
| T5 | Ingest. Input models mirroring Robin's two JSONs (`{"employees":[…]}`, `{"storylines":[…]}`), refusing any `id`. `ingest_employees(json, first_number=100101)` → one `Case` per employee (employee number unique across the batch; employee `Persona`, manager `Persona`, employer `Organisation`, `Employment` with `Money`, `hire` event). `ingest_storylines(cases, json)` → events with IDs; unknown `employeeId` refused. Both return the corrections | AMEXIO's 4 example employees go in, 4 valid cases come out; an `id` in the input is refused | 60–75 min | D4 |
| T6 | Command: `python -m case_model.ingest employees.json storylines.json --out DIR` writes one case folder per employee (`save_case`) | Running it on the AMEXIO example writes 4 folders that `load_case` reads | 20 min | D8 step 1 |
| T7 | Reference dossier 100101 rebuilt **through ingest** from the AMEXIO example input (`case_model/fixtures/generator/amexio_example/`); golden regenerated. Values are provisional until BR-00 checks them against the PDFs | Golden test green; the old hand-written story is gone | 30 min | BR-09 (provisional) |
| T8 | Export two schemas into `case_model/schema/`: `input.schema.json` (what Robin sends) and `case.schema.json` (what he reads back), with the command that makes them | The AMEXIO example input validates against the first, the golden case against the second | 15 min | BR-10 |
| T9 | Test: every input under `case_model/fixtures/generator/` is ingested and each output folder loads with `load_case`; CI runs it | A broken fixture makes it fail | 15 min | BR-11 |
| T10 | Handover: `docs/HANDOFF_ROBIN.md` (schemas, command, file layout, rules outside the schema, the defaults to confirm), push, open the PR, message Robin | Robin can start R1–R3 with no questions | 20 min | BR-13 |

About 5 hours. If time runs short, T3 and T4 can follow tomorrow's
handoff without changing the contract Robin builds on; T1, T2, T5–T8 and T10
cannot. AX-011a/b (BR-02, BR-03) do not change the contract either: they follow
right after.

### Robin — after the handoff

| # | Task | Done when |
|---|---|---|
| R1 | TypeScript types from both schemas (`json-schema-to-typescript`, npm script) | `npm run build` passes with the generated types |
| R2 | The demo saves its two LLM JSONs (`employees.json`, `storylines.json`) as it gets them, before its own `normalize.ts` | Files written for every run |
| R6 | Reader: the demo loads a case folder (upload, plus the reference 100101 bundled) and maps it to its own objects for `plan()`, PDF and XML | The reference case renders in the demo |
| R3 | 2–3 input fixtures in `case_model/fixtures/generator/` from offline runs: a leaver, a temporary → permanent contract | T9's test green on them |
| R4 | Facts printed on documents that the case does not hold yet | List sent; each item becomes a field or a named rule |
| R5 | Insurance demo (CLM-10045) removed or marked legacy | No insurance data under the HR scope |

**Together, after both sides:** BR-14 (the demo renders the reference case and
the output equals AMEXIO's files) and BR-15 (generator facts = reference facts).

## Why it does not fit today

| Topic | Case model v1 | Generator | Fixed by |
|---|---|---|---|
| Unit | `Case` = one employee | `DossierSet` = all employees of a run | Generator adapter (R2) |
| Manager, examiner, training provider | not modelled / must be a `Persona` | free text or constants | BR-07, R2 |
| Events | generic `Event`; facts end up in `summary` | union of 6 typed events | BR-05, BR-06 |
| Contract history | one `Employment` at hire | `contract_change` events replayed on hire facts | BR-05 (`contract_change`) |
| Documents | stored, `event_id` and `text` required | derived by `plan()`, payslips monthly without an event | BR-08 |
| Document types | `performance_review`, `salary_change_letter`, `resignation_letter`, … | AMEXIO's 5 + 4 proposed | BR-04 |
| IDs | assigned by `next_id`; patterns not checked on load | only the employee number | BR-02, BR-03, decision D4 |
| Amounts, enums | `Money`; free strings | whole euros; closed lists (`"Permanent"`) | BR-04, R2 |
| Reference dossier 100101 | Engineering, EUR 3850, Dirk Bakker, invented documents | IT, EUR 4350, M. Bakker, rebuilt from AMEXIO's files | BR-00, BR-09 |

## Decisions to confirm first (BR-01)

Each one goes in the Decision Log with the reason. The recommendation is
the starting point, not a given.

| # | Question | Recommendation | Why |
|---|---|---|---|
| D1 | What is the reference dossier 100101? | **Decided 24 Oct:** only AMEXIO's 100101, value by value from the PDFs and `import.xml`; the hand-written story (salary change, resignation) is dropped, no second dossier | The generator's golden test already reproduces AMEXIO's files; a reference that disagrees with the client's data is not a reference. Rejected: keeping the hand-written story as a second "edge-case" dossier. Consequence: `contract_change` and `termination` are covered by unit tests (BR-05, BR-06) and by Robin's fixtures (R3), not by the golden snapshot |
| D2 | Which event types? | **Decided 24 Oct:** the generator's six (`contract_change`, `training`, `appraisal`, `medical_check`, `absence`, `termination`) plus `hire`; `hire` carries no employment facts (they stay in `Employment`, and `hire.date` must equal `Employment.start_date`) | The generator already produces these, so its full-history cases load without being refused, and the adapter only renames fields. `hire` holds the contract's signatories and anchors the timeline. Rejected: only the four types behind AMEXIO's documents (the bridge breaks on legitimate data, and a salary change has nowhere to live); own names (a translation layer that can go wrong) |
| D3a | Must every document point at an event? | **Decided 24 Oct:** yes, except recurring types (`payslip`, `annual_income_statement`), where `event_id` may be empty; a contract without its event is still refused | A recurring document records no single happening; a payroll event per month would hold no fact but a date already on the document. Rejected: a `payroll` event per payslip (empty events, an eighth type against D2); optional for all types (loses a check that works today); payslip pointing at the event that set its salary (gives `event_id` two meanings — reconsider as a separate field in M05) |
| D3b | Is the document text stored in the case? | **Decided 24 Oct:** one copy of each fact. `text` becomes optional; the text is a derived product, generated from the facts when needed | A fact stored twice (in `Employment` and inside the text) diverges after the first correction, and no test compares text with facts: the case would be wrong with every test green. Rejected: required `text` (the generator would copy rendered text into the case); removing `text` now (that choice belongs to M04, where templates and placeholders are designed) |
| D4 | Who assigns IDs to the generator's data? | **Decided 24 Oct:** the case model. The generator sends the LLM's JSON without IDs (`{"employees":[…]}`, then `{"storylines":[…]}`); no case exists before: the employees JSON creates the cases, one per employee, and the case model assigns every ID (employee numbers included, unique across the batch), normalizes the values and returns the corrections. A reference to an ID that already exists (a storyline's `employeeId`) is allowed and checked; an object's own ID is never accepted from outside | Keeps AX-012 absolute: one place creates IDs. Rejected: IDs assigned by the generator adapter and only checked on load (two ID authorities). Consequence: the demo must reach the Python case model at run time (D8) |
| D5 | Document types | Closed list of 9: AMEXIO's 5 plus the 4 proposed, the 4 marked "proposed" until AMEXIO confirms | The generator can already produce them; refusing them would block its fixtures |
| D6 | JSON field names | Keep snake_case; the adapter maps from camelCase | Python owns the contract; renaming would break v1 files and the golden test |
| D7 | Training provider and medical examiner | Provider = `Organisation` (`kind="training_provider"`); examiner = `Persona` (`role="examiner"`) linked to an `Organisation` (`kind="occupational_health"`) | Both are printed on AMEXIO's documents, so they are facts; check the exact wording in BR-00 |
| D8 | How does the browser demo reach the Python case model? | **Open.** Step 1: file exchange — the demo exports the LLM JSON, a case model command turns it into a case, the demo loads the case back; CI runs the same path on fixtures. Step 2: Pyodide — the case model runs inside the demo | Step 1 needs no infrastructure and unblocks this week; Pyodide is the only option that also works on the hosted page with one implementation. Alternatives: a local Python API (does not work on the hosted page); porting the case model to TypeScript (two copies of the rules) |
| D9 | Who owns normalization and the seeded plot (who leaves, sick-leave periods, appraisal years)? | **Open, to agree with Robin and Mike.** Case model: IDs, normalization against the format rules, corrections log, storing the plot's results as facts. Generator: drawing the plot from the seed and writing the prompts | Normalization is about facts (the case model's job); drawing a plot is generation (Daniel and Robin's job) |

## Target shape (v1.1)

Only what changes. Everything else stays as in v1 (see `case_model/README.md`).

**Closed value sets** (BR-04)

| Field | Values |
|---|---|
| `Employment.contract_type`, `contract_change.new_contract_type` | `Permanent`, `Temporary` |
| `Document.type`, `metadata.document_type` | `employment_contract`, `payslip`, `medical_check`, `performance_appraisal`, `training_certificate` + proposed `contract_amendment`, `annual_income_statement`, `absence_report`, `termination_letter` |
| `appraisal.rating` | `Below expectations`, `Meets expectations`, `Exceeds expectations` |
| `medical_check.result` | `Fit for work`, `Fit for work with adjustments` |
| `termination.reason` | `Resignation`, `End of temporary contract`, `Mutual agreement`, `Retirement` |
| `Persona.role` | `employee`, `manager`, `hr_officer`, `examiner` |

**Events** (BR-05). Every event keeps `id`, `type`, `date`, `participant_ids`;
`label` and `summary` become optional. Type-specific fields:

| `type` | Extra fields | Participants |
|---|---|---|
| `hire` | — (the facts are in `Employment`) | employee, HR officer |
| `contract_change` | `reason`, optional `new_salary` (Money), `new_position`, `new_contract_type`, `new_hours` | employee, HR officer |
| `training` | `course`, `duration_days`, `provider_id` (Organisation) | employee |
| `appraisal` | `year`, `rating`, optional `comment` | employee, manager |
| `medical_check` | `result` | employee, examiner |
| `absence` | optional `end_date` | employee |
| `termination` | `reason`, optional `notice_date` | employee, HR officer |

**Generator → case model mapping** (for Robin's adapter, R2)

| Generator | Case model v1.1 |
|---|---|
| `Employee.id` | `case_number`, `dossier.employee_number`, `metadata.employee_id` |
| `firstName` + `lastName` | `Persona(role="employee").name` |
| `department`, `position`, `hireDate`, `contractType`, `hoursPerWeek` | `Employment.department`, `position`, `start_date`, `contract_type`, `hours` |
| `startSalary` (4350) | `Employment.salary` = `{"amount": "4350.00", "currency": "EUR"}` |
| `managerId` / `managerName` | `Persona(role="manager")` in this case, put in each `appraisal`'s participants |
| company profile | `Organisation(kind="employer")` |
| `CareerEvent` | `Event` with the same type; camelCase fields → snake_case; `appraisal` gets `date` = the appraisal document's date |
| `DocumentInstance` | `Document` with `type`, `event_id` (empty for payslips), metadata; `text` optional |
| `DossierSet` | one case folder per employee |

**Rules the schema cannot carry.** The JSON Schema gives the generator the
shape only. These hold only through `load_case`, which is why the CI test
(BR-11) matters: references point at existing parts, ID patterns (AX-011b),
`hire.date` = `Employment.start_date`, one `hire` per case, nothing after
`termination`, `absence.end_date` ≥ `date`, `metadata.employee_id` =
`dossier.employee_number`, `metadata.document_type` = `Document.type`.

## Microphases

Each one: one change, one output, one pass/fail check. G = Giulia, R = Robin.

| ID | Build | Verify | Who | Needs |
|---|---|---|---|---|
| BR-00 | Fact sheet of AMEXIO's 100101: every value printed in the 5 PDFs and in `import.xml`, with its source and where it lives in the case (a field, or the rule that computes it) | Every row names a file and a case field or rule; nothing is copied from the generator's preset | G | — |
| BR-01 | Decisions D1–D7 confirmed and written in the Decision Log | Each decision has a reason and an alternative that was rejected | G | BR-00 |
| BR-02 | = AX-011a: strict ID and employee-number regexes | `"P001\n"`, `"100101\n"`, `"P٠٠١"` fail | G | — |
| BR-03 | = AX-011b: `Case` checks every ID's pattern | A loaded case with persona id `"banana"` fails | G | BR-02 |
| BR-04 | Closed value sets (table above) | `"permanent"` and `"performance_review"` fail; `"Permanent"` passes | G | BR-01 |
| BR-05 | Typed events: discriminated union on `type` | An appraisal without `rating` fails; an unknown type fails; save/load keeps the type-specific fields | G | BR-04 |
| BR-06 | Event coherence rules (list above) | One deliberate break per rule fails with a clear message | G | BR-05 |
| BR-07 | Manager, examiner, training provider as parts of the case | A training whose `provider_id` is unknown fails | G | BR-05 |
| BR-08 | Documents v1.1: optional `event_id` for recurring types only, optional `text`, metadata consistency | A contract without an event fails; a payslip without one passes; mismatched `employee_id` fails | G | BR-04 |
| BR-09 | Reference dossier 100101 rebuilt from BR-00, with AMEXIO's 5 documents; golden snapshot regenerated | Golden test green; every value traces to a BR-00 row | G | BR-00, BR-05–08 |
| BR-10 | JSON Schema of `Case` exported and committed (`case_model/schema/case.schema.json`) with the command that makes it | The golden case validates against the schema | G | BR-09 |
| BR-11 | Fixtures folder `case_model/fixtures/generator/` and a test that runs `load_case` on every subfolder | A deliberately broken fixture makes the test fail | G | BR-10 |
| BR-12 | Module contract updated to version 1.1 (README), change list v1 → v1.1, tag `v1.1` | Every change in the list has its test | G | BR-11 |
| BR-13 | Handover note to Robin: schema, mapping table, file layout, rules outside the schema | Robin confirms he can start R1–R3 without questions | G | BR-12 |
| R1 | TypeScript types generated from the schema (npm script); own fact types replaced where they leave the generator | `npm run build` passes with the generated types | R | BR-10 |
| R2 | Adapter `DossierSet` → one case folder per employee, written next to `generation.json` | Every exported folder loads with `load_case` | R | R1 |
| R3 | 2–3 fixtures in `case_model/fixtures/generator/`: 100101 from the AMEXIO preset, one leaver, one temporary → permanent | BR-11 test green on them | R | R2 |
| R4 | List of facts printed on documents that the formats doc does not name | List sent; each item becomes a field or an explicit "derived" | R | — |
| R6 | Reader: the demo loads a case folder (upload, plus the reference 100101 bundled) and passes it to its document plans, PDF and XML export | The reference case renders in the demo with no error | R | R1 |
| R5 | Insurance demo (`demo's/first_pregenerated_example_demo`, CLM-10045) removed or marked legacy | No insurance data left under the HR scope | R | — |
| BR-14 | Read test: the demo renders the reference case 100101 and the output equals AMEXIO's 5 PDFs and `import.xml` entries (Robin's golden comparison, with the case as input instead of his preset) | Identical output; removing a fact from the case (e.g. the examiner) makes it fail | G + R | BR-09, R6 |
| BR-15 | Write test: generator's 100101 written as a case vs reference 100101, comparing facts (not IDs, not text) | Same facts; a changed salary in either makes it fail | G + R | BR-09, R3 |

**Gate M03b:** BR-11, BR-14 and BR-15 green on `main`, tag `v1.1`, Demo-Generator
merged through a pull request with the vitest job next to pytest in CI.

## Calendar

Lecture slots and Sundays are left out.

| When | What |
|---|---|
| Sat 24 Oct (afternoon) | BR-00, BR-01; presentation draft |
| Mon 26 Oct (afternoon) | Presentation; BR-02, BR-03 |
| Tue 27 Oct (morning) | BR-04, BR-05 |
| Wed 28 Oct | BR-06, BR-07, BR-08; **draft schema to Robin at end of day**, so R1 can start |
| Thu 29 Oct (afternoon) | BR-09, BR-10 |
| Fri 30 Oct (morning) | BR-11, BR-12, BR-13 — handover |
| Week of 2 Nov | R1, R6 then R2–R3 (Robin); BR-14 and BR-15 together; merge; then M04 |

## Risks

- **M04 starts about a week late.** Sprint 3 already holds M04–M08 before
  Review 2 (~13 Nov). Typed events are a prerequisite for M04's placeholders
  (`{{employee.name}}` needs fields to point at), so the time is not lost, but
  M07–M08 may need to move to Sprint 4. Discuss at the weekly meeting.
- **BR-00 may contradict the generator's preset.** Then D1 still holds: the PDFs
  win, and Robin's preset is corrected too.
- **The schema drifts from the code.** Until the deferred CI check exists,
  BR-10's command is rerun by hand at every model change.
- **Overlapping roles.** The generator's validator (Valentin's area) and
  PDF/XML export (Stylianos' area) are not decided here; they go to the weekly
  meeting.

## Deferred

Pyodide (the real case model in the browser); CI check that the committed
schema is up to date; the 4 proposed document types becoming final (needs
AMEXIO).
