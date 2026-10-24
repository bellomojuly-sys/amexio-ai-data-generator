# Case model — roadmap

Module: case model, domain configuration, review interface (CM, CFG, REV).
Role: GenAI Engineer, team DATANOVA. Owner: Giulia Bellomo.
Made 6 October 2026; code finished by week 16 (18 Dec), delivery by week 20.

80 microphases in 16 milestones (`AX-001` … `AX-080`). Each microphase has one
change, one output and one pass/fail check. The reference dossier is the HR
dossier `100101 Jan de Vries` from AMEXIO's mock data. The detailed portfolio
tracking lives in Notion; this file is the in-repo source of truth for status.

> Team rule: AI writes, code keeps the facts. The case model is where the facts
> live.

## Calendar

| Sprint | Weeks | Dates | Milestones | What exists at the end |
|---|---|---|---|---|
| S2 | 7–8 | 5–16 Oct | M00–M03 | Case model v1 in the team repo; the reference dossier loads and validates; other modules can read it |
| — | — | 19–23 Oct | Autumn break | |
| S3 | 9–11 | 26 Oct–13 Nov | M04–M08 | Review 2 (~13 Nov): placeholders, change propagation, versioned runs, run from config, read-only review screen |
| S4 | 12–13 | 16–27 Nov | M09–M11 | Review edits reach documents; HR as a domain template; a second domain if time allows |
| S5 | 14–16 | 30 Nov–18 Dec | M12–M14 | Review 3 (~18 Dec): batches, edge cases, review without editing JSON; code freeze |
| S6 | 17–18 | 4–15 Jan | M15 | "How to add a domain" guide, report sections, demo script |
| Buffer | 19–20 | 18–29 Jan | — | Only fixes from the demo and the final submission |

## Status

- **Done:** M00–M02 and M03 (AX-001 → AX-020, plus AX-018a). Case model v1 is
  tagged `v1` and the reference dossier runs as a regression test on every push.
- **In progress:** M03b, case model v1.1 and the generator bridge, on branch
  `case-model-v1.1` (AX-011a/b done there). Plan: [ROADMAP_BRIDGE.md](ROADMAP_BRIDGE.md).
- **Next gate:** M04 (Sprint 3 — fact lookup and placeholders).

## Milestones

### M00 — Team baseline
| ID | Build | Verify | Status |
|---|---|---|---|
| AX-001 | ID generator in code (`next_id`) | Two calls never return the same ID | ✅ |
| AX-002 | Persona and Event models, linked by ID | Event stores participant IDs, not names | ✅ |
| AX-003 | First three tests | Unknown reference is refused; all tests pass | ✅ |
| AX-004 | Move the code into the team repo, `case_model/` | The three tests pass there | ✅ |
| AX-005 | Module contract (README) | Orchestration and generation confirm they can use it | ✅ |

### M01 — Remaining entities
| ID | Build | Verify | Status |
|---|---|---|---|
| AX-006 | Organisation model (ORG-01) | Unknown organisation ID fails | ✅ |
| AX-007 | Employment model (position … salary as `Money`) | Missing required field fails | ✅ |
| AX-008 | Document model with AMEXIO's five metadata fields | Document with an unknown event ID fails | ✅ |
| AX-009 | Dossier-level facts (employee number, title, description) | Dossier without an employee number fails | ✅ |
| AX-010 | One Case object that holds all parts | A full Case validates in one call | ✅ |

### M02 — ID and format rules
| ID | Build | Verify | Status |
|---|---|---|---|
| AX-011 | One ID pattern per type; six-digit employee number | An ID with the wrong pattern fails | ✅ |
| AX-012 | Refuse incoming data that already carries an ID | An ID written by the LLM is refused | ✅ |
| AX-013 | Dates stored only as ISO 8601 | "12/03/2026" fails | ✅ |
| AX-014 | Amounts as number plus currency | "EUR 4.350" fails | ✅ |
| AX-015 | Uniqueness test over 100 dossiers | 0 duplicate IDs | ✅ |
| AX-011a | Strict ID and employee-number regexes: `fullmatch` and `[0-9]` instead of `^…$` and `\d` | `"P001\n"`, `"100101\n"` and non-ASCII digits (`"P٠٠١"`) fail | ✅ (v1.1) |
| AX-011b | `Case` checks every ID's pattern with `validate_id`, so a case loaded from JSON obeys AX-011 too | A loaded case with persona id `"banana"` or event id `"EVT-1"` fails | ✅ (v1.1) |

> AX-011a and AX-011b were found on 24 October while reviewing `format_rules.py`:
> all tests were green, but the rules did not hold. Today a case built with
> `CaseModel` always has well-formed IDs (they come from `next_id`), while a
> case read by `load_case` — such as one exported by the demo — is never
> checked for ID patterns. Do AX-011a first; AX-011b relies on it.

### M03 — Reference dossier and integration
| ID | Build | Verify | Status |
|---|---|---|---|
| AX-016 | Cast and storyline of dossier 100101 as data | Loads with no error; every participant ID exists | ✅ |
| AX-017 | Five documents and the dossier facts | Each document has its event ID and a participant | ✅ |
| AX-018 | Save to four JSON files and load back | Save, load, compare: the two cases are equal | ✅ |
| AX-018a | Critical review of every test (feedback 15 Oct) | For each test, one sentence on what it proves; a deliberate break makes the right test fail | ✅ |
| AX-019 | Reference dossier as a regression test on every push | A deliberate break in the fixture makes it fail | ✅ |
| AX-020 | Hand over case model v1 (tag `v1`) | Generation and export read the dossier through the module | ✅ |

**Gate M03:** the team's thin slice runs on case model v1.

### M04–M08 (Sprint 3) — planned
M04 fact lookup and placeholders (AX-021–025); M05 change propagation
(AX-026–030); M06 versioned storage (AX-031–035); M07 run configuration
(AX-036–040); M08 read-only review screen (AX-041–045).

### M09–M11 (Sprint 4) — planned
M09 review edits (AX-046–050); M10 HR as a domain template (AX-051–055);
M11 second domain, stretch (AX-056–060).

### M12–M14 (Sprint 5) — planned
M12 volume (AX-061–065); M13 edge cases (AX-066–070); M14 usability and freeze
(AX-071–075).

### M15 (Sprint 6) — planned
Documentation and handover (AX-076–080).

## Traceability (v1)

The case model tests can be run from the repository root with
`python3 -m pytest -v` (55 tests). Continuous integration
(`.github/workflows/tests.yml`) runs them on every push and pull request.

| Step | Proof | Terminal check |
|---|---|---|
| AX-006 → AX-014 | parts, ID and format rules | `-k "organisation or employment or document or employee_number or pattern or caller or non_iso_date or money"` |
| AX-015 | 100 dossiers, 0 duplicate IDs | `-k "uniqueness"` |
| AX-016, AX-017 | reference dossier loads and is coherent | `-k "test_reference_dossier"` |
| AX-018 | saved to four files and loaded back equal | `-k "test_storage"` |
| AX-018a | critical test review; a deliberate break fails the right test | see `case_model/TEST_REVIEW.md` |
| AX-019 | reference dossier frozen as a golden snapshot | `-k "matches_golden"` |
| AX-020 | case model v1 tagged for integration | `git show v1 --stat` |

Case model v1 lives on `main`; the integration point is tag `v1`.
