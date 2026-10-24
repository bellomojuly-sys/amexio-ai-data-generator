# Handover to Robin — case model v1.1 and the generator

From Giulia, 24 October 2026. Branch `case-model-v1.1`. Plan, decisions and
calendar: [ROADMAP_BRIDGE.md](ROADMAP_BRIDGE.md). Module contract:
[case_model/README.md](../case_model/README.md).

## The idea in one paragraph

The case model is the single place where the facts live, so the generator's
data passes through it. Your demo already asks the LLM for two JSON objects
(`personasPrompt`, `storylinePrompt` in `src/ai/prompts.ts`). Those objects now
go **unchanged** into the case model, which creates one case per employee,
assigns every ID, normalizes the values and records the corrections. Your demo
then reads the cases back and renders PDFs and `import.xml` from them. Your
own `normalize.ts` / ID assignment becomes unnecessary for the facts.

```
LLM ─▶ employees.json ─▶ case model (cases + IDs + corrections)
                              │
     your plan step (who leaves, sick-leave periods, appraisal years, medical checks)
                              │
LLM ─▶ storylines.json ─▶ case model (typed events + IDs + rules)
                              │
                              ▼
               case folders ─▶ your demo ─▶ PDF + import.xml
```

## What is ready for you

| What | Where |
|---|---|
| Input schema, step 1 | `case_model/schema/input.employees.schema.json` |
| Input schema, step 2 | `case_model/schema/input.storylines.schema.json` |
| Case schema (what you read back) | `case_model/schema/case.schema.json` |
| Command | `python -m case_model.ingest employees.json storylines.json --out DIR` |
| Example input (AMEXIO's 4 employees) | `case_model/fixtures/generator/amexio_example/` |
| Example input (leaver, temporary → permanent, messy values) | `case_model/fixtures/generator/leaver_example/` |
| Reference case 100101 (golden) | `case_model/reference_dossier.golden.json` |

Try it:

```bash
pip install -r requirements.txt
python -m case_model.ingest case_model/fixtures/generator/amexio_example/employees.json \
    case_model/fixtures/generator/amexio_example/storylines.json --out /tmp/cases
```

## The input — what you send

**Step 1, `employees.json`.** Exactly your personas JSON, plus a `company`
object (your `CompanyProfile`, same names):

```json
{"company": {"employerName": "Acme Logistics B.V. (fictional)",
             "trainingProvider": "Training Academy (fictional)",
             "examiner": "Occupational physician (fictional)",
             "absenceService": "Occupational health service (fictional)",
             "directorName": "H. de Wit (fictional)"},
 "employees": [{"firstName": "Jan", "lastName": "de Vries", "department": "IT",
                "position": "Software Developer", "isManager": false,
                "hireDate": "2021-03-01", "contractType": "Permanent",
                "hoursPerWeek": 40, "startSalary": 4350,
                "managerName": "M. Bakker (fictional)"}]}
```

- **No `id`, no fields the shape does not name** (`leaves`, `managerId`, …):
  both are refused. Send the LLM's answer, not your normalized `Employee`.
- `managerName` is optional; without it, a department's manager is the
  employee marked `isManager` there, and managers report to `directorName`.
- **Employee numbers:** the employee at position *i* in the list gets
  `100101 + i` (or `--first-number + i`). Use the same numbers in step 2.

**Step 2, `storylines.json`.** Exactly your storyline JSON:
`{"storylines": [{"employeeId": "100101", "events": [...], "appraisals": [...]}]}`
with the event shapes of your prompt (`contract_change`, `training`,
`absence` with `startDate`/`endDate`, `termination`). Also accepted in
`events`: `{"type": "medical_check", "date", "result"}` (your rules add these)
and `{"type": "appraisal", "year", "rating", "comment"?, "date"?}`. An appraisal
without a date is dated 30 June of its year, as in your `eventDate`.

**Normalization.** A value only written differently from the closed list
(`"permanent"`, `"meets expectations"`, extra spaces in a name) is corrected
and listed in `corrections.json` (`step`, `employee_id`, `message` — same idea
as your `Correction`). A value that cannot be placed (`"Freelance"`) is
refused: the case model does not invent facts.

## The output — what you read back

One folder per employee: `DIR/100101/case.json`, `cast.json`,
`storyline.json`, `documents.json`, plus `DIR/corrections.json`. Joined, the
four files are one object of `case.schema.json` (see `save_case` in
`case_model/storage.py`). Names are snake_case. Amounts are
`{"amount": "4350.00", "currency": "EUR"}` (the amount is a string).

Mapping to your objects, for the reader (R6):

| Your object | In the case |
|---|---|
| `Employee.id` | `case_number`, `dossier.employee_number` |
| `firstName` + `lastName` | the persona with `role: "employee"` |
| `department`, `position`, `hireDate`, `contractType`, `hoursPerWeek`, `startSalary` | `employments[0]`: `department`, `position`, `start_date`, `contract_type`, `hours`, `salary.amount` |
| `managerName` / manager | the persona with `role: "manager"` |
| `company.trainingProvider` | organisation `kind: "training_provider"` (`training.provider_id` points at it) |
| `company.examiner` | persona `role: "examiner"`, in each `medical_check`'s participants |
| `CareerEvent` | `events`, same `type`; fields in snake_case; `absence.startDate` → `date`; plus a `hire` event |

## Rules the schema does not carry

They hold only through `load_case`/ingest, so please run the command (or the
tests) on what you produce: references point at existing parts; IDs follow
`P001`, `ORG-01`, `EVT-001`, `DOC-001`; at most one `hire`, on the employment's
start date; nothing before the hire or after the `termination`; an absence
does not end before it starts; a document other than a payslip or annual
income statement needs an event.

## Defaults I took to hand over today — please confirm or push back

1. Document types: AMEXIO's 5 plus your 4 proposed (marked "proposed").
2. Input keeps your camelCase; the case uses snake_case.
3. Training provider = organisation; examiner = persona.
4. For now we exchange files; later the case model can run in the demo through Pyodide.
5. Drawing the plot from the seed (who leaves, sick leave, appraisal years,
   medical checks) stays in your generator; the case model stores the results.

## Your part

| # | Task | Done when |
|---|---|---|
| R1 | TypeScript types from the three schemas (e.g. `json-schema-to-typescript`, npm script) | `npm run build` passes with the generated types |
| R2 | The demo saves `employees.json` (with `company`) and `storylines.json` as above, for every run | Both files load with the command |
| R6 | Reader: load a case folder (upload, plus the reference 100101 bundled) and feed it to your `plan()`, PDF and XML export | The reference case renders in the demo |
| R3 | 2–3 more input fixtures from offline runs in `case_model/fixtures/generator/<name>/` | `python3 -m pytest case_model/test_fixtures.py` green |
| R4 | List of facts printed on documents that the case does not hold yet | Each becomes a field or a named rule |
| R5 | Insurance demo (`demo's/first_pregenerated_example_demo`, CLM-10045) removed or marked legacy | No insurance data under the HR scope |

**Then together:** BR-14 — your demo renders the reference case 100101 and the
output equals AMEXIO's 5 PDFs and `import.xml` entries (your golden test, with
the case as input instead of your preset).

## Known open points

- The reference values come from your AMEXIO preset; I still check each one
  against AMEXIO's PDFs (BR-00). If they differ, the PDFs win, for both of us.
- The case holds no documents yet: document metadata (tags, confidentiality,
  dates) comes after BR-00. Until then your doctype specs provide it.
