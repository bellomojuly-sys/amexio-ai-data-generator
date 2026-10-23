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
Configure ──> Personas ──> Storylines ──> Documents ──> Validate ──> Export
              (model)      (model)        (code)        (code)       (code)
```

1. **Configure**: company, period, departments, document types, scenario mix (leavers, temporary contracts, part time, sick leave), history length.
2. **Personas**: the model returns employees as JSON. `generate/normalize.ts` fixes anything outside the allowed lists and records each correction. Code assigns personnel numbers, links managers, and picks who leaves.
3. **Storylines**: per employee, the model writes contract changes, trainings, sick leave, appraisal ratings and comments, and leaving. Code schedules medical checks, enforces dates and ranges, and fills gaps.
4. **Documents**: every document type's `plan()` turns the facts into documents (monthly payslips, yearly appraisals and so on).
5. **Validate**: 14 deterministic checks (`validate/validate.ts`). Use "Try to break it" to plant typical model mistakes and watch them get caught.
6. **Export**: a ZIP with `import.xml`, `files/*.pdf`, `README.md` and `generation.json` (the facts every document was made from).

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
