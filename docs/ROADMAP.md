# AMEXIO roadmap — Giulia's module in microphases

Copy for the team repo. The source of truth is `docs/ROADMAP.md` in Giulia's
repo `bellomojuly-sys/amexio-ai-data-generetor-`; the Notion page "AMEXIO
roadmap: my module in microphases" is another copy. The generator bridge plan
(M03b) is in [ROADMAP_BRIDGE.md](ROADMAP_BRIDGE.md).

**Module:** case model, the first two backend stages (CM ID and Plot), domain
configuration, preview interface · **Role:** GenAI Engineer, team Datanova ·
**Made on:** 6 October 2026 · **Rewritten on:** 26 October 2026 (backend split) ·
**Deadline:** code finished by week 16 (18 Dec), delivery by week 20.

72 microphases in 16 milestones (M00–M03, M03b, M04–M13). Each has one change,
one output and one pass/fail check. The reference dossier is AMEXIO's HR
dossier 100101 Jan de Vries. Since 7 October the team focuses on HR.

> Team rule: AI writes, code keeps the facts. My module is where the facts live.

Study objective column: each milestone is a learning objective in
`docs/STUDY-PLAN.md`. A microphase closes when the code works; the objective
closes only when Giulia passes its oral check ("Prova").

## What changed on 26 October 2026

The team split the backend into a chain of stages (whiteboard, 26 Oct):

| Step | Owner | What it does |
|---|---|---|
| Input and analysis (frontend, first LLM call) | Daniel | Takes AMEXIO's mock data or a description of a reference dossier and produces the analysis |
| **CM ID** | **Giulia** | Turns the analysis into cases through the existing case model: code-assigned IDs, personas, employment |
| **Plot** | **Giulia** | Builds the storyline outline of each case: event types in order, with the LLM's description |
| Date & participants | Valentin | Adds dates and participants to the outline, on Giulia's case model |
| Fill placeholder | Valentin | Fills the document texts with facts from the case |
| LLM calls | Robin | The client every stage uses to call the model |
| Preview layout (editable) | later, at the end | Each edit goes back to the LLM and the chain runs again |

Consequences for this roadmap:

- **The case model is not rebuilt.** v1 (and v1.1 from the generator bridge)
  is the base; the backend stages call it (`ingest_employees`,
  `ingest_storylines`, `load_case`, `save_case`). New work is integration: the
  contract between stages and the two stages Giulia owns.
- **Priority: hand teammates what they build on, as early as possible.** The
  pipeline contract (M04) comes first, because Daniel, Valentin and Robin
  depend on it.
- **The preview interface moves to the end** (M12).
- Old M04 (placeholders) is split: syntax and fact lookup stay here (AX-038);
  filling texts belongs to Valentin's Fill placeholder stage.
- Old M11 (second domain) is cut. Old M07+M10 and M12+M13 are merged.
- IDs from AX-021 on were renumbered (no work had started on them). The
  mapping is at the end of this file.

## Status

| Field | Value |
|---|---|
| Completed | M00–M03 (AX-001 → AX-020, plus AX-018a), closed 21 Oct. M03b (case model v1.1 and generator bridge) done 24–26 Oct, except the `v1.1` tag and Robin's two open questions |
| Where the code is | Team repo [bellomojuly-sys/amexio-ai-data-generator](https://github.com/bellomojuly-sys/amexio-ai-data-generator), `main`: case model v1.1 (PR #1 `case-model-v1.1`) and Robin's demo on v1.1 (PR #2 `Demo-Generator`). Tag `v1` → `cf5f963`. This repo's `case_model/` is behind (v1, `5e343f3`); do not build on it |
| Where backend code goes | Team repo, folder `pipeline/` (to confirm in AX-021) |
| **Active** | **AX-021 — decide where the backend runs and how stages talk** |
| Then | AX-022 … AX-026 (pipeline contract, target Fri 30 Oct) |
| Study objectives now | F3 and F8 (needed by M04), then A-I. Still open: ripasso F2, A-A |

## Calendar

| Sprint | Weeks | Dates | Milestones | What exists at the end |
|---|---|---|---|---|
| S2 | 7–8 | 5–16 Oct | M00–M03 | Case model v1 in the team repo; reference dossier loads and validates |
| — | — | 19–23 Oct | Autumn break | M03b done in the break (v1.1, bridge with Robin's demo) |
| S3 | 9–11 | 26 Oct–13 Nov | M04–M07 | **Contract to the team by Fri 30 Oct.** **Review 2 (~13 Nov):** the backend chain produces the reference dossier from an input |
| S4 | 12–13 | 16–27 Nov | M08–M09 | A corrected fact reaches every document; runs are versioned and reload to the same export |
| S5 | 14–16 | 30 Nov–18 Dec | M10–M12 | **Review 3 (~18 Dec):** HR as configuration, batches and edge cases, preview interface. Code freeze |
| — | — | 21 Dec–1 Jan | Christmas break | |
| S6 | 17–18 | 4–15 Jan | M13 | Guide, report sections, demo script |
| Buffer | 19–20 | 18–29 Jan | — | Only fixes and final submission |

Target dates inside Sprint 3 (to be placed in the calendar): M04 Fri 30 Oct ·
M05 Thu 5 Nov · M06 Tue 10 Nov · M07 Fri 13 Nov.

## Sprint 2 — weeks 7–8 (5–16 Oct)

### M00 — Team baseline · study: A-A (review), F8

Closes: TR-01, first part of FR-CM-02 and FR-CM-03.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-001 | ID generator in code (`next_id`) | Function | Two calls never return the same ID | ✅ 2 Oct |
| AX-002 | Persona and Event models, linked by ID | Two typed models | Event stores participant IDs, not names | ✅ 2 Oct |
| AX-003 | First three tests | Test file | Unknown reference is refused; all tests pass | ✅ 2 Oct |
| AX-004 | Move my code into the team repository, in the case-model folder | Commit in the team repo | The three tests pass there | ✅ 7 Oct · `6313d49` |
| AX-005 | Module contract: what the case model takes in and gives out | One-page README | Mike and Daniel or Robin confirm they can use it | ✅ 8 Oct · `81cb937` |

**Gate M00:** passed 8 Oct.

### M01 — Remaining entities · study: A-A (review), F2

Closes: DR-01, DR-03, DR-04, DR-05.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-006 | Organisation model (ORG-01); a professional persona points to an organisation ID | Typed model | Unknown organisation ID fails | ✅ 8 Oct · `729d331` |
| AX-007 | Employment model: position, department, start date, contract type, hours, salary | Typed model | Missing required field fails | ✅ 8 Oct · `729d331` |
| AX-008 | Document model with AMEXIO's five metadata attributes | Typed model | Document with an unknown event ID fails | ✅ 8 Oct · `729d331` |
| AX-009 | Dossier-level facts: employee number, folder title, description | Typed model | Dossier without an employee number fails | ✅ 13 Oct · `729d331` |
| AX-010 | One Case object that holds all the parts | Case container | A full Case validates in one call | ✅ 13 Oct · `729d331` |

**Gate M01:** passed 13 Oct.

### M02 — ID and format rules · study: A-A (review), F2

Closes: FR-CM-02, DR-02, DR-08.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-011 | One ID pattern per entity type (P001, ORG-01, EVT-001, DOC-001), employee number as six digits | Pattern check | An ID with the wrong pattern fails | ✅ 13 Oct · `729d331` |
| AX-012 | Refuse incoming data that already carries an ID | Rejection error | An ID written by the LLM is refused | ✅ 13 Oct · `729d331` |
| AX-013 | Dates stored only as ISO 8601 | Date field rule | "12/03/2026" fails | ✅ 13 Oct · `729d331` |
| AX-014 | Amounts stored as number plus currency | Amount type | The text "EUR 4.350" fails | ✅ 13 Oct · `729d331` |
| AX-015 | Uniqueness test over 100 dossiers | Test | 0 duplicate IDs | ✅ 14 Oct · `c6cfe17` |

**Gate M02:** passed 14 Oct.

### M03 — Reference dossier on disk · study: A-A, F1, F7

Closes: FR-CM-03, first part of FR-CM-05, TR-09.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-016 | Cast and storyline of HR dossier 100101 as data | Fixture | Loads with no error; every participant ID exists | ✅ 14 Oct · `03c2084` |
| AX-017 | The five documents and the dossier facts | Fixture | Every document has its event ID and at least one participant ID | ✅ 14 Oct · `03c2084` |
| AX-018 | Save the case to four files and load it back | Four files | Save, load, compare: the two cases are equal | ✅ 14 Oct · `12c9a2d` |
| AX-018a | Critical review of every test | `case_model/TEST_REVIEW.md`, fixed weak tests | A deliberate break makes the right test fail | ✅ 21 Oct · `5e3edac` |
| AX-019 | Reference dossier as regression test (golden snapshot), CI on every push | Test + CI | A deliberate break in the fixture makes it fail | ✅ 21 Oct · `cf5f963` |
| AX-020 | Hand over case model v1 | Tag `v1` | Generation and export read the reference dossier through my module | ✅ 21 Oct · tag `v1` → `cf5f963` |

**Gate M03:** passed 21 Oct.

### M03b — Case model v1.1 and generator bridge · study: A-A, F2, F8

Inserted on 24 Oct. Full plan in the team repo, `docs/ROADMAP_BRIDGE.md`;
Robin's reply in `docs/HANDOFF_GIULIA.md`.

| ID | Build | Verify | Status |
|---|---|---|---|
| BR (T0–T10) | Closed value sets, typed events, event rules, documents v1.1, ingest of the generator's JSON with code-assigned IDs, reference 100101 rebuilt through ingest, JSON Schemas, fixtures test, handover note | 100 tests green; a deliberate break of four rules fails the right test | ✅ 24 Oct · PR #1 merged |
| R1–R6 | Robin: types from the schemas, demo writes and reads case folders, fixtures, insurance demo removed | Robin's handoff reply | ✅ 24–26 Oct · PR #2 merged |
| BR-14 | The demo renders reference 100101 as AMEXIO's 5 PDFs and `import.xml` | Identical output; removing a fact fails it | ✅ locally (CI skips it: AMEXIO's mock package is not in git) |
| BR-15 | Generator's 100101 vs reference 100101: same facts | A changed salary fails it | ✅ |
| BR-12 | Contract v1.1 in `case_model/README.md`, tag `v1.1` | Tag exists on `main` | ⬜ |
| BR-16 | Answer Robin's two questions: who signs an appraisal when the manager has left; keep document metadata in the demo's cases or leave `documents` empty | Answers written in `docs/HANDOFF_GIULIA.md`; Robin confirms | ⬜ |

**Gate M03b:** BR-12 and BR-16 done. Can run in parallel with AX-021.

## Sprint 3 — weeks 9–11 (26 Oct–13 Nov)

### M04 — Backend pipeline contract · study: A-I, F8, F3 · target Fri 30 Oct

Goal: every teammate can build their stage against a written contract, this
week.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-021 | Decide with the team where the backend runs and how the stages talk. Proposal: one Python service that hosts the case model, stages as functions behind one API. Alternatives: stages in the TypeScript demo; one service per person | Decision Log, agreed by the team | Mike, Robin, Daniel and Valentin agree; the rejected options are written down | ⬜ **active** |
| AX-022 | Pipeline contract `docs/PIPELINE_CONTRACT.md`: the five steps (Daniel's analysis → CM ID → Plot → Date & participants → Fill placeholder), owner, input, output, and the case-model function each one uses | One-page contract | Each owner confirms their row | ⬜ |
| AX-023 | Stage inputs and outputs as Pydantic models (`pipeline/contracts.py`), JSON Schemas exported next to the case-model schemas | Models + schemas | Example payloads validate; a payload that carries an ID written by the LLM fails | ⬜ |
| AX-024 | With Robin: the LLM client interface (one call: prompt + output model → validated object) and a fake LLM for tests | Interface + fake | A stage test runs with the fake, offline, without an API key | ⬜ |
| AX-025 | Stub chain: the four stages as stubs, wired in order, on AMEXIO's example input | Running chain | The output loads with `load_case`; a stage that returns the wrong shape stops the chain and names the stage | ⬜ |
| AX-026 | Hand over: contract, schemas and stub chain pushed; note `docs/HANDOFF_BACKEND.md`; message to Daniel, Valentin, Robin, Mike | Handover note | Daniel and Valentin start their stages without questions | ⬜ |

**Gate M04 (Fri 30 Oct):** the team builds on the contract.

### M05 — Stage CM ID: from the analysis to cases · study: A-I, F3, F5 · target Thu 5 Nov

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-027 | Map Daniel's analysis output to the ingest input (`employees`) | Mapping function | Daniel's sample analysis maps; an unknown field is refused | ⬜ |
| AX-028 | Persona call through Robin's client: prompt and output model without IDs | Prompt + model | With the fake LLM the output validates; an output with an `id` is refused (AX-012) | ⬜ |
| AX-029 | The CM ID stage: analysis → `ingest_employees` → cases with code-assigned IDs and the list of corrections | Stage function | AMEXIO's example in → 4 valid cases; 100101 carries the reference facts | ⬜ |
| AX-030 | Invalid LLM output: one retry, then a clear error; nothing half-written | Error handling | A fake that returns bad JSON twice gives an error that names the field; no case folder is written | ⬜ |
| AX-031 | One run with the real model, trace saved | Trace + run folder | The output loads with `load_case`; the trace is linked in the README as evidence | ⬜ |

**Gate M05:** from an analysis, the backend returns valid cases whose IDs come only from code.

### M06 — Stage Plot: the storyline outline · study: A-I · target Tue 10 Nov

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-032 | Decide with Robin and Mike what moves from the generator's seeded plot into the backend (revisits D9 of the bridge plan) | Decision Log | Both agree; the plot code that stays in the generator is listed | ⬜ |
| AX-033 | Plot output model: per case, the ordered events (type from the closed list, type-specific facts, description), without dates, participants or IDs | Model + schema | An unknown event type fails; an outline that carries an ID fails | ⬜ |
| AX-034 | Event-description call through Robin's client | Prompt + model | The fake-LLM test passes; the real model's answer validates | ⬜ |
| AX-035 | Plot coherence before handover: exactly one `hire`, first; nothing after `termination` | Checks | One deliberate break per rule fails with a clear message | ⬜ |
| AX-036 | The Plot stage: cases → one outline per case | Stage function | On AMEXIO's example, 100101's outline has the reference event types in the reference order | ⬜ |

**Gate M06:** Valentin takes the outline and adds dates and participants without adapting it.

### M07 — Integration: the chain speaks · study: A-I, A-B, F6 · Review 2 (~13 Nov)

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-037 | With Valentin: his dated, staffed events go back into the case through `ingest_storylines` | Events with IDs | Every event loads with `load_case`; an unknown `employeeId` is refused | ⬜ |
| AX-038 | With Valentin: placeholder syntax and fact lookup by path (the function his Fill stage calls) | Written syntax + lookup function | One example works for both sides; an unknown path gives a clear error | ⬜ |
| AX-039 | Full run: Daniel's input → four stages → filled documents for 100101 | End-to-end run | The result's facts equal the reference facts (as in BR-15) | ⬜ |
| AX-040 | A run ID and one trace line per stage | Trace | The run can be reconstructed from the trace alone | ⬜ |
| AX-041 | Contract version and tag `backend-v0.1`; README updated | Tag + README | CI green on `main` | ⬜ |

**Gate M07 (Review 2):** the backend chain produces the reference dossier from an input.

## Sprint 4 — weeks 12–13 (16–27 Nov)

### M08 — Change propagation · study: A-C, F6

Closes: FR-CM-04. From old M05.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-042 | Record which facts each document uses | Usage index | Matches the placeholders counted by hand in one document | ⬜ |
| AX-043 | Change a fact through one function only | Update function | An invalid new value is refused; the old value stays | ⬜ |
| AX-044 | Return the documents and stages affected by a change | List | A fact used nowhere returns an empty list | ⬜ |
| AX-045 | Reference test: correct the gross salary | Test | Exactly the contract and the payslip are re-filled, 0 manual text edits | ⬜ |
| AX-046 | Log every change: what, old value, new value, when | Change log | The log entry matches the change made | ⬜ |

**Gate M08:** one corrected fact reaches every document that uses it.

### M09 — Versioned runs · study: A-D, F4

Closes: FR-CM-05, supports NFR-TRC-01. From old M06.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-047 | Schema version inside every file | Version field | A file without version fails to load | ⬜ |
| AX-048 | One folder per run (GEN-YYYY-NNNN), named from the run ID of AX-040 | Run folder | Two runs never share a folder | ⬜ |
| AX-049 | Reload an old run | Loaded case | Equal to the case that was saved | ⬜ |
| AX-050 | Saving is deterministic | Stable files | Same case saved twice gives identical files | ⬜ |
| AX-051 | With Stylianos: reload a run and export it again | Joint test | The XML is identical | ⬜ |

**Gate M09:** any stored run can be reloaded and gives the same export.

## Sprint 5 — weeks 14–16 (30 Nov–18 Dec)

### M10 — Run configuration and HR template · study: A-E, F8

Closes: FR-CFG-01, FR-CFG-03, FR-CFG-04, first part of FR-CFG-07, DR-11. From old M07 and M10.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-052 | Decide where the line is between domain and scenario | Decision Log, proposed to the team | The team agrees; a teammate classifies two examples the same way | ⬜ |
| AX-053 | Run configuration: domain, scenario, language, target system, and the rule values Robin listed (wage-tax rate, medical-check interval) | Config model + loader | A missing or wrong field fails with a clear message | ⬜ |
| AX-054 | HR template: document types, metadata fields and event types out of the core code | HR template | No HR word is left in core code | ⬜ |
| AX-055 | With Valentin: coherence rules as data (at least 3) | Rules in the template | The validator runs them from the template | ⬜ |
| AX-056 | Reference dossier through template and config | Green regression test | Nothing in the output changed | ⬜ |

**Gate M10:** the HR domain is configuration, not code.

### M11 — Volume and edge cases · study: A-G, F5, F6

Closes: FR-CFG-02, supports BR-08. From old M12 and M13.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-057 | Batch: N dossiers from the config, unique case numbers | Batch run | 0 duplicate case numbers or IDs in 100 dossiers | ⬜ |
| AX-058 | With Mike: time and cost of a 100-dossier run | Two numbers | Reported to the team | ⬜ |
| AX-059 | Two personas with the same name | Test | They stay distinct by ID in every document | ⬜ |
| AX-060 | Delete an entity that is still referenced | Refusal | Nothing is left pointing to a missing ID | ⬜ |
| AX-061 | Error messages name the entity ID and the field | Reworded errors | A teammate fixes a broken fixture without asking me | ⬜ |

**Gate M11:** the backend holds a batch of 100 dossiers and broken input fails loudly.

### M12 — Preview interface and code freeze · study: A-F, A-H, F7 · Review 3 (~18 Dec)

Closes: FR-REV-01 to FR-REV-04. From old M08, M09 and M14, moved to the end on 26 Oct.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-062 | Decide with Daniel where the preview lives (his frontend or separate) and the API it may call | Decision Log + API list | The preview never writes files directly | ⬜ |
| AX-063 | Read-only preview: cast, storyline in time order, one document next to its metadata | Preview | Works for all five reference documents | ⬜ |
| AX-064 | Edit a persona or an event date from the preview; the edit goes through AX-043 and re-runs the affected stages | Edit form | The change appears in every affected document | ⬜ |
| AX-065 | With Valentin: validation errors with a link to the entity | Error list | Every failing check opens the right persona, event or document | ⬜ |
| AX-066 | Test the preview with one person outside my module; fix the biggest problem | Notes + fix | Done in 15 minutes or less; the same person confirms the fix | ⬜ |
| AX-067 | Code freeze for my module | Final tag | All tests green; reference dossier passes | ⬜ |

**Gate M12 (Review 3):** my code is finished.

## Sprint 6 — weeks 17–18 (4–15 Jan)

### M13 — Documentation and handover · study: A-H

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-068 | Guide: how to add a domain | Step-by-step guide | A teammate adds a toy domain by following it | ⬜ |
| AX-069 | Case model and backend stages section for the architecture report | Report section | Stylianos or Mike accepts it into the report | ⬜ |
| AX-070 | Preview part of the user guide | Guide section | Screens in the guide match the real ones | ⬜ |
| AX-071 | Demo script for my part: change one fact, the documents follow | Script | Rehearsed once from start to end | ⬜ |
| AX-072 | Review test with AMEXIO consultants, if they are available | Dated feedback | Result recorded, also if the answer is no | ⬜ |

**Gate M13 (15 Jan):** someone else can use and extend my module without me.

## Buffer — weeks 19–20 (18–29 Jan)

No new microphases. Only fixes from the demo and feedback, and the final submission.

## Decisions on my side

I propose, the team decides. Each one becomes a Decision Log.

| Decision | Where | Needed by |
|---|---|---|
| Generate from a structured case model, or extract metadata from generated text? | Team working principle | Decision Log still to write (task in progress) |
| Case model schema v1, then v1.1 | AX-010, AX-020, M03b | Done |
| Domain focus: HR first | Team decision, 7 Oct | Done |
| Where the backend runs and how stages talk | AX-021 | Wed 28 Oct |
| Who owns the plot: generator or backend Plot stage | AX-032 | Thu 5 Nov |
| Line between domain and scenario | AX-052 | Week 14 |
| Where the preview lives | AX-062 | Week 15 |

## Dependencies on teammates

| Who | What I need or give | Microphases |
|---|---|---|
| Daniel (frontend, analysis) | His analysis output is my CM ID input; preview location | AX-022, AX-027, AX-039, AX-062 |
| Robin (LLM calls, demo) | The LLM client; the plot moving out of the generator; open questions on v1.1 | BR-16, AX-024, AX-028, AX-032, AX-034 |
| Valentin (Date & participants, Fill placeholder) | Takes my outline and case; placeholder syntax and lookup; rules as data | AX-022, AX-033, AX-037, AX-038, AX-055, AX-065 |
| Mike (architecture, orchestration) | Backend runtime; batch run | AX-021, AX-032, AX-058 |
| Stylianos (export, AMEXIO contact) | Reload and re-export | AX-051 |

## Old IDs → new IDs (26 Oct)

| Old | New |
|---|---|
| AX-021, AX-022 (placeholder syntax, lookup by path) | AX-038 |
| AX-023–AX-025 (fill texts, stop on unresolved placeholder, format at fill time) | Valentin's Fill placeholder stage |
| AX-026–AX-030 (change propagation) | AX-042–AX-046 |
| AX-031–AX-035 (versioned storage) | AX-047–AX-051 |
| AX-036–AX-040 (domain/scenario line, run configuration) | AX-052–AX-054 (document types and metadata fields move into the HR template; "run from config" is covered by AX-053 and AX-056) |
| AX-041–AX-050 (review screen and edits) | AX-062–AX-065 |
| AX-051–AX-055 (HR template) | AX-054–AX-056 |
| AX-056–AX-060 (second domain) | Cut |
| AX-061–AX-070 (volume, edge cases) | AX-057–AX-061 |
| AX-071–AX-075 (usability, freeze) | AX-066, AX-067 |
| AX-076–AX-080 (documentation) | AX-068–AX-072 |
| — (new) | AX-021–AX-037, AX-039–AX-041: pipeline contract, CM ID, Plot, integration |

## Stop conditions

Stop and ask Giulia (she talks to the team) if a change:

- alters the case model schema after v1.1 (only by group agreement, with a new version number);
- changes the pipeline contract after AX-026 (same rule);
- adds more than one new concept to the active microphase;
- cannot be checked with a test or a visible output;
- is something Giulia cannot explain herself after the session.

## Maintenance

- Add a microphase instead of making an existing one bigger; insert it where it belongs with a letter suffix (e.g. AX-018a).
- Keep the IDs once work has started.
- Mark complete only with evidence (commit, test run or screenshot).
- Update the Status table after every closed microphase.
