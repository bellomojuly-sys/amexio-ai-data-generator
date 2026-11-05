# Backend pipeline contract (v0.1 — draft)

Status: **draft**, 5 November 2026 (BE-02). Every owner confirms their row
before it becomes v1.0 (gate B1, Fri 30 Oct target — now catching up). Runtime
decided in BE-01: **one Python service hosts the case model; each stage is a
Python function; stages talk in-process with validated objects** (see
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

## What is NOT in this contract yet

Error handling and retries per stage (BE-10), the run ID and per-stage trace
(BE-19), the real-model run (BE-11), and the placeholder **syntax** itself
(AX-021, agreed with Valentin and Robin). Those come in later microphases and
extend this contract with a new version number.

## Sign-off

| Owner | Stage(s) | Confirmed |
|---|---|---|
| Daniel | Analysis | ☐ |
| Giulia | CM ID, Plot | ☐ |
| Valentin | Date & participants, Fill placeholder | ☐ |
| Robin | LLM client used by stages | ☐ |
| Mike | orchestration (one Python process) | ☐ |
