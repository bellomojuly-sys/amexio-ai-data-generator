# Database schema: changes to the draft (proposed)

Draft reviewed: the ERD in *AMEXIO Data Generator Design* (draft for Review 2,
13 Nov 2026), tab "The data". Owner of the case tables: Giulia. Status:
**proposed**, to agree in the team.

Rule used for every change: **the case model v1.1 is the source of truth.** The
tables inside the dossier box store a `Case` exactly, so that
`load_case_db(save_case_db(case)) == case`. If the database cannot hold a field
the case model has, a case gets lost on the way.

Engine stays as drawn: two SQLite files, `rules.db` and `case.db`, through
Python's built-in `sqlite3` (no new dependency). `PRAGMA foreign_keys = ON` on
every connection, or SQLite ignores the foreign keys.

## 1. Must change (the draft would lose or corrupt data)

### 1.1 Keys of the dossier tables are composite

`P001`, `ORG-01`, `EVT-001` and `DOC-001` are unique **inside one case**, not
across a run: every case has its own `P001`. With `persona_id` alone as the
primary key, the second dossier of a run cannot be saved.

| Table | Draft PK | New PK |
|---|---|---|
| `persona` | `persona_id` | `(case_id, persona_id)` |
| `organisation` | `organisation_id` | `(case_id, organisation_id)` |
| `event` | `event_id` | `(case_id, event_id)` |
| `document` | `document_id` | `(case_id, document_id)` |
| `event_participant` | `(event_id, persona_id)` | `(case_id, event_id, persona_id)` |
| `edit_target` | `(edit_id, document_id)` | `(edit_id, case_id, document_id)` |

Every foreign key between these tables carries `case_id` too, e.g.
`FOREIGN KEY (case_id, persona_id) REFERENCES persona(case_id, persona_id)`.
This also makes the database refuse a link to a persona of another dossier.

`employment` keeps a surrogate key, but adds `UNIQUE (case_id, persona_id)`:
the placeholder lookup (`{{employments.P001.salary.amount}}`) needs one
employment per persona.

### 1.2 `case` needs the case number and the dossier facts

| Column | Type | Why |
|---|---|---|
| `case_number` | TEXT NOT NULL | `Case.case_number`; unique within a run: `UNIQUE (run_id, case_number)` |
| `employee_number` | TEXT NOT NULL, `CHECK (length = 6)` | already drawn; six digits (AX-011) |
| `description` | TEXT NULL | `Dossier.description` is missing |

### 1.3 `document` needs its participants

`Document.participant_ids` is required in the case model ("at least one
participant", AX-017). Add a link table:

`document_participant (case_id, document_id, persona_id)`, PK all three,
FKs to `document` and `persona`.

### 1.4 Event facts by type

The case model has seven event types, each with its own fields
(`training.course`, `training.duration_days`, `training.provider_id`,
`appraisal.year`, `appraisal.rating`, `contract_change.new_salary`, …). The
draft has one `details` column.

Proposal: keep **one** `event` table with the common columns (`type`, `date`,
`label`, `summary`) and put the type-specific fields in `details` as **JSON
validated by the case model before it is written**. One table per event type
is the alternative (7 tables, real SQL types, harder to change). Decision to
log.

`type` gets a `CHECK (type IN ('hire','contract_change','training',
'appraisal','medical_check','absence','termination'))`.

### 1.5 Amounts are two columns

`salary` "+ currency" becomes `salary_amount NUMERIC NOT NULL` and
`salary_currency TEXT NOT NULL CHECK (length = 3)`. Same for every amount
(`new_salary` inside `details` stays a `{amount, currency}` object).

### 1.6 Dates are ISO text

SQLite has no date type. Every date column is `TEXT` with
`CHECK (date(col) = col)`, so `"12/03/2026"` is refused by the database too.

## 2. Missing fields (the case model has them, the draft does not)

| Table | Add |
|---|---|
| `persona` | `salutation`; rename `birth_date` → `date_of_birth`; `role` with `CHECK (role IN ('employee','manager','hr_officer','examiner'))` |
| `organisation` | `kind`, `address` |
| `employment` | `contract_type` with `CHECK (IN ('Permanent','Temporary'))`; `hours` as REAL |
| `template_field` (new, `rules.db`) | one row per template field: `template_id`, `version`, `document_type`, `placeholder`, `kind` (`catalogue` / `custom`), `field` (catalogue key) or `label` + `format` + `origin` + `params` (JSON), `optional` — formats and origins are Robin's `FieldFormat` and `ValueOrigin`, see `docs/TEMPLATE_CONTRACT.md` |
| `case_field_value` (new, `case.db`) | values of **custom** template fields per case: `case_id`, `document_id`, `placeholder`, `value` (JSON, validated against the field's type) |
| `document` | `employee_id` (metadata), `tags` as JSON array; `type` with `CHECK` on the nine document types |
| `event` | `signed_by` (persona ID, NULL) — only once case model v1.2 is agreed |

## 3. In the draft but not in the case model

These are needed (export, review, KPIs), but the case model v1.1 has no field
for them. Two ways: (a) add them to the case model as **v1.2** by group
agreement, or (b) keep them as **storage-only** columns outside `Case`
(written by export or review, not by the pipeline).

| Column | Proposal |
|---|---|
| `document.title` | (a) v1.2 — AMEXIO's `import.xml` has a title; Robin's spec already makes it (`titlePattern`) |
| `document.restricted`, `document.access_group` | (a) v1.2, with Stylianos; Robin's spec already has them per document type (`confidential`, `acl`) |
| `document.data_type` (`SYNTHETIC`) | (b) storage-only, always `SYNTHETIC`, set by code |
| `document.pdf_path` | (b) storage-only, written by export |
| `event_participant.role_in_event` | (b) for now; the case model only stores `participant_ids` |
| `case.status`, `validator_errors`, `case_model_ok`, `attempt` | (b) pipeline state, not case facts |

## 4. Smaller fixes

- `step_log.case_id` → nullable FK to `case(case_id)`; `step` with a `CHECK`
  on the step names of the pipeline contract §3; add `run_id` index.
- `step_log` columns follow the trace line of the contract §8: `ok`, `ms`,
  `model`, `input_tokens`, `output_tokens`, `retries`, `cost_eur`, `error`.
  Rename `tokens_in`/`tokens_out` → `input_tokens`/`output_tokens`.
- `run.run_id` is the code-made `GEN-YYYY-NNNN` (AX-032), TEXT PK.
- `run.template_id` + `run.template_version`: the link to `rules.db` is checked
  by code, so store the **version** too, or a later edit changes what an old
  run claims it used.
- `template.document_types` and the field definitions move to their own table
  `template_field` (see `docs/TEMPLATE_CONTRACT.md`): one row per field, so the
  backend can validate against them.
- `template`: `UNIQUE (domain_id, version)`; a template version is never
  updated, an edit makes a new version.
- `review.decision` and `upload.status`: `CHECK` on the listed values.
- `domain.attribute_list` → table `domain_attribute`, or JSON validated in code.

## 5. Decided by Giulia (17 Nov)

- The database **is** the store the pipeline and monitoring read. The four
  JSON files per case stay only as an export/exchange format (Robin's generator
  writes and reads them; `load_case` stays the check).
- Columns the monitoring needs are stored; those that are dossier facts go into
  the case model as **v1.2** (proposal to the team).
- Only the backend writes `rules.db`.
- `sqlite3` from the standard library; no new dependency.

## 6. Questions for the team

1. Event facts: one table + JSON `details` (proposal) or one table per type?
2. Section 3: which columns go into case model v1.2, which stay storage-only?
