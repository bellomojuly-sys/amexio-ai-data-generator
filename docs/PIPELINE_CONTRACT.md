# Pipeline contract — generation ↔ case model

Version **0.2**, 2 November 2026 · owner: Giulia (Datanova) · microphases BE-02, BE-03, AX-021

Replaces the draft of 28 October (`docs/backend_b1/BACKEND_B1_PROPOSAL.md`, Part 2 and Part 4). It follows the 30 October meeting and Robin's note *Generation in three parts: the LLM calls* (31 October), and closes the five gaps Robin found in the draft.

**Status:** proposed. Each owner confirms their row in §2. After that, the contract changes only by group agreement and a new version number.

---

## 1. The rules at every boundary

1. **Generation never writes an ID.** It may only echo a key that code gave it: an employee number, a slot key, a document key.
2. **Generation never writes dates, amounts, participants, signers or closed-list values.** Code decides them.
3. **Each prompt is built from what the case model saved**, not from the previous LLM answer.
4. **A bad answer gets one retry, then an `LLMError` that names the field.** Nothing is half-written: no partial case is saved or returned.
5. **Every LLM call goes through the one LLM client**, which records model, tokens, time and retries for the trace (§7).
6. **Every boundary is a Pydantic model** with its JSON Schema exported next to the case-model schemas. An unknown field is refused.

---

## 2. The chain

| # | Step | Kind | Owner | Input | Output |
|---|---|---|---|---|---|
| 0 | Create analysis | LLM (frontend) | Daniel | AMEXIO mock data or a description | `RunConfig` (reviewed by the user) |
| 1 | **Personas** | LLM | Robin | `RunConfig` | `PersonasIn` |
| 2 | **CM ID** | code | Giulia | `PersonasIn` + `RunConfig` | cases with IDs (via `ingest_employees`) |
| 3 | **Plot** | code | Giulia | cases + `RunConfig` | `PlotOutline` (slots, no dates) |
| 4 | **Event content** | LLM | Robin | cases + `PlotOutline` | `EventContentIn` |
| 5 | **Dates and participants** | code | Valentin | outline + content + cases | `StorylinesIn` → `ingest_storylines` |
| 6 | **Document plan** | code | Giulia | cases with dated events | `DocumentPlan` |
| 7 | **Document text** | LLM | Robin | one case + its `DocumentPlan` | `DocumentTextsIn` |
| 8 | **Fill** | code | Valentin | case + `DocumentTextsIn` | `Document.text` filled (lookup AX-022) |
| 9 | Export | code | Stylianos | complete cases | PDFs + `import.xml` |

The orchestrator calls steps 1–8 in this fixed order inside the one Python service (BE-01).

Generation is three Python functions:

```python
propose_personas(config: RunConfig, llm) -> PersonasIn
write_event_content(cases, outline: PlotOutline, llm) -> EventContentIn
write_document_text(case, plan: CaseDocumentPlan, llm) -> DocumentTextsIn
```

---

## 3. Run request (`POST /runs`) — gap 1

The request carries the **reviewed configuration**, not the employees. Part 1 creates the employees.

```json
{
  "config": {
    "company": {
      "employerName": "Acme Logistics B.V. (fictional)",
      "trainingProvider": "Training Academy (fictional)",
      "examiner": "Occupational physician (fictional)",
      "absenceService": "Occupational health service (fictional)",
      "directorName": "H. de Wit (fictional)"
    },
    "departments": [
      {"name": "IT",
       "positions": [
         {"title": "Software Developer", "salaryMin": 3800, "salaryMax": 5200},
         {"title": "IT Manager", "salaryMin": 5500, "salaryMax": 7000, "isManagerRole": true}
       ]}
    ],
    "employeeCount": 10,
    "temporaryShare": 0.2,
    "partTimeShare": 0.3,
    "asOfDate": "2026-10-31",
    "notes": "Logistics company, mostly office staff."
  },
  "seedEmployees": null,
  "options": {"fake_llm": false}
}
```

- `seedEmployees` is **optional**: a starting set in the `EmployeesIn` shape (for example the reference employee 100101). Seed employees skip Part 1 and go straight to CM ID; Part 1 proposes only `employeeCount − len(seedEmployees)`.
- A request that carries an `id` anywhere is refused (422).
- The response is unchanged from the draft: `run_id`, `status`, `cases` (each one object of `case.schema.json`), `corrections`, `trace` (§7). Errors keep the one shape `{"error": {"kind", "stage", "message", "field"}}`.

---

## 4. Part 1 → CM ID

**`PersonasIn`** — what the LLM writes, per employee:

| Field | Type | Note |
|---|---|---|
| `firstName`, `lastName` | string | |
| `department` | string | must be in `config.departments` |
| `position` | string | must be in that department's positions |
| `isManager` | bool | |
| `contractType` | `Permanent` \| `Temporary` | closed list |
| `hoursPerWeek` | number | |

**Decision (Giulia, Robin):** `hireDate` and `startSalary` are **not** written by the LLM. CM ID sets them: the salary inside the position's range, the hire date before `asOfDate` by the rules of the HR template. Same rule as the event dates: AI writes, code keeps the facts.

CM ID then builds `EmployeesIn` (the existing `input.employees.schema.json`, unchanged) and calls `ingest_employees`, which gives personnel numbers and the `P` and `ORG` IDs. A department or position outside the config is a correction or a refusal, named in `corrections`.

---

## 5. Plot → Event content → Dates — gap 2

### `PlotOutline` (code, Giulia)

Per employee number, 1–10 **slots**. Each slot has a key from code and the facts code already decided. No dates, participants or IDs.

```json
{"outlines": [{"employeeNumber": "100101", "slots": [
  {"slot": "S01", "type": "training"},
  {"slot": "S02", "type": "appraisal", "year": 2025, "rating": "Meets expectations"},
  {"slot": "S03", "type": "contract_change", "change": "promotion", "newPosition": "Senior Software Developer"},
  {"slot": "S04", "type": "medical_check"}
]}]}
```

**Decision (Giulia, Robin):** **Plot picks the closed-list values** — appraisal rating, termination reason, and the new position on a promotion. Coherence between events (two weak appraisals before a dismissal) is a property of the plot, so it stays in code. The LLM then writes text that agrees with those values.

### `EventContentIn` (LLM, Robin)

Per employee number, every slot answered exactly once, by echoing its key:

| Event type | LLM writes | Code decides |
|---|---|---|
| `contract_change` | `reason` (text) | change kind, new position (Plot); date, new salary, contract type, hours (Dates) |
| `training` | `course`, `durationDays` | date, provider (Dates) |
| `appraisal` | `comment` | rating, year (Plot); date 30 June, signer (Dates) |
| `termination` | nothing beyond the summary | reason (Plot); date, notice date (Dates) |
| `absence` | nothing: never a cause | start and end date (Dates) |
| `medical_check` | nothing | date, result (Dates) |
| `hire` | — (not a slot; CM ID adds it) | everything |

Every slot also gets a one-line `summary` (the event already has that field).

```json
{"content": [{"employeeNumber": "100101", "slots": [
  {"slot": "S01", "summary": "Two-day secure coding course.", "course": "Secure Coding Fundamentals", "durationDays": 2},
  {"slot": "S02", "summary": "Solid year, steady delivery.", "comment": "Jan delivered his sprint goals reliably."}
]}]}
```

Checked by `complete_as`: every slot answered once, no unknown or missing slot, one retry.

### `storylines.json` (code, Valentin)

`storylines.json` is **no longer an LLM output**. It is what the Dates step hands to `ingest_storylines`, so every event in it has a date. Its shape (`input.storylines.schema.json`) stays as it is, plus `signedBy` (§6).

---

## 6. `signed_by` — gap 4

**Decision (Giulia):** `signed_by` lives **on the event**, as an optional persona ID. The Dates step sets it (the manager at the event date, or the director when the manager has left). A document inherits the signer of its event; recurring documents without an event (payslips) are signed by the employer as the template says.

This is a change to the case-model schema after v1.1, so it becomes **case model v1.2** (new field `signed_by: str | None` on every event, checked as a persona ID the case holds; `signedBy` in the storylines input). Needs team agreement before it is merged.

---

## 7. Document plan → Document text → Fill — gap 3

### `DocumentPlan` (code, Giulia)

Built after the Dates step, when events have IDs. Per case, the documents to write, each with a key from code:

```json
{"plans": [{"employeeNumber": "100101", "documents": [
  {"doc": "D01", "type": "performance_appraisal", "eventId": "EVT-004", "sections": ["feedback", "summary"]},
  {"doc": "D02", "type": "contract_amendment", "eventId": "EVT-005", "sections": ["cover_letter"]}
]}]}
```

**Which documents get LLM text** (Robin's proposal, accepted): performance appraisal, termination letter, contract amendment. Employment contract, training certificate, payslip, annual income statement, medical check and absence report stay templated. One Part 3 call per employee writes all of that dossier's texts together.

### `DocumentTextsIn` (LLM, Robin)

```json
{"employeeNumber": "100101", "documents": [
  {"doc": "D01", "sections": {
    "feedback": "On {{events.EVT-004.date}}, {{personas.P002.name}} reviewed the work of {{personas.P001.name}}.",
    "summary": "..."
  }}
]}
```

### Placeholder syntax — AX-021

**Decision:** `{{<collection>.<ID>.<field>}}`, a path straight into the case model. No mapping table.

| Collection | Example |
|---|---|
| `personas` | `{{personas.P001.name}}` |
| `organisations` | `{{organisations.ORG-01.name}}` |
| `events` | `{{events.EVT-004.date}}`, `{{events.EVT-004.rating}}` |
| `dossier` | `{{dossier.employee_number}}` (no ID part) |

`employee_001` (meeting notes) is not used: the case model's IDs are `P001`, so it would need an extra mapping and it does not say which field is wanted.

Checked inside `complete_as`: an unknown collection, ID or field fails validation, and so does a name, date or amount typed out instead of a placeholder. One retry with the bad placeholder named, then the run fails. Fill (Valentin) resolves every placeholder with the lookup (AX-022) and rejects any ID the case does not hold; dates and amounts are formatted only when the text is filled (AX-025).

---

## 8. Trace — gap 5

One trace line per **LLM call** and one per **code step**, all with the run ID, so a run can be rebuilt from the trace alone (BE-19, for Mike).

```json
{"run_id": "GEN-2026-0001", "stage": "event_content", "kind": "llm",
 "ok": true, "ms": 8421, "model": "claude-sonnet-...",
 "input_tokens": 3120, "output_tokens": 2480, "retries": 0,
 "cost_eur": 0.047, "error": null}
```

- Code steps have `kind: "code"` and no token fields.
- `cost_eur` is computed from the tokens and a price table in config, not by the client.
- **Change needed in the LLM client (Robin):** `complete()` returns the text **and** the token usage; `complete_as` adds the retry count.

---

## 9. Still open

| Question | Who |
|---|---|
| Batch sizes: keep the demo's 25 (personas) and 5 (event content), then measure with the school key | Robin, Mike |
| A second human review after Fill | Daniel |
| Exact shape of Daniel's `RunConfig` output and the review screen that edits it | Daniel, Giulia |
| Case model v1.2 (`signed_by`) agreed by the team | all |

## 10. Next

- BE-03 v2 (Giulia, from Wed 4 Nov): `pipeline/contracts.py` with `RunConfig`, `PersonasIn`, `PlotOutline`, `EventContentIn`, `DocumentPlan`, `DocumentTextsIn`, `TraceLine`; JSON Schemas exported; example payloads validate, a payload with an LLM-written ID fails.
- Worked examples for the Part 2 and Part 3 boundaries on 100101, like `EXAMPLE_PAYLOAD.md` for Part 1.
