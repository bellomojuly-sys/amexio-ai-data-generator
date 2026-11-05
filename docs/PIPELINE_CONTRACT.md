# Backend pipeline contract (v0.1 — draft)

Status: **v1.0 — confirmed**, 5 November 2026 (BE-02). Every owner has confirmed
their row (sign-off below). A change from here needs a new version number.
Runtime decided in BE-01: **one Python service hosts the case model; each stage
is a Python function; stages talk in-process with validated objects** (see
`docs/decisions/BE-01-backend-runtime.md`).

## The chain

```
Daniel            Giulia          Giulia        Valentin            Valentin
 analysis  ─────►  CM ID  ─────►  Plot  ─────►  Date & participants ─────►  Fill placeholder ─────► documents
                     │              │                   │                        │
                     ▼              ▼                   ▼                        ▼
             ingest_employees   (read cases)    ingest_storylines           lookup (AX-022)
```

Robin's LLM client is called by any stage that asks the model something
(CM ID personas, Plot descriptions). The editable **preview layout** sits after
the chain; an edit re-enters the chain at the right stage (M08–M09, later).

## The stages

Each stage is a Python function: **one typed input in, one typed output out**,
validated at the boundary (pydantic). IDs are assigned only by the case model,
never by the LLM.

| # | Stage | Owner | Input | Output | Case-model function it uses |
|---|---|---|---|---|---|
| 1 | Analysis | Daniel | AMEXIO mock data or a description of a reference dossier | `Analysis` — personas, employment facts, company roles (no IDs) | — (first LLM call) |
| 2 | **CM ID** | **Giulia** | `Analysis` | cases with code-assigned IDs + list of corrections | `ingest_employees` |
| 3 | **Plot** | **Giulia** | cases (from CM ID) | one storyline **outline** per case: ordered event types with the LLM's description, **no dates, participants or IDs** | reads the cases (no write) |
| 4 | Date & participants | Valentin | the outline | events with dates and participant IDs | `ingest_storylines` |
| 5 | Fill placeholder | Valentin | the case with full storyline | documents with their texts filled from facts | fact lookup (AX-022) |

## Boundary rules (hold at every arrow)

- **Validate at every boundary**, even if the previous stage already validated:
  an output that does not match the next stage's input model stops the chain and
  names the stage (BE-05).
- **IDs come from code.** Any stage output that carries an `id` is refused
  (AX-012). The case model assigns IDs in CM ID (personas, events) and when
  storylines are ingested.
- **Dates are ISO 8601; amounts are a number + currency** (`Money`). A stage that
  emits `"12/03/2026"` or `"EUR 4.350"` is refused at the boundary.
- **Crossing between owners is validated JSON** matching a committed JSON Schema
  (next to the case-model schemas). In-process the stages pass pydantic objects.

## Placeholder syntax (AX-021)

Agreed with Valentin (Fill placeholder) and Robin, 5 Nov. A document template
holds placeholders `{{ path }}`; the Fill stage reads each `path` from the case
with the case model's `get_fact(case, path)` (AX-022). An unknown path raises —
no silent blank.

`path` is `collection.id.field…`:

| Collection | Key | Example path | Value on 100101 |
|---|---|---|---|
| `dossier` | — | `dossier.employee_number` | `"100101"` |
| `personas` | persona id | `personas.P001.name` | `"Jan de Vries"` |
| `organisations` | org id | `organisations.ORG-01.name` | the employer |
| `events` | event id | `events.EVT-001.date` | `2021-03-01` |
| `documents` | document id | `documents.DOC-001.metadata.document_date` | the date |
| `employments` | **persona id** | `employments.P001.salary.amount` | `4350.00` |

`employments` is a list, so it is addressed by the employee's persona id — one
employment per persona; more than one makes the path ambiguous and raises.
Formatting (long dates, amount + currency) is the Fill stage's job (AX-025); the
case model returns the stored value.

## What is NOT in this contract yet

Error handling and retries per stage (BE-10), the run ID and per-stage trace
(BE-19), and the real-model run (BE-11). Those come in later microphases and
extend this contract with a new version number.

## Sign-off

| Owner | Stage(s) | Confirmed |
|---|---|---|
| Daniel | Analysis | ✅ 5 Nov |
| Giulia | CM ID, Plot | ✅ 5 Nov |
| Valentin | Date & participants, Fill placeholder | ✅ 5 Nov |
| Robin | LLM client used by stages | ✅ 5 Nov |
| Mike | orchestration (one Python process) | ✅ 5 Nov |
