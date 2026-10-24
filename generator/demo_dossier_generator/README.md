# AMEXIO Dossier Generator (demo)

An interactive demo that generates **synthetic HR dossiers** in the format of AMEXIO's mock import package: one folder per employee, PDFs with AMEXIO's "MOCK DATA" layout, and an `import.xml` for OpenText Object Importer.

The model proposes the people and their careers. Code assigns IDs, checks every value, computes every amount and date, and writes the PDFs and the XML. A validator checks all documents against each other and blocks the export on any error.

**Golden test:** given AMEXIO's four example employees, the generator rebuilds AMEXIO's `import.xml` (identical elements, attributes and text) and all 20 PDFs (identical text and layout).

## Run it

```bash
npm install
npm run dev          # the app on http://localhost:5173
npm test             # golden test, generation, validation, fake-model tests
npm run example      # AMEXIO's example package -> out/mock-import-dossier/
npm run example -- --offline 40 --years 5   # 40 employees, No AI -> out/hr-dossier-import/
npm run types        # regenerate src/case/generated/ from case_model/schema/ (after a case model change)
npm run fixtures     # regenerate case_model/fixtures/demo_cases/ and fixtures/generator/demo_*
```

The golden test needs AMEXIO's mock package, which is kept out of git. Put it in `generator/generated_mock_data/mock_import_dossier/` (git-ignored), or point `AMEXIO_MOCK_DIR` at it. Without it, that test is skipped and the other tests still run.

`npm run build:artifact` makes the single-file page for the hosted Claude demo (`dist-artifact/dossier-generator.html`).

## Choosing the model

| Where | Default | Who pays |
| --- | --- | --- |
| Hosted Claude page | Claude, through the page's own Claude access | The person using the page: it runs on **their** Claude account and limits. It cannot use anyone else's account and cannot reach other AI services. |
| Local (`npm run dev`) | "No AI", unless `.env.local` says otherwise | Whoever owns the key you enter |

Locally, pick any model in **Model settings** (top right), or set a default in `.env.local` (see `.env.example`):

- **Anthropic API**: your key and model name.
- **OpenAI-compatible**: OpenAI, Google Gemini, Groq, OpenRouter, or a **free local model** with Ollama or LM Studio.
- **No AI**: the built-in sample generator. Free, instant, reproducible from the seed.

Team-wide defaults live in `src/config/model.ts`. Keys never go in source files; `npm run build:artifact` blanks them, and the build stops if a key-like string ends up in the bundle.

## How it works

```
Configure ──> Personas ──> Storylines ──> cases/ ──> Documents ──> Validate ──> Export
              (model)      (model)        (code)     (code)        (code)       (code)
```

1. **Configure**: company, period, departments, document types, scenario mix (leavers, temporary contracts, part time, sick leave), history length.
2. **Personas**: the model returns employees as JSON. `generate/normalize.ts` fixes anything outside the allowed lists and records each correction. Code assigns personnel numbers, links managers, and picks who leaves.
3. **Storylines**: per employee, the model writes contract changes, trainings, sick leave, appraisal ratings and comments, and leaving. Code schedules medical checks, enforces dates and ranges, and fills gaps.
4. **Cases**: the run is written as one case folder per employee in the case model's format (`case_model/`, v1.1) and read back. See below.
5. **Documents**: every document type's `plan()` turns the facts read from the cases into documents (monthly payslips, yearly appraisals and so on). Personas and storylines are read-only: the facts are the cases.
6. **Validate**: 15 deterministic checks (`validate/validate.ts`), the first being the case model's own rules. Use "Try to break it" to plant typical model mistakes and watch them get caught.
7. **Export**: a ZIP with `import.xml`, `files/*.pdf`, `README.md`, `generation.json` (the run) and `cases/` (the case folders the documents were made from).

## The case model (the bridge)

The case model in `case_model/` holds the facts of one dossier. The demo writes its runs in that format and makes every document from it (`src/case/`):

| File | What it does |
| --- | --- |
| `generated/` | TypeScript types from `case_model/schema/*.json`, and a copy of the reference case 100101. Made by `npm run types`; a test fails when they are out of date. |
| `toCase.ts` | A run becomes one case per employee, built as `case_model/ingest.py` builds it: P001 employee, P002 manager, P003 examiner; ORG-01 employer, ORG-02 training provider, ORG-03 occupational health; EVT-001 the hire, then the events in date order; DOC-001... the documents in date order, each with the event it records. snake_case names, `{amount: "4350.00", currency: "EUR"}`, appraisals on 30 June. |
| `caseJson.ts` | The four files of `save_case` (`case.json`, `cast.json`, `storyline.json`, `documents.json`), byte for byte, and reading them back. |
| `checkCase.ts` | The rules `load_case` applies, in TypeScript, so the browser can check a case. Python stays the authority (CI). |
| `fromCase.ts` | The reader: cases back into what `plan()`, the PDFs and `import.xml` read. When a case lists its documents, the case decides which exist. |
| `bridge.ts` | The route: run → case folders → read back → documents. Also writes the run as `employees.json` / `storylines.json` for `python -m case_model.ingest`. |

In the app, **Configure** can also open cases instead of generating: the bundled reference case 100101, a folder of case folders (for example from `python -m case_model.ingest ... --out DIR`), or a ZIP this demo exported.

Tests on both sides keep the format shared: `tests/case.test.ts` here, and `case_model/test_demo_cases.py`, which loads the committed demo cases with `load_case`, checks that `ingest` gives the same cases from the same run, and refuses every case in `case_model/fixtures/broken_demo_cases.json` (the demo's `checkCase` is tested on the same list). With AMEXIO's mock package present, `tests/golden.test.ts` also renders the reference case and compares it with AMEXIO's five PDFs and `import.xml` entries (BR-14).

## The format as TypeScript

Each document type is one file in `src/spec/doctypes/`: fields, labels, formats, where each value comes from, tags, confidentiality, access rights, when it occurs, and its cross-document rules.

| File | Document Type | In AMEXIO's example |
| --- | --- | --- |
| `employmentContract.ts` | Employment Contract | yes |
| `payslip.ts` | Payslip | yes |
| `medicalCheck.ts` | Medical Check | yes |
| `performanceAppraisal.ts` | Performance Appraisal | yes |
| `trainingCertificate.ts` | Training Certificate | yes |
| `contractAmendment.ts` | Contract Amendment | proposed |
| `annualIncomeStatement.ts` | Annual Income Statement | proposed |
| `absenceReport.ts` | Absence Report | proposed |
| `terminationLetter.ts` | Termination Letter | proposed |

To add a document type: copy one of these files, change it, and register it in `src/spec/doctypes/index.ts`. The PDF renderer, XML exporter, validator, UI and `format-spec.json` pick it up automatically.

Other places worth knowing:

- `src/spec/target.ts`: Content Server names (category, attributes, users, groups). These must already exist in the target system.
- `src/spec/rules.ts`: business rules found in the example (pay day, 37% wage tax rounded half to even, 2-year medical interval).
- `src/spec/format.ts`: output formats (DD-MM-YYYY in PDFs, YYYYMMDD in XML, `EUR 4.350` vs `EUR 4350`).
- `src/ai/prompts.ts`: the prompts. `src/ai/providers.ts`: the model connectors.
- `src/export/pdf.ts`: the PDF layout, measured from AMEXIO's files.

## Open questions and assumptions

The running list of constraints, assumptions and questions for AMEXIO (XSD, vocabularies, file names, access rights, model access...) is kept in the team's analysis doc: https://claude.ai/artifact/9xRkoDtVdtj6NnZAyMeAzF ("Generator notes" tab).
