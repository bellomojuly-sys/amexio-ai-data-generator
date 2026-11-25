# Template contract: from Daniel's Template Studio to the backend (v0.2)

Version **0.2**, 17 November 2026 · from: Giulia (backend, case model) · to:
Daniel (PDF Template Studio, `pdf_template_studio/`) · cc: Robin (document-type
spec) · Status: **proposed**, to agree with Daniel and Robin; then it changes
only with a new version number.

Related: `docs/PIPELINE_CONTRACT.md` (v1.1), `docs/DB_SCHEMA_CHANGES.md`,
`docs/TEAM_CODE_ANALYSIS.md`.

| Version | What |
|---|---|
| 0.1 | First draft: invented its own field types and generator rules |
| **0.2** | **Reuses what exists:** Robin's document-type spec (`generator/demo_dossier_generator/src/spec/`) is the field catalogue; its `FieldFormat` and `ValueOrigin` are the closed lists. Nothing new is invented on the backend side |

## The problem this contract solves

Today the studio's AI step invents the placeholder names
(`"placeholder": "UPPERCASE_SNAKE_CASE"`), so the backend receives names it has
never seen. It cannot know what such a field means, its format, or how to make
a value for it, and would have to guess. Then a fact in a document comes from
nowhere.

The rule, as in the pipeline contract: **AI proposes, code decides the
structure.** The LLM never chooses the format of the data. The backend
publishes the fields it knows; the studio maps every placeholder onto them;
whatever does not fit is declared from closed lists, checked by the backend and
approved by a person. A field the backend has not accepted is never used in a
run.

## 0. What already exists (and is reused, not rebuilt)

| What | Where | Used as |
|---|---|---|
| Nine document types, each with its fields (`key`, `label`, `format`, `origin`, `rule`), title pattern, tags, confidentiality, ACL | Robin, `src/spec/doctypes/*.ts`, exported as `format-spec.json` (`src/spec/exportSpec.ts`) | **The field catalogue** |
| `FieldFormat`: `text`, `date`, `dateRange`, `monthYear`, `eurGrouped`, `eurPlain`, `days`, `number` | Robin, `src/spec/types.ts` | Closed list of formats |
| `ValueOrigin`: `persona`, `storyline`, `rule`, `constant`, `ai-text` | Robin, `src/spec/types.ts` | Closed list of where a value comes from |
| `LABEL_KEYS` (Employee, Department, Gross salary, Examined by, …) | Daniel, `pdf_template_studio/app.py` | Same labels as Robin's fields: both come from AMEXIO's PDFs, so a placeholder maps to a catalogue field **by its label** |
| Nine document type IDs | case model, `format_rules.DocumentType` (= Robin's `DocTypeId`) | Closed list of document types |

## 1. Every placeholder is one of two kinds

### Placeholder binding rules (AX-021a)

1. Each placeholder gets its information from a specific field in the case data.
2. If the same information is used multiple times, it always shows the same value.
3. The way information looks can change (like date formats), but the actual information stays the same.
4. Before creating a document, the system checks if all placeholders are linked to the right information.
5. All generated documents must use the same case information so everything stays consistent.

### 1.1 Catalogue field: the backend already knows it

The placeholder points to a field of Robin's spec for that document type:
`documentType` + `field` (the spec's `key`). Format and origin come from the
spec; the studio does not repeat or change them.

| Daniel's placeholder | Document type | Catalogue field (`key`) | Format | Origin |
|---|---|---|---|---|
| `GROSS_SALARY` | `payslip` | `gross` | `eurPlain` | `rule` |
| `WAGE_TAX` | `payslip` | `tax` | `eurPlain` | `rule` |
| `NET_SALARY` | `payslip` | `net` | `eurPlain` | `rule` |
| `PAYMENT_DATE` | `payslip` | `paymentDate` | `date` | `rule` |
| `EXAMINATION_DATE` | `medical_check` | `examDate` | `date` | `storyline` |
| `EXAMINED_BY` | `medical_check` | `examiner` | `text` | `constant` |
| `OVERALL_RATING` | `performance_appraisal` | `rating` | `text` | `storyline` |
| `COURSE` | `training_certificate` | `course` | `text` | `storyline` |
| `HOURS_PER_WEEK` | `employment_contract` | `hoursPerWeek` | `number` | `persona` |

The identity block on every page (Employee, Employee ID, Department) is part
of the spec's `wrapper` and maps to `wrapper.fullName`, `wrapper.employeeId`,
`wrapper.department`.

Matching rule: the studio's detected label, compared case-insensitively with
the spec's `label` for that document type. A match is proposed automatically;
the user confirms it. The short names stay in the PDF (`{{GROSS_SALARY}}`): they
fit the layout. The mapping lives in `_fields.json`.

### 1.2 Custom field: not in the catalogue

Allowed, but **declared** from the closed lists, never free:

```json
{
  "placeholder": "BONUS_TARGET",
  "kind": "custom",
  "label": "Bonus target",
  "format": "eurGrouped",
  "origin": "constant",
  "value": 1500,
  "optional": false
}
```

Which origins a custom field may have, and what it must then carry:

| `origin` | Allowed for custom? | Must carry | Who makes the value |
|---|---|---|---|
| `constant` | yes | `value` (one fixed value for every document) | code |
| `rule` | yes | `rule`: the **name** of a rule the backend already has (list published with the catalogue, e.g. `wageTax`, `netSalary`, `nextCheck`) | code |
| `ai-text` | yes, `format: "text"` only | `maxLength` | LLM, placeholders only (pipeline contract rule 3) |
| `persona`, `storyline` | **no** | — | these are case-model facts: a new one is a case-model change (new version, group agreement) |

The backend accepts a custom field only if: the `format` and `origin` are in the
lists above; the parameters for that origin are present and valid for that
format (a `constant` with format `date` must be an ISO date; with `eurPlain` or
`eurGrouped` a number); the label does not match a catalogue field of the same
document type (no `GROSS_SALARY` declared as custom); the placeholder matches
`^[A-Z][A-Z0-9_]{1,40}$` and is unique in its document type.

So the backend never has to "know" a new field in advance: it knows the
**formats** and the **origins**, and a new field is valid exactly when it is
built from them.

## 2. What the backend gives the studio

- `format-spec.json` (Robin's, committed by the generator) — the catalogue.
- `template.schema.json` — JSON Schema of the export below. The studio's AI
  call should use it as the structured output format (OpenAI `response_format`
  with a JSON Schema), so the model can only answer in this shape.
- A validation function (later `POST /templates/validate`): template in → per
  field `accepted` or `refused` with the reason. The studio shows refusals
  before Finish.

## 3. What the studio gives the backend (the export ZIP)

The ZIP keeps its layout; `manifest.json` and `_fields.json` gain fields.

`manifest.json`:

```json
{
  "contract": "template/0.2",
  "domain": "HR",
  "documents": [
    {"source": "100101_payslip_2026-09.pdf",
     "documentType": "payslip",
     "template": "payslip/0001_100101_payslip_2026-09_template.pdf",
     "fields": "payslip/0001_100101_payslip_2026-09_fields.json",
     "warnings": []}
  ]
}
```

`documentType` is one of the nine IDs. The studio's free-text group name maps
to one of them (a dropdown instead of free text); a group that maps to none is
refused.

`*_fields.json`, one entry per placeholder in use (`replace: true`):

```json
[
  {"placeholder": "GROSS_SALARY", "kind": "catalogue", "field": "gross",
   "original": "EUR 4350"},
  {"placeholder": "BONUS_TARGET", "kind": "custom", "label": "Bonus target",
   "format": "eurGrouped", "origin": "constant", "value": 1500,
   "original": "EUR 1.500"}
]
```

`original` is for the studio's preview only. The backend **never** stores it
as a fact: it is the mock's value, not a generated one. Positioned fields keep
their rectangle as today; the same two kinds apply.

## 4. What the backend does with it

1. Validate the ZIP against `template.schema.json`; unknown keys are refused.
2. Check every catalogue field against `format-spec.json` and every custom
   field against §1.2. A refusal names the document, the placeholder and the
   reason.
3. Only if everything is accepted and the user approved (human check 1): the
   **backend** writes a new template version in `rules.db` (`template`,
   `template_field`). Only the backend writes `rules.db`; a version is never
   changed afterwards.
4. A run pins `template_id` + `version`. Catalogue fields get their values as
   the generator makes them today; custom fields from their declaration. A
   placeholder in a template PDF without a field definition stops the run.

## 5. Example: a new field, end to end

The user adds "Bonus target" to the appraisal template.

1. The studio's AI suggests `{"placeholder": "BONUS_TARGET", "kind": "custom",
   "format": "eurGrouped", "origin": "constant", "value": 1500}` in the shape of
   `template.schema.json`; it cannot answer in another shape.
2. The backend checks it: format and origin known, `value` is a number, label
   free → accepted. Had the AI written `"format": "currency"` or
   `"origin": "storyline"`, it would be refused with that reason.
3. The user approves; the backend saves template v2 with the field.
4. Every appraisal of the run prints `EUR 1.500`, made by code.

## 6. Questions for Daniel (and Robin)

1. Daniel: can the studio's AI call use structured output with
   `template.schema.json`?
2. Daniel: can the type-assignment table offer the nine document types as a
   dropdown?
3. Daniel: in the fields table, two new columns — `kind` (catalogue / custom)
   and, for custom, `format` + `origin` + its parameter?
4. Daniel: which labels in AMEXIO's mock PDFs did not match a catalogue field?
   Those are the first custom fields, or candidates for Robin's spec.
5. Robin: can `npm run spec` write `format-spec.json` to a committed path
   (e.g. `pipeline/schema/format-spec.json`) so the Python backend reads it
   without Node?
