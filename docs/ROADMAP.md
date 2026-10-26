# AMEXIO roadmap — Giulia's module in microphases

Copy for the team repo. The source of truth is `docs/ROADMAP.md` in Giulia's
repo `bellomojuly-sys/amexio-ai-data-generetor-`; the Notion page "AMEXIO
roadmap: my module in microphases" is another copy. The generator bridge plan
(M03b) is in [ROADMAP_BRIDGE.md](ROADMAP_BRIDGE.md).

**Module:** case model, domain configuration, review interface, and since
26 October the first two backend stages (CM ID and Plot) · **Role:** GenAI
Engineer, team Datanova · **Made on:** 6 October 2026 · **Rewritten on:**
26 October 2026 (backend added) · **Deadline:** delivery by week 20.

Three groups of microphases: the 80 case-model microphases (AX-001 … AX-080,
plus AX-018a, milestones M00–M15), the generator bridge (M03b, BR-xx) and 20
backend microphases (BE-01 … BE-20, milestones B1–B4). Each has one change, one output and one
pass/fail check. The reference dossier is AMEXIO's HR dossier 100101 Jan de
Vries. Since 7 October the team focuses on HR.

> Team rule: AI writes, code keeps the facts. My module is where the facts live.

Study objective column: each milestone is a learning objective in
`docs/STUDY-PLAN.md`. A microphase closes when the code works; the objective
closes only when Giulia passes its oral check ("Prova").

## How this roadmap is ordered (26 October 2026)

On 26 October the team split the backend into a chain of stages:

| Step | Owner | What it does |
|---|---|---|
| Input and analysis (frontend, first LLM call) | Daniel | Takes AMEXIO's mock data or a description of a reference dossier and produces the analysis |
| **CM ID** | **Giulia** | Turns the analysis into cases through the existing case model: code-assigned IDs, personas, employment |
| **Plot** | **Giulia** | Builds the storyline outline of each case: event types in order, with the LLM's description |
| Date & participants | Valentin | Adds dates and participants to the outline, on Giulia's case model |
| Fill placeholder | Valentin | Fills the document texts with facts from the case |
| LLM calls | Robin | The client every stage uses to call the model |
| Preview layout (editable) | at the end | Each edit goes back to the LLM and the chain runs again |

Two rules decide the order:

1. **The case model keeps all its planned work.** The backend is added; nothing
   of the case model is cut or simplified. The backend stages call the case
   model (`ingest_employees`, `ingest_storylines`, `load_case`, `save_case`);
   they do not rebuild it.
2. **What teammates depend on comes first.** Part A closes every microphase
   that Daniel, Valentin, Robin or Mike wait for. Part B is the rest of the case
   model, in the original order, with the preview interface at the end.

| Part | What | When |
|---|---|---|
| **A — for the team** | BR-12, BR-16 (case model v1.1 closed for Robin) · B1 pipeline contract · AX-021, AX-022 (placeholder syntax and lookup, for Valentin's Fill stage) · B2 stage CM ID · B3 stage Plot · B4 integration | Sprint 3, 26 Oct–13 Nov |
| **B — the case model** | BR-00, BR-01, BR-09 (bridge, our side) · M04 rest · M05–M07 · M10 · M12–M13 · then the review interface M08–M09 · M14–M15. M11 (second domain) only if time allows | Sprint 4 → Sprint 6 |

IDs: the case-model IDs AX-021 … AX-080 stay as they were; backend microphases
have their own prefix (BE-), as the bridge has BR-.

## Status

| Field | Value |
|---|---|
| Completed | M00–M03 (AX-001 → AX-020, plus AX-018a), closed 21 Oct. M03b partly: the handoff sprint (BR-02 … BR-08, BR-10, BR-11, BR-13), Robin's R1–R6, BR-14 (locally) and BR-15 |
| Where the code is | Team repo [bellomojuly-sys/amexio-ai-data-generator](https://github.com/bellomojuly-sys/amexio-ai-data-generator), `main`: case model v1.1 (PR #1 `case-model-v1.1`) and Robin's demo on v1.1 (PR #2 `Demo-Generator`). Tag `v1` → `cf5f963`; no `v1.1` tag yet. This repo's `case_model/` is an older copy (v1); do not build on it |
| Where backend code goes | Team repo, folder `pipeline/` (to confirm in BE-01) |
| **Active** | **BE-01 — decide where the backend runs and how stages talk**, with BR-12 and BR-16 alongside |
| Then | BE-02 … BE-06 (pipeline contract to the team by Fri 30 Oct), then AX-021, AX-022 |
| Study objectives now | F3 and F8 (needed by B1), then A-I. Still open: ripasso F2, A-A |

## Calendar

| Sprint | Weeks | Dates | Milestones | What exists at the end |
|---|---|---|---|---|
| S2 | 7–8 | 5–16 Oct | M00–M03 | Case model v1 in the team repo; reference dossier loads and validates |
| — | — | 19–23 Oct | Autumn break | Most of M03b done (v1.1, bridge with Robin's demo) |
| S3 | 9–11 | 26 Oct–13 Nov | **Part A:** BR-12, BR-16, B1, AX-021–AX-022, B2, B3, B4 | **Contract to the team by Fri 30 Oct.** **Review 2 (~13 Nov):** the backend chain produces the reference dossier from an input |
| S4 | 12–13 | 16–27 Nov | **Part B:** BR-00, BR-01, BR-09, M04 (AX-023–AX-025), M05, M06 | Reference dossier checked against AMEXIO's files; placeholders complete; a corrected fact reaches every document; versioned runs |
| S5 | 14–16 | 30 Nov–18 Dec | M07, M10, M12, M13 | **Review 3 (~18 Dec):** run from config, HR as a template, batches, edge cases |
| — | — | 21 Dec–1 Jan | Christmas break | |
| S6 | 17–18 | 4–15 Jan | M08, M09, M14, M15 | Review interface (preview) read-only and with edits, usability test, **code freeze**, guide, report sections, demo script |
| Buffer | 19–20 | 18–29 Jan | (M11 only if ahead) | Only fixes and final submission |

Target dates in Part A (to be placed in the calendar): BR-12, BR-16 Wed 28 Oct ·
B1 Fri 30 Oct · AX-021, AX-022 Tue 3 Nov · B2 Thu 5 Nov · B3 Tue 10 Nov ·
B4 Fri 13 Nov.

**Risk.** Adding the backend without cutting the case model moves the code
freeze from 18 Dec (old plan) to 15 Jan, and Sprint 6 holds 20 microphases in
two weeks. If Part B slips, cut in this order: M11 (already a stretch goal),
then AX-073–AX-074 (usability test and fixes), never the gates that teammates
or the reviews depend on. Discuss at the weekly meeting.

## Sprint 2 — weeks 7–8 (5–16 Oct) · done

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
| AX-008 | Document model with AMEXIO's five metadata attributes (Employee ID, Document Type, Document Date, Confidential, Tags) | Typed model | Document with an unknown event ID fails | ✅ 8 Oct · `729d331` |
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
Robin's reply in `docs/HANDOFF_GIULIA.md`. BR-12 and BR-16 are in Part A
(Robin waits for them); BR-00, BR-01 and BR-09 are in Part B.

| ID | Build | Verify | Status |
|---|---|---|---|
| BR-00 | Fact sheet of AMEXIO's 100101: every value printed in the 5 PDFs and in `import.xml`, with its source and the case field or rule that holds it | Every row names a file and a case field or rule | ⬜ Part B |
| BR-01 | Decisions D1–D9 of the bridge plan written as Decision Logs (D1–D4 decided 24 Oct, D5–D9 confirmed by Robin) | Each has a reason and a rejected alternative | ⬜ Part B |
| BR-02, BR-03 | = AX-011a/b: strict ID regexes; `Case` checks every ID's pattern | `"P001\n"` fails; a loaded case with persona id `"banana"` fails | ✅ 24 Oct |
| BR-04 … BR-08 | Closed value sets, typed events, event rules, manager/examiner/provider as parts of the case, documents v1.1 | One deliberate break per rule fails the right test | ✅ 24 Oct · PR #1 |
| BR-09 | Reference dossier 100101 rebuilt through ingest; golden regenerated | Golden test green | ✅ provisional · confirm every value against BR-00 in Part B |
| BR-10, BR-11 | JSON Schemas committed; fixtures test with `load_case` in CI | A broken fixture fails | ✅ 24 Oct · PR #1 |
| BR-12 | Contract v1.1: README status line updated (it still says "on branch"), tag `v1.1` on `main` | Tag exists on `main` | ⬜ Part A |
| BR-13 | Handover note to Robin (`docs/HANDOFF_ROBIN.md`) | Robin starts R1–R3 without questions | ✅ 24 Oct |
| R1–R6 | Robin: types from the schemas, demo writes and reads case folders, fixtures, insurance demo removed | Robin's reply | ✅ PR #2 |
| BR-14 | The demo renders 100101 as AMEXIO's 5 PDFs and `import.xml` | Identical output; removing a fact fails it | ✅ locally (CI skips it: AMEXIO's mock package is not in git) |
| BR-15 | Generator's 100101 vs reference 100101: same facts | A changed salary fails it | ✅ |
| BR-16 | Answer Robin's two questions: who signs an appraisal when the manager has left; keep document metadata in the demo's cases or leave `documents` empty | Answers in `docs/HANDOFF_GIULIA.md`; Robin confirms | ⬜ Part A |

**Gate M03b:** BR-00, BR-01, BR-09 (checked), BR-12 and BR-16 done; tag `v1.1`.

# Part A — what the team depends on (Sprint 3, 26 Oct–13 Nov)

### Case model v1.1 closed for Robin · target Wed 28 Oct

BR-12 and BR-16 (table above). They can run alongside BE-01.

### B1 — Backend pipeline contract · study: A-I, F8, F3 · target Fri 30 Oct

Goal: every teammate can build their stage against a written contract, this week.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| BE-01 | Decide with the team where the backend runs and how the stages talk. Proposal: one Python service that hosts the case model, stages as functions behind one API. Alternatives: stages in the TypeScript demo; one service per person | Decision Log, agreed by the team | Mike, Robin, Daniel and Valentin agree; the rejected options are written down | ⬜ **active** |
| BE-02 | Pipeline contract `docs/PIPELINE_CONTRACT.md`: the five steps (Daniel's analysis → CM ID → Plot → Date & participants → Fill placeholder), owner, input, output, and the case-model function each one uses | One-page contract | Each owner confirms their row | ⬜ |
| BE-03 | Stage inputs and outputs as Pydantic models (`pipeline/contracts.py`), JSON Schemas exported next to the case-model schemas | Models + schemas | Example payloads validate; a payload that carries an ID written by the LLM fails | ⬜ |
| BE-04 | With Robin: the LLM client interface (one call: prompt + output model → validated object) and a fake LLM for tests | Interface + fake | A stage test runs with the fake, offline, without an API key | ⬜ |
| BE-05 | Stub chain: the four stages as stubs, wired in order, on AMEXIO's example input | Running chain | The output loads with `load_case`; a stage that returns the wrong shape stops the chain and names the stage | ⬜ |
| BE-06 | Hand over: contract, schemas and stub chain pushed; note `docs/HANDOFF_BACKEND.md`; message to Daniel, Valentin, Robin, Mike | Handover note | Daniel and Valentin start their stages without questions | ⬜ |

**Gate B1 (Fri 30 Oct):** the team builds on the contract.

### M04 (first part) — Placeholder syntax and fact lookup · study: A-B · target Tue 3 Nov

Valentin's Fill placeholder stage calls these two, so they move into Part A.
The rest of M04 is in Part B.

Closes: first part of FR-CM-01. Supports FR-GEN-04.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-021 | Agree the placeholder syntax with Valentin (Fill placeholder) and Robin (e.g. `{{personas.P001.name}}`) | Written agreement in the pipeline contract | One example works for both sides | ⬜ |
| AX-022 | Read one fact by its path | Lookup function | Unknown path gives a clear error | ⬜ |

### B2 — Stage CM ID: from the analysis to cases · study: A-I, F3, F5 · target Thu 5 Nov

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| BE-07 | Map Daniel's analysis output to the ingest input (`employees`) | Mapping function | Daniel's sample analysis maps; an unknown field is refused | ⬜ |
| BE-08 | Persona call through Robin's client: prompt and output model without IDs | Prompt + model | With the fake LLM the output validates; an output with an `id` is refused (AX-012) | ⬜ |
| BE-09 | The CM ID stage: analysis → `ingest_employees` → cases with code-assigned IDs and the list of corrections | Stage function | AMEXIO's example in → 4 valid cases; 100101 carries the reference facts | ⬜ |
| BE-10 | Invalid LLM output: one retry, then a clear error; nothing half-written | Error handling | A fake that returns bad JSON twice gives an error that names the field; no case folder is written | ⬜ |
| BE-11 | One run with the real model, trace saved | Trace + run folder | The output loads with `load_case`; the trace is linked in the README as evidence | ⬜ |

**Gate B2:** from an analysis, the backend returns valid cases whose IDs come only from code.

### B3 — Stage Plot: the storyline outline · study: A-I · target Tue 10 Nov

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| BE-12 | Decide with Robin and Mike what moves from the generator's seeded plot into the backend (revisits D9 of the bridge plan) | Decision Log | Both agree; the plot code that stays in the generator is listed | ⬜ |
| BE-13 | Plot output model: per case, the ordered events (type from the closed list, type-specific facts, description), without dates, participants or IDs | Model + schema | An unknown event type fails; an outline that carries an ID fails | ⬜ |
| BE-14 | Event-description call through Robin's client | Prompt + model | The fake-LLM test passes; the real model's answer validates | ⬜ |
| BE-15 | Plot coherence before handover: exactly one `hire`, first; nothing after `termination` | Checks | One deliberate break per rule fails with a clear message | ⬜ |
| BE-16 | The Plot stage: cases → one outline per case | Stage function | On AMEXIO's example, 100101's outline has the reference event types in the reference order | ⬜ |

**Gate B3:** Valentin takes the outline and adds dates and participants without adapting it.

### B4 — Integration: the chain speaks · study: A-I, F6 · Review 2 (~13 Nov)

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| BE-17 | With Valentin: his dated, staffed events go back into the case through `ingest_storylines` | Events with IDs | Every event loads with `load_case`; an unknown `employeeId` is refused | ⬜ |
| BE-18 | Full run: Daniel's input → four stages → filled documents for 100101 (Valentin's Fill stage uses AX-022) | End-to-end run | The result's facts equal the reference facts (as in BR-15) | ⬜ |
| BE-19 | A run ID and one trace line per stage | Trace | The run can be reconstructed from the trace alone | ⬜ |
| BE-20 | Contract version and tag `backend-v0.1`; README updated | Tag + README | CI green on `main` | ⬜ |

**Gate B4 (Review 2):** the backend chain produces the reference dossier from
an input. **End of Part A**: from here on, nobody waits for my module.

# Part B — the case model (Sprint 4 → Sprint 6)

## Sprint 4 — weeks 12–13 (16–27 Nov)

### M03b (our side) — BR-00, BR-01, BR-09 · study: A-A, F2

See the M03b table: fact sheet from AMEXIO's files, the bridge decisions as
Decision Logs, and every reference value checked against the fact sheet.

### M04 (rest) — Placeholders resolve from the case model · study: A-B

Closes: FR-CM-01, TR-06. Filling the texts is Valentin's stage; these
microphases make the case model guarantee what his stage needs.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-023 | Every placeholder in the reference documents resolves through the lookup | Test shared with Valentin's stage | 100% of placeholders in the reference dossier resolve | ⬜ |
| AX-024 | An unresolved placeholder stops the run | Error | One wrong placeholder fails; no silent blank | ⬜ |
| AX-025 | Format dates and amounts only when the text is filled (formatting functions the Fill stage calls) | Long date, formatted amount | Stored values stay ISO and numeric | ⬜ |

**Gate M04:** every fact in a document comes from a case-model field.

### M05 — Change propagation · study: A-C

Closes: FR-CM-04.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-026 | Record which facts each document uses | Usage index | Matches the placeholders counted by hand in one document | ⬜ |
| AX-027 | Change a fact through one function only | Update function | Invalid new value is refused; old value stays | ⬜ |
| AX-028 | Return the documents (and backend stages) affected by a change | List of document IDs | A fact used nowhere returns an empty list | ⬜ |
| AX-029 | Reference test: correct the gross salary | Test | Exactly the contract and the payslip are flagged and re-filled, 0 manual text edits | ⬜ |
| AX-030 | Log every change: what, old value, new value, when | Change log | The log entry matches the change made | ⬜ |

**Gate M05:** one corrected fact reaches every document that uses it.

### M06 — Versioned storage · study: A-D, F4

Closes: FR-CM-05, supports NFR-TRC-01.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-031 | Schema version inside every file | Version field | A file without version fails to load | ⬜ |
| AX-032 | One folder per run (GEN-YYYY-NNNN), named from the backend run ID (BE-19) | Run folder | Two runs never share a folder | ⬜ |
| AX-033 | Reload an old run | Loaded case | Equal to the case that was saved | ⬜ |
| AX-034 | Saving is deterministic | Stable files | Same case saved twice gives identical files | ⬜ |
| AX-035 | With Stylianos: reload a run and export it again | Joint test | The XML is identical | ⬜ |

**Gate M06:** any stored run can be reloaded and gives the same export.

## Sprint 5 — weeks 14–16 (30 Nov–18 Dec)

### M07 — Run configuration · study: A-E, F8

Closes: FR-CFG-01, FR-CFG-03, FR-CFG-04.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-036 | Decide where the line is between domain and scenario | Decision, proposed to the team | The team agrees; two examples are classified the same way by a teammate | ⬜ |
| AX-037 | Config model and loader for `config.json`: domain, scenario, outcome, language, target system, and the rule values Robin listed (wage-tax rate, medical-check interval) | Loaded config | A missing or wrong field fails with a clear message | ⬜ |
| AX-038 | Document types to include, in process order | Ordered list in config | Unknown document type fails | ⬜ |
| AX-039 | Required and optional metadata fields in config; with Valentin, the validator reads this list | Field lists | Removing a field from the list changes the check result | ⬜ |
| AX-040 | With Mike: the reference dossier starts from `config.json` alone, through the backend chain | Run from config | No other input is needed | ⬜ |

**Gate M07:** one configuration file defines a run.

### M10 — HR as a domain template · study: A-E

Closes: first part of FR-CFG-07, DR-11.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-051 | Define the domain template format: entity types, document types, event types, metadata fields, coherence rules | Template format | A teammate can read it without me | ⬜ |
| AX-052 | Move everything HR-specific out of the code into the HR template | HR template | No HR word is left in core code | ⬜ |
| AX-053 | Dossier-level facts defined by the template | Facts from template | The employee number still validates | ⬜ |
| AX-054 | With Valentin: coherence rules as data (net = gross minus wage tax, payslip gross = contract salary, no document before the start date) | At least 3 rules | The validator runs them from the template | ⬜ |
| AX-055 | Load the reference dossier through the template | Green regression test | Nothing in the output changed | ⬜ |

**Gate M10:** the first domain is configuration, not code.

### M12 — Volume · study: A-G, F6

Closes: FR-CFG-02, supports BR-08 (requirement).

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-061 | Number of dossiers and documents per dossier in config | Two config values | 1×5 and 10×20 give exactly those counts | ⬜ |
| AX-062 | Case numbers unique inside a batch | Batch numbering | 0 duplicate case numbers in 100 dossiers | ⬜ |
| AX-063 | With Mike: ID check on a real batch run through the backend | Batch test | 0 duplicate IDs, 0 IDs from the LLM | ⬜ |
| AX-064 | Measure save and load time (and LLM cost) for 100 dossiers | Numbers | Reported to the team | ⬜ |
| AX-065 | Review list for many dossiers, filter by validation status | List view | The filter shows only failing dossiers | ⬜ |

**Gate M12:** the case model holds a batch of 100 dossiers.

### M13 — Edge cases · study: A-G, F5

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-066 | Large dossier: 10 participants, 20 documents | Fixture | Validates and reloads | ⬜ |
| AX-067 | Two personas with the same name | Test | They stay distinct by ID in every document | ⬜ |
| AX-068 | Event with no document, document with no participant | Two tests | Each is refused or flagged with a clear message | ⬜ |
| AX-069 | Delete an entity that is still referenced | Refusal | Nothing is left pointing to a missing ID | ⬜ |
| AX-070 | Error messages name the entity ID and the field | Reworded errors | A teammate fixes a broken fixture without asking me | ⬜ |

**Gate M13 (Review 3, ~18 Dec):** broken input fails loudly and never silently.

## Sprint 6 — weeks 17–18 (4–15 Jan)

### M08 — Review screen (preview), read-only · study: A-F

Closes: FR-REV-03, TR-12. Moved to the end on 26 Oct; the preview is the
editable "preview layout" of the team's architecture.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-041 | Decide with Daniel the form and place of the review interface (inside his frontend, or separate) | Decision, proposed to the team | Criteria and rejected options are written down | ⬜ |
| AX-042 | List the case-model functions the interface may call | Small API | The interface never writes files directly | ⬜ |
| AX-043 | Show the cast of the reference dossier | Cast view | All personas and organisations appear once | ⬜ |
| AX-044 | Show the storyline in time order | Storyline view | Order matches the event dates | ⬜ |
| AX-045 | Show one document next to its metadata and the facts it uses | Document view | Works for all five reference documents | ⬜ |

**Gate M08:** a person can read the whole reference dossier on screen.

### M09 — Review edits · study: A-F

Closes: FR-REV-01, FR-REV-02, FR-REV-04, FR-CFG-05.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-046 | Edit a persona name from the screen | Edit form | The new name appears in 100% of later documents | ⬜ |
| AX-047 | Edit an event date from the screen | Edit form | The new date appears in all documents of that event | ⬜ |
| AX-048 | After an edit, show which documents changed | Affected list on screen | Matches the list from AX-028 | ⬜ |
| AX-049 | Review points in config (after personas, after storyline); with Mike, the backend chain pauses there | Two pauses | Generation waits at both points | ⬜ |
| AX-050 | With Valentin: show validation errors with a link to the entity | Error list | Every failing check opens the right persona, event or document | ⬜ |

**Gate M09:** a reviewer corrects personas and storyline, and the documents follow.

### M14 — Usability and freeze · study: A-H, F7

Closes: FR-REV-05 (could-have), DR-07 when AMEXIO's schema arrives.

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-071 | Check the template metadata against AMEXIO's latest list | Updated template | Only the template changes | ⬜ |
| AX-072 | Review without editing JSON: form fields for persona and event | Forms | A full correction is done with no file opened | ⬜ |
| AX-073 | Test the review with one person outside my module | Notes | Finished in 15 minutes or less | ⬜ |
| AX-074 | Fix the three biggest problems from the test | Three fixes | The same person confirms them | ⬜ |
| AX-075 | Code freeze for my module | Final tag | All tests green; reference dossier passes | ⬜ |

**Gate M14:** my code is finished.

### M15 — Documentation and handover · study: A-H

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-076 | Guide: how to add a domain | Step-by-step guide | A teammate adds a toy domain by following it | ⬜ |
| AX-077 | Case model and backend stages (CM ID, Plot) section for the research and architecture report | Report section | Stylianos or Mike accepts it into the report | ⬜ |
| AX-078 | Review part of the user guide | Guide section | Screens in the guide match the real ones | ⬜ |
| AX-079 | Demo script for my part: change one fact, the documents follow | Script | Rehearsed once from start to end | ⬜ |
| AX-080 | Review test with AMEXIO consultants, if they are available | Dated feedback | Result recorded, also if the answer is no | ⬜ |

**Gate M15 (15 Jan):** someone else can use and extend my module without me.

## Stretch — only if ahead of plan

### M11 — Second domain · study: A-E

Closes: FR-CFG-07, FR-CFG-06, DR-12, BR-05 (requirement).

| ID | Build | Output | Verify | Status |
|---|---|---|---|---|
| AX-056 | Write a small reference dossier for a second domain by hand | Second reference dossier | A teammate finds it coherent | ⬜ |
| AX-057 | Second-domain template: entities and at least five document types | Template | The template loads | ⬜ |
| AX-058 | Second-domain metadata fields and at least three coherence rules | Rules as data | One broken rule is caught | ⬜ |
| AX-059 | Load the second-domain dossier | Valid case | 0 changed files in core code | ⬜ |
| AX-060 | Scenario variations (e.g. permanent or fixed-term contract) | Two variations | Both load and both are valid | ⬜ |

**Gate M11:** a second domain works with no code changes. AX-060 can be done on HR alone.

## Buffer — weeks 19–20 (18–29 Jan)

No new microphases. Only fixes from the demo and feedback, and the final submission.

## Decisions on my side

I propose, the team decides. Each one becomes a Decision Log.

| Decision | Where | Needed by |
|---|---|---|
| Generate from a structured case model, or extract metadata from generated text? | Team working principle | Decision Log in progress |
| Case model schema v1, then v1.1 | AX-010, AX-020, M03b | Done; v1.1 decisions D1–D9 to write (BR-01) |
| Domain focus: HR first | Team decision, 7 Oct | Done |
| Where the backend runs and how stages talk | BE-01 | Wed 28 Oct |
| Who owns the plot: generator or backend Plot stage | BE-12 | Thu 5 Nov |
| Line between domain and scenario | AX-036 | Week 14 |
| Form and place of the review interface | AX-041 | Week 17 |

## Dependencies on teammates

| Who | What I need or give | Microphases |
|---|---|---|
| Daniel (frontend, analysis) | His analysis output is my CM ID input; the review interface lives in or next to his frontend | BE-02, BE-07, BE-18, AX-041 |
| Robin (LLM calls, demo) | The LLM client; the plot moving out of the generator; v1.1 questions | BR-12, BR-16, BE-04, BE-08, BE-12, BE-14 |
| Valentin (Date & participants, Fill placeholder, validation) | Takes my outline and case; placeholder syntax and lookup; metadata list; rules as data; error links | BE-02, BE-13, BE-17, AX-021–AX-025, AX-039, AX-050, AX-054 |
| Mike (architecture, orchestration) | Backend runtime; run from config; review pauses; batch run | BE-01, BE-12, AX-040, AX-049, AX-063 |
| Stylianos (export, AMEXIO contact) | Reload and re-export; AMEXIO's metadata schema and mock data | AX-035, AX-071, AX-080 |

## Stop conditions

Stop and ask Giulia (she talks to the team) if a change:

- alters the case model schema after v1.1 (only by group agreement, with a new version number);
- changes the pipeline contract after BE-06 (same rule);
- adds more than one new concept to the active microphase;
- cannot be checked with a test or a visible output;
- is something Giulia cannot explain herself after the session.

## Maintenance

- Add a microphase instead of making an existing one bigger; insert it where it belongs with a letter suffix (e.g. AX-018a).
- Keep the IDs once work has started.
- Mark complete only with evidence (commit, test run or screenshot).
- Update the Status table after every closed microphase.
