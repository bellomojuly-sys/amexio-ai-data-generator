# [DL] Where does the backend run, and how do the stages talk to each other?

Date: 2026-11-05 · Microphase: BE-01 · Study objective: A-I · Decided by: team (Datanova)

## Context — what made the decision necessary

On 26 October the team split the backend into a chain of stages: Daniel's
analysis → **CM ID** (Giulia) → **Plot** (Giulia) → Date & participants
(Valentin) → Fill placeholder (Valentin), with Robin's LLM client used by every
stage. Before anyone builds a stage we must agree **where the code runs** and
**how one stage hands its output to the next**. The facts of a dossier already
live in a Python case model (pydantic, `case_model/`, v1.1), which exposes
`ingest_employees`, `ingest_storylines`, `load_case`, `save_case`. The existing
demo is in TypeScript. The deadline for Review 2 (the chain produces the
reference dossier from an input) is 13 November, so the runtime must be the
least infrastructure that still lets every teammate build and test their stage
this sprint.

## Options

**Option 1 — one Python service hosts the case model; stages are functions
behind one API.**
- Pros: each stage calls the case model directly, in-process
  (`ingest_employees`, `load_case`, …), so there is **one copy of each model**
  and no extra serialization layer between stages; one language for the facts;
  the whole chain is testable offline with a fake LLM; least to run and deploy
  for a five-person student project; one place to validate at each boundary.
- Cons: all stages share one process and one deploy; a stage owner who prefers
  TypeScript (part of Valentin's/Daniel's work) writes Python here; scaling is
  coarse (the whole service, not one stage).

**Option 2 — stages live inside the existing TypeScript demo.**
- Pros: reuses Robin's demo; frontend and stages in one codebase.
- Cons: the case model is Python, so **every stage crosses a language boundary**
  and must re-serialize and re-validate; the "facts live in code" rule would get
  a second copy of the models in TypeScript; calling `ingest_*`/`load_case`/
  `save_case` from TS is awkward; duplicated models drift.

**Option 3 — one service per person.**
- Pros: clear ownership; independent deploys; each person picks their language.
- Cons: a network hop between **every** stage; versioned HTTP contracts plus
  infrastructure is heavy for a team delivering in weeks; the case model would be
  called over HTTP from everywhere; slow and fragile to test end-to-end.

## Decision

**Option 1.** The backend is one Python package, `pipeline/`, that imports and
hosts the case model. Each stage is a Python function with a **typed input and a
typed output** (pydantic). The stages are wired in order behind one entry point.
Communication between stages is **in-process Python objects, validated at each
boundary**, not network calls. Where an output must cross to another owner —
Daniel's analysis coming in, Valentin's dated events going back — it is exchanged
as **validated JSON matching committed JSON Schemas**, next to the case-model
schemas.

## Why

The facts already live in the Python case model. Keeping the stages in the same
process lets every stage call the case model directly, so there is no second
copy of a model and no network layer to maintain; a fake LLM client makes the
whole chain run offline in tests; and it is the least infrastructure for the
team to reach Review 2 on 13 November. Evidence: the case model already exposes
the ingest/load/save contract in Python (`case_model/README.md`); its 139 tests
run offline in under a second (`python3 -m pytest -q`, 2026-11-05).

## Consequences

**My module (Giulia).**
- BE-02 writes the pipeline contract for these in-process stages (owner, input,
  output, and the case-model function each stage uses).
- BE-03 defines stage input/output as pydantic models in `pipeline/contracts.py`,
  with JSON Schemas exported next to the case-model schemas.
- BE-04 (with Robin) is one LLM-client interface (prompt + output model →
  validated object) plus a fake LLM for offline tests.
- BE-05 is a stub chain of the four stages wired in order; its output loads with
  `load_case`, and a stage that returns the wrong shape stops the chain and names
  the stage.

**Teammates.**
- Valentin and Daniel write their stages as Python functions against the
  contract; Daniel's analysis crosses in as validated JSON, Valentin's dated and
  staffed events go back into the case through `ingest_storylines`.
- Robin's LLM client is a Python interface that every stage calls.
- Mike orchestrates one Python process, not several services.

## Evidence

- This Decision Log.
- BE-02 pipeline contract (`docs/PIPELINE_CONTRACT.md`) — to follow.
- Commit: _to fill when committed_.
