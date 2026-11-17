# Backend pipeline contract (v1.1)

Version **1.1**, 16 November 2026 · owner: Giulia (Datanova)

**Status: proposed.** Each owner confirms their row in §11. After that, the
contract changes only by group agreement and a new version number.

## What changed and why

| Version | Date | What |
|---|---|---|
| 0.2 | 2 Nov | Generation in three LLM calls (Robin's note *Generation in three parts*), code decides the facts, `RunConfig` from Daniel |
| 1.0 | 5 Nov | Option A: Daniel's analysis delivered the employees directly as `EmployeesIn` (with hire date and salary); no Personas call |
| **1.1** | **16 Nov** | **Back to the 0.2 flow**, plus the four fixes Robin raised on 3 Nov (§12) |

Why 1.0 is replaced: under Option A the analysis is an LLM call that writes hire
dates, salaries and contract types. That breaks the team rule *AI writes, code
keeps the facts* (rule 2 below). Robin's three-part design keeps every fact in
code and was already built on 0.2. What 1.0 got right stays: one Python service
(BE-01), the stub chain (BE-05), the LLM client with an offline fake (BE-04), the
placeholder lookup (AX-021, AX-022). Option A's `EmployeesIn` input survives as
**seed employees** (§3).

---

## 1. The rules at every boundary

1. **Generation never writes an ID.** It may only echo a key that code gave it:
   an employee number, a slot key, a document key.
2. **Generation never writes dates, amounts, numbers, participants, signers or
   closed-list values.** Code decides them. This includes `contractType`,
   `hoursPerWeek` and `durationDays` (§4, §5).
3. **Generation never types out a name, date or amount in free text.** Every fact
   in a text is a placeholder (§7). This holds for Part 2 and Part 3 alike.
4. **Each prompt is built from what the case model saved**, not from the previous
   LLM answer.
5. **A bad answer gets one retry, then an `LLMError` that names the field.**
   Nothing is half-written: no partial case is saved or returned.
6. **Every LLM call goes through the one LLM client**, which records model,
   tokens, time and retries for the trace (§8).
7. **Every boundary is a Pydantic model** with its JSON Schema exported next to
   the case-model schemas. An unknown field is refused.

## 2. Runtime (BE-01, unchanged)

One Python service hosts the case model. Each step is a Python function with one
typed input and one typed output. Steps talk in-process with validated pydantic
objects; what crosses between owners is also exported as JSON Schema. Decision:
`docs/decisions/BE-01-backend-runtime.md`.

## 3. The chain

| # | Step | Kind | Owner | Input | Output |
|---|---|---|---|---|---|
| 0 | Create analysis | LLM (frontend) | Daniel | AMEXIO mock data or a description | `RunConfig`, reviewed by the user |
| 1 | **Personas** | LLM | Robin | `RunConfig` | `PersonasIn` |
| 2 | **CM ID** | code | **Giulia** | `PersonasIn` + `RunConfig` (+ seed employees) | cases with IDs, via `ingest_employees`; `corrections` |
| 3 | **Plot** | code | **Giulia** | cases + `RunConfig` | `PlotOutline` |
| 4 | **Event content** | LLM | Robin | cases + `PlotOutline` | `EventContentIn` |
| 5 | **Dates & participants** | code | Valentin | outline + content + cases | `StorylinesIn` → `ingest_storylines` |
| 6 | **Document plan** | code | **Giulia** | cases with dated events | `DocumentPlan` |
| 7 | **Document text** | LLM | Robin | one case + its `CaseDocumentPlan` | `DocumentTextsIn` |
| 8 | **Fill** | code | Valentin | case + `DocumentTextsIn` | `Document.text` filled, via `get_fact` |
| 9 | Export | code | Stylianos | complete cases | PDFs + `import.xml` |

The orchestrator (Mike) calls steps 1–8 in this fixed order with `run_chain`. A
step that returns the wrong shape stops the chain with `ChainError`, naming the
step.

Generation is three Python functions in `pipeline/`:

```python
propose_personas(config: RunConfig, llm: LLMClient) -> PersonasIn
write_event_content(cases: list[Case], outline: PlotOutline, llm: LLMClient) -> EventContentIn
write_document_text(case: Case, plan: CaseDocumentPlan, llm: LLMClient) -> DocumentTextsIn
```

**Seed employees.** A run may start from employees already in the `EmployeesIn`
shape (for example AMEXIO's reference employee 100101). They skip Part 1 and go
straight to CM ID through `map_analysis` (BE-07). Part 1 proposes only
`employeeCount − len(seedEmployees)`.

### Run request (`POST /runs`)

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

A request that carries an `id` anywhere is refused (422). The response holds
`run_id`, `status`, `cases` (each one `case.schema.json` object), `corrections`
and `trace` (§8). Errors have one shape:
`{"error": {"kind", "stage", "message", "field"}}`.

---

## 4. Part 1 → CM ID

**`PersonasIn`** — what the LLM writes, per employee:

| Field | Type | Note |
|---|---|---|
| `firstName`, `lastName` | string | |
| `department` | string | must be in `config.departments` |
| `position` | string | must be in that department's positions |

**Changed in 1.1 (Robin, fix 1):** `contractType` and `hoursPerWeek` are no
longer written by the LLM. They are closed-list or numeric facts (rule 2), and
only code can hit `temporaryShare` and `partTimeShare` exactly. `isManager`
follows from the position (`isManagerRole` in the config), so the LLM does not
write it either.

**CM ID sets, by the HR template's rules:**

| Fact | Rule |
|---|---|
| `contractType` | `Permanent` / `Temporary`, so that `temporaryShare` of the run is `Temporary` (rounded) |
| `hoursPerWeek` | full time, or part time for `partTimeShare` of the run (rounded) |
| `isManager` | from the position's `isManagerRole` |
| `startSalary` | inside the position's `salaryMin`–`salaryMax` |
| `hireDate` | before `asOfDate`; managers have usually been there longest |

CM ID then builds `EmployeesIn` (the existing `input.employees.schema.json`,
unchanged) and calls `ingest_employees`, which assigns personnel numbers and the
`P` and `ORG` IDs. A department or position outside the config becomes a
correction or a refusal, named in `corrections`.

---

## 5. Plot → Event content → Dates & participants

### `PlotOutline` (code, Giulia)

Per employee number, 1–10 **slots**. Each slot has a key from code (`S01`,
`S02`, …) and every value code already decided. No dates, participants or IDs.

```json
{"outlines": [{"employeeNumber": "100101", "slots": [
  {"slot": "S01", "type": "training", "durationDays": 2},
  {"slot": "S02", "type": "appraisal", "year": 2025, "rating": "Meets expectations"},
  {"slot": "S03", "type": "contract_change", "change": "promotion", "newPosition": "Senior Software Developer"},
  {"slot": "S04", "type": "medical_check"}
]}]}
```

Plot picks the closed-list values: appraisal rating, termination reason, the new
position on a promotion. Coherence between events (two weak appraisals before a
dismissal) is a property of the plot, so it stays in code.

**Changed in 1.1 (Robin, fix 2):** **Plot also picks `durationDays`** of a
training (1–5 days in the HR template). It is a stored fact that ends up on the
certificate, so the LLM no longer writes it.

### `EventContentIn` (LLM, Robin)

Per employee number, every slot answered exactly once, by echoing its key:

| Event type | LLM writes | Code decides |
|---|---|---|
| `contract_change` | `reason` (text) | change kind, new position (Plot); date, new salary, contract type, hours (Dates) |
| `training` | `course` (text) | duration (Plot); date, provider (Dates) |
| `appraisal` | `comment` | rating, year (Plot); date 30 June, signer (Dates) |
| `termination` | nothing beyond the summary | reason (Plot); date, notice date (Dates) |
| `absence` | nothing: never a cause | start and end date (Dates) |
| `medical_check` | nothing | date, result (Dates) |
| `hire` | — (not a slot; CM ID adds it) | everything |

Every slot also gets a one-line `summary`.

**Changed in 1.1 (Robin, fix 3):** `summary`, `comment` and `reason` follow
rule 3. No name, date or amount typed out; a person is written as a placeholder.
The persona IDs are known at this point (CM ID ran), so the prompt lists them:

```json
{"content": [{"employeeNumber": "100101", "slots": [
  {"slot": "S01", "summary": "Two-day secure coding course.", "course": "Secure Coding Fundamentals"},
  {"slot": "S02", "summary": "Solid year, steady delivery.",
   "comment": "{{personas.P001.name}} delivered the sprint goals reliably."}
]}]}
```

Checked by `complete_as` with the same placeholder check as Part 3 (§7): every
slot answered once, no unknown or missing slot, no typed-out name, one retry.

### `storylines.json` (code, Valentin)

No longer an LLM output. It is what the Dates & participants step hands to
`ingest_storylines`, so every event has a date. Its shape
(`input.storylines.schema.json`) stays, plus `signedBy` (§6).

---

## 6. `signed_by`

`signed_by` lives **on the event**, as an optional persona ID. Dates &
participants sets it: the manager at the event date, or the director when the
manager has left. A document inherits the signer of its event; recurring
documents without an event (payslips) are signed by the employer as the template
says.

This changes the case-model schema after v1.1, so it becomes **case model v1.2**
(new field `signed_by: str | None` on every event, checked as a persona ID the
case holds; `signedBy` in the storylines input). Needs team agreement before it
is merged.

---

## 7. Document plan → Document text → Fill

### `DocumentPlan` and `CaseDocumentPlan` (code, Giulia)

**Changed in 1.1 (Robin, fix 4):** two names, both defined here.

- `CaseDocumentPlan` — the plan for **one** case: its employee number and the
  documents to write, each with a key from code (`D01`, `D02`, …), its type, its
  event and its sections. This is what `write_document_text` receives.
- `DocumentPlan` — the plan for the **whole run**: a list of `CaseDocumentPlan`.

Built after Dates & participants, when events have IDs.

```json
{"plans": [{"employeeNumber": "100101", "documents": [
  {"doc": "D01", "type": "performance_appraisal", "eventId": "EVT-004", "sections": ["feedback", "summary"]},
  {"doc": "D02", "type": "contract_amendment", "eventId": "EVT-005", "sections": ["cover_letter"]}
]}]}
```

**Which documents get LLM text:** performance appraisal, termination letter,
contract amendment. Employment contract, training certificate, payslip, annual
income statement, medical check and absence report stay templated. One Part 3
call per employee writes all of that dossier's texts together.

### `DocumentTextsIn` (LLM, Robin)

```json
{"employeeNumber": "100101", "documents": [
  {"doc": "D01", "sections": {
    "feedback": "On {{events.EVT-004.date}}, {{personas.P002.name}} reviewed the work of {{personas.P001.name}}.",
    "summary": "..."
  }}
]}
```

### Placeholder syntax (AX-021) and lookup (AX-022)

`{{<collection>.<key>.<field>}}`, a path straight into the case model. Spaces
inside the braces are ignored (`{{ personas.P001.name }}` is the same path). Fill
reads each path with the case model's `get_fact(case, path)`; an unknown path
raises — no silent blank.

| Collection | Key | Example | Value on 100101 |
|---|---|---|---|
| `dossier` | — | `{{dossier.employee_number}}` | `"100101"` |
| `personas` | persona ID | `{{personas.P001.name}}` | `"Jan de Vries"` |
| `organisations` | org ID | `{{organisations.ORG-01.name}}` | the employer |
| `events` | event ID | `{{events.EVT-004.date}}` | the date |
| `documents` | document ID | `{{documents.DOC-001.metadata.document_date}}` | the date |
| `employments` | **persona ID** | `{{employments.P001.salary.amount}}` | `4350.00` |

`employments` is a list, so it is addressed by the employee's persona ID: one
employment per persona; more than one makes the path ambiguous and raises.

The placeholder check runs inside `complete_as` for Part 2 and Part 3: an unknown
collection, key or field fails validation, and so does a name, date or amount
typed out instead of a placeholder. One retry with the bad placeholder named,
then the run fails. Fill (Valentin) resolves every placeholder and rejects any ID
the case does not hold; dates and amounts are formatted only when the text is
filled (AX-025).

---

## 8. LLM client and trace

**Client (Robin implements, everyone calls).** Replaces `generate` from 1.0:

```python
class LLMClient(Protocol):
    def complete(self, prompt: str) -> Completion: ...          # text + token usage
    def complete_as(self, prompt: str, output_model: type[T]) -> T: ...
```

- `complete_as` validates the answer into `output_model`, retries **once** with
  the validation error in the prompt, then raises `LLMError` naming the field.
  The retry lives in the client, so no step implements its own.
- Every call adds one trace line (below). `FakeLLM` has the same interface, so
  every step is tested offline without an API key.
- The API key comes only from an environment variable; `.env` is in
  `.gitignore`; CI runs a secret scan.

**Trace (BE-19, for Mike).** One line per LLM call and per code step, all with
the run ID, so a run can be rebuilt from the trace alone:

```json
{"run_id": "GEN-2026-0001", "stage": "event_content", "kind": "llm",
 "ok": true, "ms": 8421, "model": "...",
 "input_tokens": 3120, "output_tokens": 2480, "retries": 0,
 "cost_eur": 0.047, "error": null}
```

Code steps have `kind: "code"` and no token fields. `cost_eur` is computed from
the tokens and a price table in config, not by the client.

---

## 9. Calls per run

For N employees: ⌈(N − seeds) ÷ 25⌉ (Personas) + ⌈N ÷ 5⌉ (Event content) + N
(Document text), each with at most one retry, plus one or two frontend calls.
For 10 employees: 13 calls, at most 26 with retries.

## 10. Still open

| Question | Who |
|---|---|
| Batch sizes: keep 25 (personas) and 5 (event content), then measure with the school key | Robin, Mike |
| A second human review after Fill | Daniel |
| Exact shape of `RunConfig` and the review screen that edits it | Daniel, Giulia |
| Case model v1.2 (`signed_by`) agreed by the team | all |

## 11. Sign-off

| Owner | Steps | Confirmed |
|---|---|---|
| Daniel | Create analysis → `RunConfig` | ⬜ |
| Robin | Personas, Event content, Document text; LLM client | ⬜ |
| Giulia | CM ID, Plot, Document plan | ⬜ |
| Valentin | Dates & participants, Fill | ⬜ |
| Mike | orchestration (`run_chain`), trace | ⬜ |
| Stylianos | Export | ⬜ |

## 12. Robin's four points (3 Nov) and how 1.1 answers them

| # | Point | Answer in 1.1 |
|---|---|---|
| 1 | `contractType` breaks rule 2; the LLM cannot hit the temporary and part-time shares | `contractType`, `hoursPerWeek` (and `isManager`) move to CM ID (§4) |
| 2 | `durationDays` is the only number the LLM still writes | Plot picks it (§5) |
| 3 | Part 2 text has no name check; the example types "Jan" | Rule 3 and the placeholder check apply to Part 2; example fixed (§5). Valentin's model document to be updated the same way |
| 4 | `CaseDocumentPlan` vs `DocumentPlan` | Both defined: one case vs the whole run (§7) |

## 13. What changes in the code (from 1.0)

| What | Where | Who |
|---|---|---|
| `RunConfig`, `PersonasIn`, `PlotOutline`, `EventContentIn`, `CaseDocumentPlan`, `DocumentPlan`, `DocumentTextsIn`, `TraceLine` + JSON Schemas | `pipeline/contracts.py`, `pipeline/schema/` | Giulia (models of her steps), each owner for theirs |
| `Analysis` kept as the seed-employee input (`EmployeesIn`) | `pipeline/contracts.py`, `pipeline/mapping.py` | Giulia |
| `generate` → `complete` / `complete_as`, one retry, trace line | `pipeline/llm.py` | Robin |
| Personas, Event content, Document plan, Document text added to `STAGES` | `pipeline/chain.py` | Giulia, Mike |
| Placeholder check shared by Part 2 and Part 3 | `pipeline/` | Robin, Valentin |
