# Backend B1 — proposal for the team (draft)

Draft, 28 October 2026 · author: Giulia (Datanova) · study objective A-I, F3, F8.

**Status: proposal, not a decision.** BE-01 is a Decision Log that the team
takes together (Mike, Robin, Daniel, Valentin). This document is what I bring to
the meeting: a recommended runtime (part 1) and a first pipeline contract (part
2) so each owner can confirm their row. The pipeline contract becomes the
official `docs/PIPELINE_CONTRACT.md` in the team repo only once agreed (BE-02);
after that it changes only by group agreement with a new version number.

Targets: BE-01 Wed 29 Oct · B1 contract to the team Fri 30 Oct.

---

## Part 1 — BE-01: where the backend runs and how the stages talk

### The question

The chain is: Daniel's analysis → **CM ID** → **Plot** → Date & participants →
Fill placeholder → (preview). The case model is Python + Pydantic. Robin's LLM
client is TypeScript in the browser. We must decide **one** runtime for the
stages and **one** way they pass data.

### Recommended option — A: one Python service, stages as functions behind one API

- The case model and the four stages live in **one Python service** (folder
  `pipeline/` in the team repo). Each stage is a **function** with a typed input
  and a typed output; the service calls them in order in the same process.
- The boundaries between stages are **validated Pydantic models** (JSON over the
  wire for the frontend). Daniel's frontend calls the service over **HTTP/JSON**
  (one endpoint to run the chain, plus the review pauses later in M09).
- The **LLM client** is a small Python interface that mirrors Robin's
  `complete()` (see part 2 §"LLM client"), with a `FakeLLM` for tests.
- Robin's TypeScript demo keeps working on its own and can later call the same
  service instead of its in-browser pipeline.

**Why this one**
- The case model is Python/Pydantic; Robin showed the browser **cannot** host it
  (Pyodide can't fetch the runtime in the hosted page — his default 4). A Python
  service is where the facts already live.
- One process, functions in order = the simplest thing that can validate every
  boundary and keep IDs in code (A-I). No network between our own stages.
- It matches the team's own picture ("the final hub has a backend", Robin) and
  Mike's orchestration role.

**Cost / risk:** we must stand up a small service (FastAPI) and agree the HTTP
shape with Daniel. Kept minimal, this is a day of work, not a sprint.

### Alternatives (write-down for the Decision Log)

- **B: stages in Robin's TypeScript demo.** Rejected: the case model is Python;
  the browser can't run it (Pyodide caveat); we'd duplicate the ingest/validate
  logic in TS and fight to keep the two copies in step. The one thing it saves —
  no service — is the thing Robin says we need anyway.
- **C: one service per person (microservices).** Rejected: network contracts
  between every stage, deployment and latency overhead, far too much for a
  five-person student project on a week-20 deadline. Revisit only if a stage
  ever needs to scale on its own (it won't).

### What the team must confirm
1. Runtime = one Python service in `pipeline/` (option A)? — **Mike, Robin,
   Daniel, Valentin**
2. Frontend ↔ backend = HTTP/JSON, one "run" endpoint for now? — **Daniel, Mike**
3. The LLM client is a Python mirror of Robin's interface, owned with Robin? —
   **Robin**

---

## Part 2 — BE-02: the pipeline contract (first draft)

One row per step: owner, what goes in, what comes out, and the case-model
function the step uses. **Each owner confirms their row.**

| # | Step | Owner | Input | Output | Case-model function |
|---|---|---|---|---|---|
| 0 | Input & analysis | Daniel | AMEXIO mock data, or a description of a reference dossier | `analysis` (structured: company + a list of employees with HR facts, no IDs) | — (feeds step 1) |
| 1 | **CM ID** | **Giulia** | `analysis` | `employees.json` shape → cases with **code-assigned IDs** + `corrections` | `ingest_employees` |
| 2 | **Plot** | **Giulia** | the cases from step 1 | one **storyline outline** per case: ordered typed events (type from the closed list, type-specific facts, LLM description) — **no dates, no participants, no IDs** | builds the outline; `ingest_storylines` is called in step 3 |
| 3 | Date & participants | Valentin | the outlines + the cases | dated, staffed events written back into each case | `ingest_storylines` |
| 4 | Fill placeholder | Valentin | the case + document templates | filled document texts | fact lookup (`AX-022`) + placeholders (`AX-021`) |
| — | Preview layout | at the end | a filled dossier | reviewer edits | an edit re-enters the chain from the right step (M09) |

### Contract conventions (hold at every boundary)

1. **Every boundary is a validated Pydantic model**, and its JSON Schema is
   exported next to the case-model schemas (BE-03). A payload that carries an
   `id` written by the LLM is **refused** (AX-012).
2. **IDs are assigned only by code**, never by the LLM. Dates are **ISO 8601**.
   Amounts are **`Money`** (a number as a string + a currency), never formatted
   text.
3. **Each stage validates its own input**, even though the previous stage
   already validated — a boundary never trusts the stage before it (A-I prova).
4. **Errors use Robin's taxonomy**: `setup` (fix config) · `retry` (try again) ·
   `refused` (change the request) · `cancelled`. Domain errors (a value outside
   a closed list) are distinct from technical failures (the model timed out).
5. **Bad LLM output → one retry, then fail loud** (BE-10): a clear error that
   names the field, and **nothing half-written** (no partial case folder). This
   is the opposite of the demo, which fills in basics — deliberate, because the
   backend must produce valid cases or none.
6. **Observability / monitoring** (BE-19, **owned by Mike**): one **run ID** per
   run and **one trace line per stage**, so a run can be reconstructed from the
   trace alone (F6). The `POST /runs` response and the orchestrator carry this
   trace.

### LLM client (BE-04, with Robin)

A thin interface, the Python mirror of `src/ai/types.ts`:

```
complete(system, prompt, *, max_tokens=None) -> str          # thin transport
complete_as(model, system, prompt) -> <validated model>      # parse + validate + ONE retry (BE-10)
```

A **runnable draft** of this interface — `LLMClient`, `complete_as` (the
one-retry gate), `LLMError` with Robin's four error kinds, and a `FakeLLM` for
offline tests — is in `docs/backend_b1/llm_client_interface.py`. Run it:
`python3 docs/backend_b1/llm_client_interface.py`.

- `complete_as` is where parsing (Robin's `extractJson` logic), Pydantic
  validation and the single retry live, so every stage receives a validated
  object and no stage repeats the retry code.
- A `FakeLLM` returns canned answers (per prompt) for tests — the whole chain
  runs **offline, without an API key**, and a `FakeLLM` that returns bad JSON
  twice must produce the BE-10 error with no case folder written.
- Reuse Robin's prompt text and the SYSTEM injection defence for the CM ID and
  Plot prompts.

### Open questions to route at the meeting

| Question | Microphase | Owner(s) |
|---|---|---|
| Confirm runtime = one Python service (Part 1) | BE-01 | Mike, Robin, Daniel, Valentin |
| Placeholder syntax — propose `{{personas.P001.name}}` | AX-021 | Valentin, Robin |
| What plot logic moves from the generator into the Plot stage (who leaves, sick leave, appraisal years, medical checks currently stay in the generator) | BE-12 | Robin, Mike |
| What each trace line holds, so a run can be reconstructed (monitoring) | BE-19 | Mike |
| Who signs an appraisal when the manager has left; keep document metadata in the demo's cases or leave `documents` empty | **BR-16** (still open) | Giulia + team |
| Shape of Daniel's `analysis` output = my CM ID input | BE-02/BE-07 | Daniel, Giulia |

---

## Part 3 — the LLM↔CM alternation and the orchestrator

The chain is an **alternation**: `LLM → CM → LLM → CM → LLM → CM`. The LLM
proposes facts; the case model (CM) is the gate after every call. This is a
**fixed pipeline, not an agent** — the *code* decides the order of stages, the
LLM only fills in facts at its step (A-I: "a staged pipeline vs an agent that
decides on its own").

Three principles make the alternation work and run automatically:

1. **The case model is the state that flows through the backend.** Not files
   handed between parts: inside the service there is one `Case` (a list of
   `Case`s) that **is the truth**, and each stage enriches it. The complete case
   model is the backbone, not a side tool — which is why the runtime is one
   Python service that hosts it (Part 1, option A).
2. **Between every LLM call there is a CM gate.** Each `LLM → CM` arrow is a
   validation gate: the LLM proposes, the case model **assigns IDs, normalizes,
   records corrections, checks the rules and stores**. "AI writes, the code
   keeps the facts", enforced at each boundary. The LLM never holds canonical
   state.
3. **The prompt for stage N+1 is built from the CM state after stage N**, not
   from the previous LLM's raw text. The storyline prompt is built from the
   employees the *case model* created (with their code-assigned IDs). This is
   what makes it one chain and not two unrelated calls.

### The alternation for AMEXIO

```
Daniel        LLM                 CM                    LLM                  CM                       LLM               CM
analysis ──▶ personas ──▶ ingest_employees ──▶ plot + descriptions ──▶ ingest_storylines ──▶ document text ──▶ lookup/validate
            (proposes)    (IDs, normalize,      (proposes typed       (dates + participants,   (writes bodies)   (facts verified)
                           corrections, store)    events + text)        rules, store)
              └─ gate ───────┘        └──────── gate ────────┘             └──────── gate ────────┘
                  │                            │                                 │
            ── Giulia: CM ID ──       ── Giulia: Plot ──              ── Valentin: Date & participants / Fill ──
```

Giulia owns the first two links; Valentin the later ones; both work on the
**same `Case` objects through the same case-model functions.** The contract
guarantees the `Case` that leaves Giulia's stages is exactly what Valentin's
stages expect.

### The orchestrator (schematic — real code written with guidance, BE-05)

The "platform" is **one loop** over a fixed list of stages. The automatism is
the loop; the `LLM → CM` pair lives inside each stage.

```
run_pipeline(analysis, llm):
  1.  state = empty(run_id)                      <- the case model IS the state
  2.  for stage in [CM_ID, Plot, Dates, Fill]:   <- fixed order (code, not the LLM)
  3.      state = stage(state, llm)              <- stage = LLM proposes -> CM gate
  4.      validate(state)                        <- gate: Pydantic + case-model rules
  5.      trace(state)                           <- one line per stage (BE-19)
  6.  return state                               <- valid cases, or an error, never half
```

One stage, in one line:

```
stage(state, llm) = ingest_*( llm.complete_as(Model, prompt_from(state)) ) -> new state
                    └── CM gate ──┘  └──────── LLM proposes ────────┘
```

A runnable draft of the client (`complete`, `complete_as` with the one-retry
gate, and a `FakeLLM`) is in `docs/backend_b1/llm_client_interface.py` — to show
Robin for BE-04.

- **The case model is `RunState.cases`** — embedded whole, carried from stage to
  stage, never duplicated.
- **Human review** (M08/M09) is a pause between stages:
  `LLM → CM → [review?] → LLM → CM → …`.
- **Robin sends the right data** because the first gate has a fixed input schema
  (`input.employees.schema.json`, `input.storylines.schema.json`, already
  committed). His client's answer must validate against it; the case model
  refuses anything else (an LLM-written `id`, an unknown field). No trust
  needed — the schema is the gate.

---

## Part 4 — HTTP contract frontend ↔ backend (for Daniel), draft

Daniel's frontend calls the one Python service (Part 1, option A). One
synchronous endpoint runs the whole chain for B1/B4; the review-pause endpoints
come with M09. **Daniel confirms this part.**

### Conventions

- JSON over HTTP, UTF-8. Dates are ISO 8601; amounts are `Money`
  (`{"amount": "4350.00", "currency": "EUR"}`).
- Every response that carries cases uses **`case.schema.json`** (already
  committed) — no second shape to agree.
- **IDs come only from the backend.** A request that carries an `id` is refused
  (422), same rule as ingest (AX-012).
- **Errors always have one shape**, with Robin's four kinds:
  ```json
  {"error": {"kind": "setup|retry|refused|cancelled",
             "stage": "cm_id", "message": "...", "field": "employees.0.contractType"}}
  ```

### POST /runs — run the chain

Request:
```json
{
  "analysis": { "...": "Daniel's analysis output; exact shape agreed in BE-07" },
  "config":   { "...": "optional run settings (M07): as-of date, document types" },
  "options":  { "fake_llm": false }
}
```
`options.fake_llm = true` makes the run use the `FakeLLM` — offline, no API key,
for tests and demos.

Response `200`:
```json
{
  "run_id": "GEN-2026-0001",
  "status": "completed",
  "cases": [ { "...": "one object of case.schema.json per employee" } ],
  "corrections": [ {"step": "cm_id", "employee_id": "100101", "message": "..."} ],
  "trace": [ {"stage": "cm_id", "ok": true, "ms": 1234, "llm": "claude-... via ..."} ]
}
```

Errors (HTTP status + `error.kind`):

| Status | kind | When |
|---|---|---|
| 422 | `refused` | the analysis/config did not validate, or a domain refusal (value outside a closed list, an LLM-written `id`); `error.field` and `error.stage` say where |
| 503 | `retry` | the model was unreachable or rate-limited after the one retry (BE-10) |
| 400 | `setup` | bad config (missing key, unknown model) |

On any error, **nothing is half-written** — no partial case is returned (BE-10).

### If a full run is too slow (LLM latency): async variant

- `POST /runs` → `202 {"run_id", "status": "running"}`
- `GET /runs/{run_id}` → `{status: running|completed|failed, cases?, corrections?, trace?, error?}`

Decide at the meeting: **synchronous first**, switch to async only if a real run
is too slow for the frontend to wait.

### Later (M08/M09) — review pauses, not in B1

The chain stops after personas and after the storyline, returns the
intermediate cases, accepts edits, and resumes. Sketch, to agree with Daniel and
Mike when M09 lands: `GET /runs/{id}/pending`, `POST /runs/{id}/edits`,
`POST /runs/{id}/resume`.

### What Daniel confirms
1. The shape of `analysis` (BE-07) = my CM ID input.
2. Synchronous `POST /runs` for now (async only if needed)?
3. One "run" endpoint vs one endpoint per stage — I propose one run endpoint.

---

## What is NOT in this draft (on purpose)

- **No Pydantic code yet** (`pipeline/contracts.py` is BE-03): the models are
  written only after the team agrees the rows above, and I write them with
  guidance so I can explain each one.
- **No stub chain yet** (BE-05): it comes after BE-03/BE-04.
- This draft does not change the case-model schema or close any microphase. It
  is the input to the BE-01 decision and the BE-02 contract.
