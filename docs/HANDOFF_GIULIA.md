# Reply to the handover — the demo on case model v1.1

From Robin, 24 October 2026. Branch `Demo-Generator`. Answers
[HANDOFF_ROBIN.md](HANDOFF_ROBIN.md) and your message of today.

## In one paragraph

The demo now writes every run as case folders in your format and makes every
PDF and `import.xml` entry from those folders, after a real write and read.
`toCase.ts` builds the cases the way `ingest.py` does, so both paths end in the
same files: for all three committed scenarios, `ingest` on the run's input
gives exactly the demo's cases (documents aside), and AMEXIO's 100101 comes out
byte for byte as `reference_dossier.golden.json`. The reference case renders as
AMEXIO's five PDFs and `import.xml` entries (BR-14).

## Status

| # | Status | Where, and the proof |
|---|---|---|
| R1 | Done | `npm run types` writes `src/case/generated/` from `case_model/schema/` (json-schema-to-typescript). `npm run build` passes; a test fails when the types are out of date. |
| Bridge | Done | `src/case/toCase.ts`: a `hire` event (EVT-001), snake_case, `Money` with cents, appraisals on 30 June, `event_id` from the document's source event, IDs in date order. The ZIP has `cases/<number>/` with the four files. |
| R6 | Done | `src/case/fromCase.ts`. Configure → *Reference case 100101* (bundled), *Open case folder…* (for example an `ingest --out` folder) or *Open exported ZIP…*. The reference renders 5 documents, 0 validation errors. |
| R2 | Done, one difference | The ZIP has `cases/employees.json` and `cases/storylines.json`. They hold the run **after** the demo's checks, not the raw model answer (why: below). Both load with the command. |
| R3 | Done | `fixtures/generator/demo_small_company` (a temporary contract made permanent, two leavers, promotions) and `demo_leavers` (three leavers, two at the end of a temporary contract, sick leave). `test_fixtures.py` picks them up. |
| CI | Done | `case_model/test_demo_cases.py` on `fixtures/demo_cases/` (3 scenarios, 18 cases), a `vitest` job in `.github/workflows/tests.yml`. |
| R4 | Below | |
| R5 | Done | `demo's/` (CLM-10045) removed. |
| BR-14 | Green locally | `tests/golden.test.ts`. Needs AMEXIO's mock package, which is not in git, so CI skips it. Removing the examiner from the case makes it fail. |
| BR-15 | Green | `test_demo_100101_holds_the_reference_facts`; a changed salary fails it. |

What `test_demo_cases.py` proves:

- every demo case loads with `load_case`, and `save_case` writes the same bytes back;
- `ingest` on the same run gives the same cases, documents aside;
- every case in `fixtures/broken_demo_cases.json` is refused (12 broken copies of
  100101: an ID in the wrong shape, an appraisal without a rating, an event
  before the hire, a contract document without an event, …). The demo's own
  pre-check (`src/case/checkCase.ts`) is tested on the same list, so the two
  stay in step.

## The defaults

1. **9 document types** (AMEXIO's 5 + my 4 proposed): agreed.
2. **camelCase in, snake_case in the case**: agreed.
3. **Provider = organisation, examiner = persona**: agreed.
4. **Files now, Pyodide later**: agreed for now, with one caveat. Pyodide cannot run in the hosted demo page: the page may not fetch the Python runtime or pydantic from other sites. It would work in the local version only. Since the final hub has a backend, I would run the case model there rather than in the browser. Until then, `checkCase.ts` checks cases in the browser and CI keeps it in step with `load_case`.
5. **The plot stays in the generator** (who leaves, sick leave, appraisal years, medical checks): agreed.

On D3a (payslips and annual statements without an event): agreed, and the demo follows it. A payslip records a month, not a change; the salary it prints is the employment plus the `contract_change` events in force. If we want that link later, a separate field in M05, as you wrote, rather than a second meaning for `event_id`.

## What I changed in the demo to match the case

- **Manager name.** A manager who is also an employee is now printed with their full name ("Pieter Smit"), not "P. Smit (fictional)", so the case holds the name `ingest` writes. AMEXIO's example is unchanged ("M. Bakker (fictional)" is free text).
- **Training certificate title.** "Training Certificate Health & Safety" is now a template rule, as in your README, instead of a special case in my AMEXIO preset.
- **No department manager.** The demo lets the director sign. The R2 input writes `managerName` = the director for those employees, so `ingest` makes the same P002.
- **Personas and storylines are read-only**, and documents, validation and export read the cases. Validation has a new first check: *Every dossier is a valid case*.
- `generation.json` keeps its shape.

## Differences between ingest and toCase

1. **Documents.** `ingest` writes `documents: {}`; `toCase` writes one document per PDF (type, `event_id`, participants, metadata). When a case has no documents, the demo's templates decide which exist (as for the reference case); when it has documents, the case decides.
2. **An appraisal signed by someone other than P002.** When the department manager was not employed on 30 June (hired later, or left), the demo has the director sign, and `toCase` adds the director as a second manager persona (P004). `ingest` cannot express this: it always uses P002. It does not occur in the fixtures. **Question:** fine as is, or should the storyline input get a way to say who signs?
3. **Raw model answers in R2.** They would not give the same cases: the demo numbers employees by hire date, fixes values `ingest` refuses (a position outside the list, a salary outside the range), and adds the medical checks and appraisal years. So R2 writes the checked facts, which `ingest` turns into exactly the demo's cases. The raw answers stay visible in the app; I can add them to the ZIP if you want them.
4. **Names.** A case holds one name; the reader splits it at the first space for display only. Printed names are unchanged.
5. **Run settings are not facts.** Period (as-of date), document types, one-per-type or full history, version control, Dutch titles, `create`/`sync` and the update node come from the run configuration, not from the case. BR-14 renders the reference case with AMEXIO's example settings.

## R4 — printed values the case does not hold

Everything else a document prints is a stored fact. "Rule" means derived when the document is written (D3b); each rule is in `src/spec/rules.ts` or in the field's `rule` text in `src/spec/doctypes/`, and in `format-spec.json`.

| Document | Printed value | Now | Proposal |
|---|---|---|---|
| All | Banner, footer | Constant (target profile) | Run configuration (M04) |
| All | Title, description, file name | Template | Rule, per document type |
| All | Department in the header | `employments[0].department` | Stored; note it never changes after hire |
| Folder | Description "Personnel file of {name}, {position} ({department})" | Rule: latest position | Keep derived, `dossier.description` stays null |
| Payslip | Period, payment date (the 25th) | Rule | Rule |
| Payslip | Gross | Rule: employment + contract changes in force | Rule |
| Payslip | Wage tax (37%, half to even), net | Rule | Rule; the 37% belongs in the run configuration |
| Medical check | Next check (+2 years) | Rule | Rule; the interval in the run configuration |
| Appraisal | Review period (1 January–30 June, or from the start date) | Rule | Rule |
| Appraisal | Review date | Stored: the event's date (30 June) | — |
| Training certificate | Title "…Health & Safety" | Rule (course) | Rule |
| Contract amendment | Position, contract type, hours, salary after the change | Rule: the event stores only what changed | Rule |
| Annual income statement | Months paid, totals | Rule: sum of the year's payslips | Rule |
| Annual income statement | Issue date (31 January) | Rule | Rule |
| Absence report | "Sick leave" | Constant | Named constant: an absence event is sick leave by definition |
| Absence report | "Not yet returned" | Rule: `end_date` is null | Rule |
| Termination letter | Date of notice | Stored when given, else one month before the last day | Rule for the default |
| Termination letter | Final payslip month | Rule: month of the last day | Rule |
| import.xml | createdby, owner, mime, category, ACL, version control, action, language titles | Target profile and run settings | Run configuration |

Tags and confidentiality are now stored per document (`documents[].metadata`), from the document type specs, which match AMEXIO's `import.xml`. Your README says document metadata comes after BR-00: **question:** keep it in the demo's cases until then, or leave `documents` empty?

## Try it

```bash
python -m pytest -v                                   # includes test_demo_cases.py
cd generator/demo_dossier_generator
npm ci && npm test                                    # the TypeScript side
npm run example                                       # out/mock-import-dossier/ with cases/
python -m case_model.ingest out/mock-import-dossier/cases/employees.json \
    out/mock-import-dossier/cases/storylines.json --out /tmp/cases   # same cases, no documents
```

After a change to the case model: `npm run types` (schemas and reference case)
and `npm run fixtures` (demo cases); CI fails until both are committed.
