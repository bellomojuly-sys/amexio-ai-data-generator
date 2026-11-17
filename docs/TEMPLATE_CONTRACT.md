# Template contract: from Daniel's Template Studio to the backend (v0.1)

Version **0.1**, 17 November 2026 · from: Giulia (backend, case model) · to:
Daniel (PDF Template Studio, branch `MockToTemplate`) · Status: **proposed**,
to agree with Daniel, then it changes only with a new version number.

Related: `docs/PIPELINE_CONTRACT.md` (v1.1), `docs/DB_SCHEMA_CHANGES.md`.

## The problem this contract solves

Today the studio's AI step invents the placeholder names
(`"placeholder": "UPPERCASE_SNAKE_CASE"`), so the backend receives names it has
never seen, e.g. `{{GROSS_MONTHLY_SALARY}}` or `{{BONUS_TARGET}}`. The backend
cannot know what such a field means, which type it has, or how to make a value
for it. It would have to guess, and then a fact in a document comes from nowhere.

The rule, as in the pipeline contract: **AI proposes, code decides the
structure.** The LLM never chooses the format of the data. The backend
publishes the list of fields it knows and the types it accepts; the studio
maps every placeholder onto that list; whatever does not fit is declared
explicitly, checked by the backend, and approved by a person before it is
used. A field the backend has not accepted is never used in a run.

## 1. Every placeholder is one of two kinds

### 1.1 Bound field: a fact the case model already has

The placeholder points to a path in the case model (the same paths as
`get_fact`, pipeline contract §7). The backend publishes the catalogue of
paths it accepts (`field_catalogue.json`, see §4). Examples:

| Placeholder in the PDF | `binding` | Type |
|---|---|---|
| `EMPLOYEE_NAME` | `personas.$employee.name` | `text` |
| `EMPLOYEE_ID` | `dossier.employee_number` | `text` |
| `DEPARTMENT` | `employments.$employee.department` | `text` |
| `POSITION` | `employments.$employee.position` | `text` |
| `START_DATE` | `employments.$employee.start_date` | `date` |
| `CONTRACT_TYPE` | `employments.$employee.contract_type` | `enum` |
| `HOURS_PER_WEEK` | `employments.$employee.hours` | `decimal` |
| `GROSS_MONTHLY_SALARY` | `employments.$employee.salary` | `money` |
| `MANAGER` | `personas.$manager.name` | `text` |
| `REVIEW_DATE` | `events.$event.date` | `date` |
| `OVERALL_RATING` | `events.$event.rating` | `enum` |
| `COURSE` | `events.$event.course` | `text` |

`$employee`, `$manager` and `$event` are **roles**, not IDs: the template does
not know which persona is `P001` in a case. The backend replaces the role with
the real ID when it fills one document (`$event` = the event the document
records). The template never contains a case ID (rule 1 of the pipeline
contract).

The studio keeps its short names in the PDF (`{{EMPLOYEE_NAME}}`): they fit
the layout. The binding lives in `_fields.json`, not in the PDF.

### 1.2 Custom field: a new field the case model does not have

Allowed, but **declared**, never free. The declaration says what the field is
and how code makes its value. The LLM may suggest a declaration; the backend
validates it; a person approves it in the studio.

```json
{
  "placeholder": "BONUS_TARGET",
  "kind": "custom",
  "type": "money",
  "required": true,
  "generator": {"rule": "range", "min": 500, "max": 3000, "currency": "EUR"},
  "description": "Yearly bonus target printed on the appraisal"
}
```

The backend accepts a custom field only if:

1. `type` is one of the closed types (§2);
2. `generator.rule` is one of the closed rules (§3), with the parameters that
   rule needs, valid for that type;
3. the name is not already a bound field (no `GROSS_SALARY` declared as custom
   when the catalogue already has it);
4. the name matches `^[A-Z][A-Z0-9_]{1,40}$` and is unique in its document type.

Then the field is stored in `rules.db` (`template_field`) with the template
version. From then on the backend validates every value of that field against
the declaration, makes it with the declared rule, and stores it with the case.
Only code makes the value; the LLM never writes it (rule 2).

## 2. Closed field types

| Type | Stored as | Example |
|---|---|---|
| `text` | string, max length optional | `"Software Developer"` |
| `date` | ISO 8601 `YYYY-MM-DD` | `"2026-03-12"` |
| `money` | `{"amount": number, "currency": "EUR"}` | `{"amount": 4350.0, "currency": "EUR"}` |
| `integer` | integer, `min`/`max` optional | `2` |
| `decimal` | number, `min`/`max` optional | `38.0` |
| `boolean` | `true`/`false` | `true` |
| `enum` | one of `values` | `"Meets expectations"` |
| `person` | a persona role (`$employee`, `$manager`, …) | name printed at fill time |

Formatting (long dates, `€ 4.350,00`) happens only when the PDF is filled
(AX-025). The template never stores a formatted value.

## 3. Closed generator rules (custom fields only)

| Rule | Types | Parameters |
|---|---|---|
| `fixed` | all | `value` |
| `choice` | `text`, `enum` | `values` (list), optional `weights` |
| `range` | `integer`, `decimal`, `money` | `min`, `max` (+ `currency` for money) |
| `date_offset` | `date` | `from` (a bound date path), `days_min`, `days_max` |
| `derived` | `decimal`, `money` | `formula` from the backend's list (e.g. `net_from_gross`) |
| `llm_text` | `text` only | `max_length`; written by the LLM with placeholders only (rule 3) |

A rule outside this list is refused. A new rule is a backend change and a new
version of this contract.

## 4. What the backend gives the studio

- `field_catalogue.json` — every bound path with its type and the document
  types where it makes sense. Generated from the case model by code
  (`python -m pipeline.catalogue`), committed next to the schemas.
- `template.schema.json` — JSON Schema of the export below. The studio's AI
  call should use it as the structured output format, so the model can only
  answer in this shape.
- A validation function (later `POST /templates/validate`): template in →
  per field `accepted` or `refused` with the reason. The studio shows the
  refusals to the user before Finish.

## 5. What the studio gives the backend (the export ZIP)

The ZIP keeps its layout; `manifest.json` and `_fields.json` gain fields.

`manifest.json`:

```json
{
  "contract": "template/0.1",
  "domain": "HR",
  "documents": [
    {"source": "100101_contract.pdf",
     "documentType": "employment_contract",
     "template": "employment_contract/0001_100101_contract_template.pdf",
     "fields": "employment_contract/0001_100101_contract_fields.json",
     "warnings": []}
  ]
}
```

- `documentType` is one of the nine case-model types: `employment_contract`,
  `payslip`, `medical_check`, `performance_appraisal`, `training_certificate`,
  `contract_amendment`, `annual_income_statement`, `absence_report`,
  `termination_letter`. The studio's free-text group name maps to one of them;
  a group that maps to none is refused (a new document type is a case-model
  change, by group agreement).

`*_fields.json`, one entry per placeholder that is used (`replace: true`):

```json
[
  {"placeholder": "EMPLOYEE_NAME", "kind": "bound",
   "binding": "personas.$employee.name", "type": "text",
   "original": "Jan de Vries"},
  {"placeholder": "BONUS_TARGET", "kind": "custom", "type": "money",
   "required": true,
   "generator": {"rule": "range", "min": 500, "max": 3000, "currency": "EUR"},
   "original": "€ 1.500,00"}
]
```

- `original` stays for the preview only. The backend **never** stores it as a
  fact: it is the mock's real-looking value, not a generated one.
- Positioned fields keep their rectangle as today; the same two kinds apply.

## 6. What the backend does with it

1. Validate the ZIP against `template.schema.json`; unknown keys are refused.
2. Check every bound path against the catalogue and every custom field against
   §1.2–§3. One refusal names the document, the placeholder and the reason.
3. Only if everything is accepted and the user approved (human check 1): save a
   **new template version** in `rules.db` (`template`, one row per field in
   `template_field`). A version is never changed afterwards.
4. A run pins `template_id` + `version`. Fill (Valentin) resolves bound fields
   with `get_fact` and custom fields from the values code made for that case.
   A placeholder in the PDF without a field definition stops the run (AX-024).

## 7. Example: the new-field question, end to end

The user adds "Bonus target" to the appraisal template.

1. The studio's AI suggests `{"placeholder": "BONUS_TARGET", "kind": "custom",
   "type": "money", "generator": {"rule": "range", …}}` — in the shape of
   `template.schema.json`, so it cannot invent another shape.
2. The backend checks it: type and rule known, parameters valid, name free →
   accepted. Had the AI written `"type": "currency"` or `"rule": "guess"`, it
   would be refused with that reason, and the user fixes it in the studio.
3. The user approves; template v2 is saved with the field.
4. At run time code draws a value between 500 and 3000 EUR, validates it as
   `money`, stores it with the case, and Fill prints it.

The backend never has to "know" the field in advance: it knows the **types**
and the **rules**, and a new field is valid exactly when it is built from them.

## 8. Questions for Daniel

1. Can the studio's AI call use structured output with `template.schema.json`
   (OpenAI `response_format` with a JSON Schema) instead of free JSON?
2. Can the type-assignment table offer the nine document types as a dropdown
   instead of free text?
3. Where should the user choose `bound` vs `custom` and fill in the generator
   rule: in the fields table, as two new columns?
4. Do you want to keep the short names (`{{EMPLOYEE_NAME}}`) in the PDFs
   (proposal), or write paths in the PDF?
5. Which document types and fields does the studio see in AMEXIO's mock
   package that the catalogue does not cover yet? Those are the first custom
   fields to test, or candidates for case model v1.2.
