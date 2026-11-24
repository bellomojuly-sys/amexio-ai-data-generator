# Domain contract: any domain through the case model (v1.0)

Version **1.0**, 24 November 2026 · from: Giulia (case model, backend) · to:
Daniel, Robin, Valentin, Mike, Stylianos · Status: **proposed to the team**;
after agreement it changes only with a new version number.

Code: case model **v2.0** (`case_model/domain.py`, `case_model/domains.py`, PR #11).
Related: `docs/PIPELINE_CONTRACT.md` (v1.1 → v1.2), `docs/TEMPLATE_CONTRACT.md`
(v0.2 → v0.3), `case_model/README.md`.

## Why

AMEXIO wants test dossiers for OpenText, and not only HR. Until v1.2 the case
model had HR's lists in code: seven event types, nine document types, four
roles, the rules of an employment story. A dossier of another domain (an
insurance claim, a patient file, a permit) was refused.

The flow we agreed:

1. **Daniel** sends the data configuration of the domain, made from the mock
   data (MockToTemplate and the analysis). The user reviews and approves it.
2. **The case model** verifies it, validates it and fills it: code makes every
   fact (IDs, dates, amounts, values from the closed lists).
3. **The LLM** writes only the text.
4. Once the configuration is approved and generation has started, the run
   cannot be changed (team rule, 24 Nov).

## 1. The domain configuration

One JSON object per domain. JSON Schema: `case_model/schema/domain.schema.json`.

| Key | What it holds | Rules |
|---|---|---|
| `name` | the domain's name | snake_case, unique (`hr`, `insurance_claim`) |
| `version` | the configuration's version | a new version, never an edit |
| `case_number_pattern` | the dossier's key number | a regular expression; HR: `[0-9]{6}` |
| `roles` | the roles a persona can have | snake_case, unique, at least one |
| `event_types` | what can happen in a dossier: per type its `fields` | at least one; see §2 |
| `document_types` | the documents a dossier can hold | each `recurring` (no event, like a payslip) or not |
| `rules.first_event` | the event that opens the story | at most one; nothing happens before it |
| `rules.last_event` | the event that closes the story | at most one; nothing happens or ends after it |
| `rules.first_event_starts_employment` | the first event's date is the employment's start | HR only |
| `rules.last_event_label` | how an error names the last date | HR: "last working day" |

## 2. Fields of an event type

Every event has `id` (made by code), `type`, `date`, `participant_ids`,
`label`, `summary` and `signed_by`. A type adds its own fields:

| Key | Values |
|---|---|
| `format` | `text`, `date`, `money`, `integer`, `number`, `persona`, `organisation` |
| `required` | `true` / `false` |
| `values` | a closed list (only for `text`): any other value is refused |
| `gt` | lower bound, exclusive (only for `integer`, `number`) |
| `ends_period` | this date ends the event (an absence's `end_date`): never before the event's date |
| `label` | how an error names a reference ("training provider") |

`persona` and `organisation` fields hold an ID of the case and must point at a
persona or organisation the case holds. They are never printed in a document.

## 3. Example: a second domain

```json
{
  "name": "insurance_claim",
  "case_number_pattern": "CL[0-9]{6}",
  "roles": ["policyholder", "adjuster", "inspector"],
  "event_types": {
    "policy_start": {"fields": {"premium": {"format": "money", "required": true}}},
    "claim_filed": {"fields": {
      "cause": {"format": "text", "required": true,
                "values": ["Water damage", "Fire", "Theft", "Storm"]},
      "claimed_amount": {"format": "money", "required": true}}},
    "inspection": {"fields": {
      "inspector_id": {"format": "persona", "required": true, "label": "inspector"},
      "finding": {"format": "text", "required": true}}},
    "repair": {"fields": {"end_date": {"format": "date", "ends_period": true}}},
    "payout": {"fields": {"amount": {"format": "money", "required": true}}},
    "claim_closed": {}
  },
  "document_types": {"policy": {}, "claim_form": {}, "inspection_report": {},
                     "premium_statement": {"recurring": true}},
  "rules": {"first_event": "policy_start", "last_event": "claim_closed"}
}
```

HR is the same kind of object (`case_model/domains.py`): the seven event types,
nine document types, four roles and the rules of v1.2.

## 4. What the case model guarantees, for every domain

- IDs are made by code (`P001`, `ORG-01`, `EVT-001`, `DOC-001`); an ID in the
  input is refused.
- An event of a type the domain does not have, a field the type does not
  define, a missing required field, or a value outside a closed list is
  refused, naming the event and the field.
- Every reference points at something the case holds.
- Dates are ISO 8601, amounts are a number plus a currency.
- The story follows the domain's rules.
- Placeholders `{{ path }}` resolve from the case, or the run stops (M04).
- A malformed configuration is refused before any case uses it.

HR files are saved byte for byte as in v1.2; a case of another domain writes
`"domain": "<name>"` in `case.json`.

## 5. What changes for each of us

| Who | Change | Contract |
|---|---|---|
| **Daniel** | The data configuration also lists the domain's **event types and their fields** (the analysis can propose them from the mock documents), and the document types. The user approves it before the run | template contract **v0.3**: `documentType` is one of the configuration's types, not one of the nine HR types |
| **Robin** | The three prompts take event types, fields and closed lists from the configuration instead of HR's fixed lists. The demo keeps working: HR is a configuration | pipeline contract **v1.2** |
| **Valentin** | Step 5 Dates & participants reads the date rules per event type from the configuration; Fill already works for any domain (`fill_text`) | pipeline contract **v1.2** |
| **Mike** | `run_chain` passes the domain's name; nothing else | pipeline contract **v1.2**: `RunConfig.domain` |
| **Stylianos** | Export reads document types from the configuration | — |

Pipeline contract v1.2 in short: `RunConfig` names its domain (name and
version, stored in `rules.db`); Plot picks event types and closed values from
the configuration; Event content writes text only in `text` fields.

## 6. Steps

| ID | What | Who | State |
|---|---|---|---|
| GD-01 | Domain configuration, HR as data | Giulia | built, PR #11 |
| GD-02 | The case validates against its domain | Giulia | built, PR #11 |
| GD-03 | Rules between events from the configuration | Giulia | built, PR #11 |
| GD-04 | Save, load, fill and schemas per domain | Giulia | built, PR #11 |
| GD-05 | Daniel's configuration → `DomainConfig`; ingest without IDs for any domain | Giulia, Daniel | next |
| GD-06 | Pipeline contract v1.2 | Giulia, Robin, Valentin, Mike | after GD-05 |
| GD-07 | Template contract v0.3 | Giulia, Daniel | after GD-05 |

## 7. Question for the team

**Where do a domain's event types come from?** Proposal: Daniel's export lists
them (his analysis proposes them from the mock documents, the user approves
them). Alternative: the backend derives one event per non-recurring document
type; more automatic, less precise.

## 8. Sign-off

| Who | Agrees | Date |
|---|---|---|
| Daniel | ⬜ | |
| Robin | ⬜ | |
| Valentin | ⬜ | |
| Mike | ⬜ | |
| Stylianos | ⬜ | |
| Giulia | ✅ | 24 Nov 2026 |
