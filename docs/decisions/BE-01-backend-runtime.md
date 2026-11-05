# [DL] Where the backend runs and how the stages talk

Date: 2026-11-05 · Microphase: BE-01 · Study objective: A-I (software design and
contracts: F8) · Decided by: team (Mike, Robin, Daniel, Valentin, Giulia),
agreed at the meeting of Friday 30 October 2026.

## Context

On 26 October the team split the backend into a fixed chain of stages
(Daniel's analysis → CM ID → Plot → Date & participants → Fill placeholder →
preview). The case model is Python + Pydantic and is the only component that
holds the facts and assigns the IDs. Robin's LLM client and demo are TypeScript
in the browser. Before anyone could build a stage we had to decide **one**
runtime for the stages and **one** way they pass data to each other, so that
each owner can build against a written contract. The full proposal brought to
the meeting is `docs/backend_b1/BACKEND_B1_PROPOSAL.md` (28 October draft).

## Options

**A — One Python service; stages as functions behind one API.**
The case model and the stages live in one Python service (folder `pipeline/`).
Each stage is a function with a typed input and output; the service (the
orchestrator) calls them in order in the same process. Every boundary is a
validated Pydantic model. Daniel's frontend talks to the service over HTTP/JSON
(one "run" endpoint, plus the review pauses later in M09).
- *Pros:* the facts already live in Python, so no second copy of the
  ingest/validate logic; one deploy; every boundary between our own stages is a
  plain function call that can validate and keep IDs in code (A-I), with no
  network in between; it is simpler to run and test than several services that
  call each other; matches Mike's orchestration role.
- *Cons:* every stage must be Python and share one process; no independent
  deploy per person. We must stand up a small service (FastAPI) and agree the
  HTTP shape with Daniel.

**B — Stages inside Robin's TypeScript demo.**
- *Pros:* reuses the existing demo/runtime; no new service.
- *Cons:* the case model is Python and the browser cannot host it (Robin showed
  Pyodide cannot fetch the runtime in the hosted page). We would have to
  duplicate the ingest/validate logic in TypeScript and keep two copies in step
  — against the team rule that the case model is the single home of the facts.

**C — One service per person (microservices).**
- *Pros:* each owner picks a language and deploys independently; a stage could
  scale on its own.
- *Cons:* a network contract, serialization, deployment and latency between
  every stage; end-to-end runs far harder to test; far too much for a
  five-person student project on a week-20 deadline. No stage needs to scale on
  its own.

## Decision

**Option A.** One Python service in `pipeline/` (team repo); the stages are
functions called in a fixed order in the same process, every boundary a
validated Pydantic model; Daniel's frontend talks to it over HTTP/JSON.

## Why

One service is simpler than several that talk to each other: no network
contract, versioning or serialization between our own stages, which is where the
complexity and the bugs would be. The case model is already Python and must stay
the only component that holds the facts and assigns the IDs (AX-012); putting the
stages next to it as in-process functions keeps every boundary a validated call
and keeps IDs in code, which is exactly what the chain has to guarantee (A-I).
Options B and C were rejected for the reasons above — B breaks the single home of
the facts, C adds cost the project cannot carry.

Evidence: team agreement at the meeting of 30 October 2026; proposal
`docs/backend_b1/BACKEND_B1_PROPOSAL.md` and Robin's review
`docs/backend_b1/ROBIN_REVIEW.md`; the pipeline contract that implements this
decision is `docs/PIPELINE_CONTRACT.md` v0.2 (BE-02).

## Consequences

**My module.** The backend lives in the team repo under `pipeline/`. The stages
import and call the case model (`ingest_employees`, `ingest_storylines`,
`load_case`, `save_case`); they do not rebuild it. The case-model schema does not
change because of this decision. Stage boundaries are Pydantic models whose JSON
Schemas are exported next to the case-model schemas (BE-03). The orchestrator
runs steps in one fixed order and carries a run ID and one trace line per step
(BE-19).

**Teammates.** Daniel's analysis and Valentin's Date/Fill stages are Python
functions that match their rows in the contract (BE-02/BE-03); Robin's LLM client
is one Python interface with a fake for tests (BE-04); Mike orchestrates the one
service. A component that is not Python (Daniel's frontend) integrates over the
HTTP/JSON contract, not by sharing the process.

## Evidence

- This Decision Log, committed on branch `giulia/backend-b1`.
- Proposal and review: `docs/backend_b1/BACKEND_B1_PROPOSAL.md`,
  `docs/backend_b1/ROBIN_REVIEW.md` (branch `giulia/backend-b1-proposal`).
- Contract implementing the decision: `docs/PIPELINE_CONTRACT.md` v0.2 (PR #4).
