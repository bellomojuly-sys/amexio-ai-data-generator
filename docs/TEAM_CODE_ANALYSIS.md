# What the team has built, and how the backend reuses it

17 November 2026 · Giulia (backend, case model). Purpose: before the backend
moves to pipeline contract v1.1 and gets a database, list what already exists,
check it can be merged, and decide what the backend reuses instead of rebuilding.

## 1. Branches of the team repo

Checked on 17 Nov against `main` (`6710d9f`).

| Branch | Owner | What | State |
|---|---|---|---|
| `main` | all | Case model v1.1, Robin's generator demo, backend B1 (stub chain, contract v1.1 doc) | 168 pytest + 60 vitest green |
| `Demo-Generator` | Robin | Three-part LLM design (PDF, 3 Nov), `docs/backend_b1/` (B1 proposal, payload example, his review, **Python LLM client draft** `llm_client_interface.py`) | **Merged** into `claude/cool-johnson-swdlj0`, no conflict |
| `MockToTemplate` | Daniel | **PDF Template Studio** (`pdf_template_studio/`, Streamlit + PyMuPDF + OpenAI): mock PDFs → templates with `{{PLACEHOLDER}}` | **Merged**; its commit deleted the root `requirements.txt`, which was kept. Its script `test_wizard.py` passes; it runs in its own CI job |
| `giulia/backend-b1`, `be-02-pipeline-contract` | Giulia | BE-01 Decision Log, contract v0.2 | Superseded: both files are on `main` in a newer version. Not merged |
| `docs/roadmap-backend-split` | Giulia | Old roadmap draft | Superseded by the roadmap in the personal repo. Not merged |
| `giulia/m07-domain-scenario-proposal` | Giulia | AX-036 proposal (domain vs scenario) | Part B; merge when M07 starts |
| other `claude/*`, `giulia/*`, `case-model-v1.1` | Giulia | Already in `main` | — |

No teammate branch is left unmerged. `bellomojuly-sys/dani-2.0-` is not part of
AMEXIO.

## 2. What exists for each step of contract v1.1

| # | Step (owner) | What exists | Where | Language | Matches v1.1? |
|---|---|---|---|---|---|
| 0 | Create analysis (Daniel) | Template Studio: upload, detect fields (rules or OpenAI), group by type, edit, export ZIP | `pdf_template_studio/app.py` | Python | Produces **templates**, not a `RunConfig`. Placeholder names are invented by the LLM → `docs/TEMPLATE_CONTRACT.md` |
| 1 | Personas (Robin) | `runPersonaStep`, `personasPrompt`, offline personas | `generator/…/src/generate/pipeline.ts`, `src/ai/prompts.ts`, `offline.ts` | TS | 0.2-era: the LLM still writes `hireDate`, `contractType`, `hoursPerWeek`, `startSalary`; `normalize.ts` corrects them in code |
| 2 | CM ID (Giulia) | `normalizePersonas` (closed lists, ranges, shares, managers, corrections) in TS; `ingest_employees` in Python | `src/generate/normalize.ts`; `case_model/ingest.py` | TS + Py | The **rules** v1.1 gives to CM ID already exist in `normalize.ts` |
| 3 | Plot (Giulia) | `planStoryline` decides who leaves, how many absences, which appraisal years | `src/generate/normalize.ts` | TS | Partly: no `PlotOutline` with slots yet |
| 4 | Event content (Robin) | `runStorylineStep`, `storylinePrompt` (LLM writes whole events with dates) | `pipeline.ts`, `prompts.ts` | TS | 0.2-era: dates come from the LLM, then `normalizeStoryline` fixes them |
| 5 | Dates & participants (Valentin) | `normalizeStoryline` + `toCase.ts` (participants, P001/P002/P003, ORG-01..03) | TS | — | Logic exists; not as Valentin's step |
| 6 | Document plan (Giulia) | Each document type's `plan()` | `src/spec/doctypes/*.ts` | TS | Yes in substance (which documents, when, values) |
| 7 | Document text (Robin) | Appraisal comments only | `prompts.ts` | TS | Partly |
| 8 | Fill (Valentin) | `get_fact` lookup (AX-022); PDF rendering fills values directly | `case_model/lookup.py`; `src/export/pdf.ts` | Py + TS | Lookup yes; placeholder fill no |
| — | Validation (Valentin) | 15 deterministic checks, the first being the case model's rules; "Try to break it" | `src/validate/validate.ts` | TS | Yes |
| 9 | Export (Stylianos) | AMEXIO-identical PDFs and `import.xml`, golden test | `src/export/` | TS | Yes |
| — | LLM client (Robin) | Providers: Anthropic, OpenAI-compatible, offline (TS); `complete_as` + `FakeLLM` draft (Py) | `src/ai/providers.ts`; `docs/backend_b1/llm_client_interface.py` | TS + Py | Py draft = contract §8 |
| — | Field catalogue | Nine document types × fields (`key`, `label`, `format`, `origin`, `rule`), tags, confidentiality, ACL, `format-spec.json` | `src/spec/` | TS | Reused by the template contract v0.2 |
| — | Storage, run ID, trace, monitoring | — | — | — | **Nothing exists**: this is new work |

Checked by running it (17 Nov): `npm run example -- --offline 10 --seed 7`
writes 10 case folders (395 documents, 0 validation errors), and **all 10 load
with the Python `load_case`**. Robin's output already speaks the case model.

## 3. Conclusions

1. **The generator works end to end today**, in TypeScript, and its output is
   valid case-model data. The Python backend has only stubs (`pipeline/chain.py`).
   Rewriting the generator in Python would redo Robin's work.
2. **Contract v1.1 is a design, not yet code.** Robin's three-part PDF (3 Nov)
   and the contract describe it; the code is still the 0.2-era two-part demo.
   The differences are in who decides a few facts (hire date, salary, contract
   type, durations), and `normalize.ts` already re-decides them in code.
3. **Storage, run tracking and monitoring do not exist anywhere.** That is
   where the backend adds value without overlapping anyone.
4. **Daniel's studio and Robin's spec use the same labels** (from AMEXIO's
   PDFs), so templates can be bound to the existing field catalogue instead of
   to new names.

## 4. Plan: what the backend does, in order

| Step | What | Reuses | New code |
|---|---|---|---|
| 1 | `case.db` + `rules.db` (SQLite, stdlib `sqlite3`), schema from `docs/DB_SCHEMA_CHANGES.md` and the monitoring dashboard | case model v1.1 (`Case`), `load_case` as the check | `pipeline/db/` |
| 2 | **Generator bridge:** the backend runs Robin's generator as a subprocess (`npm run example`, offline = no API key, like `FakeLLM`), reads the case folders with `load_case`, saves them in `case.db` under one `run_id`, one `step_log` line per step | Robin's whole TS pipeline, unchanged | a small runner + a CLI flag in Robin's script for the output folder and config (to agree with Robin) |
| 3 | `pipeline/llm.py` → Robin's `complete_as` / `FakeLLM` draft | `docs/backend_b1/llm_client_interface.py` | trace line (contract §8) |
| 4 | Template import: Daniel's ZIP → validated → `rules.db` | Robin's `format-spec.json`, Daniel's export | validator per `TEMPLATE_CONTRACT.md` |
| 5 | Then, step by step and with Robin, move the v1.1 differences (CM ID decides hire date, salary, contract type; Plot slots) — porting `normalize.ts` rules, not inventing new ones | `normalize.ts`, `ingest.py` | per contract v1.1 |

Step 2 is what makes "the generator runs inside the backend" true today,
without rewriting it.

## 5. Questions

| Question | Who |
|---|---|
| OK that the backend runs the TS generator as a subprocess until the v1.1 Python steps exist? Can `generate-example.ts` take `--config <file>` and `--out <dir>`? | Robin |
| Template contract v0.2 (`docs/TEMPLATE_CONTRACT.md`) | Daniel, Robin |
| Monitoring dashboard: which KPIs, from which tables (`run`, `step_log`, …) | Mike |
| Case model v1.2: `signed_by`, document `title`, `restricted`, `access_group` | all |
