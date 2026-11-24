# Backend handover — contract v1.1, steps 5 and 8 to Valentin (H5)

Date: 20 November 2026 · From: Giulia · To: Valentin (and Robin, Mike, Daniel, Stylianos)

The backend runs end to end on pipeline contract v1.1 (`docs/PIPELINE_CONTRACT.md`):
eight steps, offline with a fake LLM, 275 tests green. Two steps are still stubs
with the right shapes: **step 5 Dates & participants** and **step 8 Fill**. They
are Valentin's. Everything is Python, in the team repo, folder `pipeline/`.
This note replaces the B1 handover of 5 November (contract v1.0, four stages).

## Run it (2 minutes)

```bash
pip install -r requirements.txt
python3 -m pytest -v                 # offline, no API key
```

```python
import json
from pipeline import RunRequest, run_chain

request = RunRequest.model_validate(json.load(open("pipeline/fixtures/run_request.json")))
result = run_chain(request, out_dir="runs/demo")   # options.fake_llm: offline
# result.cases: 10 cases with code-assigned IDs; result.trace: one line per step / LLM call
```

No API key is needed for any of this. When a real model is used, the key is read
only from the environment variable `LLM_API_KEY` (see `.env.example`); never
commit a key: CI runs gitleaks on every push.

## The chain (contract §3)

| # | Step | Owner | Code | State |
|---|---|---|---|---|
| 1 | Personas (LLM) | Robin | `generation.py` `propose_personas` | reference version; Robin ports his |
| 2 | CM ID | Giulia | `cm_id.py` | done |
| 3 | Plot | Giulia | `plot.py` → `PlotOutline` | done, rechecked against §5 (H3) |
| 4 | Event content (LLM) | Robin | `generation.py` `write_event_content` | reference version |
| **5** | **Dates & participants** | **Valentin** | `valentin_stubs.py` `dates_and_participants_stub` | **stub** |
| 6 | Document plan | Giulia | `document_plan.py` | done |
| 7 | Document text (LLM) | Robin | `generation.py` `write_document_text` | reference version |
| **8** | **Fill** | **Valentin** | `valentin_stubs.py` `fill_stub` | **stub** |

`chain.py` calls the steps in this order (`STAGES`). A step that returns the
wrong type stops the run with `ChainError` naming the step.

## Step 5 · Dates & participants (Valentin)

**Signature** (keep it; `chain.py` calls it like this):

```python
dates_and_participants(cm: CmIdOutput, outline: PlotOutline,
                       content: EventContentIn, config: RunConfig) -> CmIdOutput
```

- **In:** the cases with IDs (`cm.cases`), the outline (one `CaseOutline` per
  employee, 1–10 slots, every closed-list value already chosen by Plot), the
  LLM text per slot (`content`, same slot keys), and `config.as_of_date`.
- **Out:** a `storylines` dict in the shape of
  `case_model/schema/input.storylines.schema.json`, handed to
  `ingest_storylines(cases, storylines)`; return
  `CmIdOutput(cases=..., corrections=[*cm.corrections, *new])`.
- **You decide, in code:** every date (ISO `YYYY-MM-DD`), salary after a raise,
  contract type and hours after a change, medical-check result, training
  provider, absence start and end, termination date and notice date.
- **Already decided, do not change:** event type, rating, year, change kind,
  new position, training `durationDays`, termination reason (Plot); the texts
  `course`, `comment`, `reason` (LLM). IDs: never — `ingest_storylines` assigns
  `EVT-…` and links the participants.
- **Rule from the contract (§5 table):** an appraisal is dated 30 June of its
  year. Plot already keeps the order coherent (nothing after a termination;
  appraisals only in years the employee was there); keep every date between
  the hire date and `asOfDate`.
- **What the stub does today** (replace it): spreads the dated slots evenly
  between hire and `asOfDate`, +3 % on a salary review, +8 % on a promotion,
  medical check always "Fit for work", absence of 5 days, termination at a
  month end.

## Step 8 · Fill (Valentin)

**Signature:**

```python
fill(cm: CmIdOutput, texts: DocumentTexts) -> CmIdOutput
```

- **In:** the dated cases and, per employee and planned document, the section
  texts written by the LLM. Texts contain placeholders `{{ path }}`
  (contract §7, AX-021), e.g. `{{ personas.P001.name }}`.
- **Do:** fill each text with `fill_text(case, text, formats)` from
  `case_model.fill` (M04, 24 Nov). It resolves every placeholder with
  `get_fact`, formats dates and amounts as AMEXIO prints them, and raises
  `UnresolvedPlaceholders` naming every placeholder that does not resolve, has
  no value or points at an internal ID: the run stops, never a blank
  (contract §7). `fact_paths(case)` lists the placeholders a prompt may offer.
- **What the stub does today:** only checks that every placeholder resolves;
  it does not write `Document.text` yet (see open points).

## Tests that must stay green

`pipeline/test_chain.py` runs the whole chain with your steps (eight steps in
order, valid cases that load, trace, the reference seed 100101 keeps its facts).
Add your own tests next to them (`pipeline/test_dates.py`, `pipeline/test_fill.py`):
one test for the accepted case and one for each refusal, with
`pytest.raises(ValidationError)` or the exact error, not `Exception`.

## Open points that touch your steps (contract §10)

| Question | With |
|---|---|
| Case model v1.2: `signed_by` on events (§6). Dates & participants would set it (manager at the event date, director if the manager left). Not merged until the team agrees | all |
| The slot `summary` has no field in `input.storylines.schema.json`, so `ingest_storylines` drops it | Valentin, Giulia |
| Who creates the `Document` records (`DOC-…`) that Fill writes `Document.text` into | Valentin, Giulia, Stylianos |
| `RunConfig` has no leaver share, so Plot plans no termination yet | Daniel, Giulia |

## What we ask you

1. Read contract §3, §5 and §7, then confirm your row in **§11 Sign-off**
   (Dates & participants, Fill) — or write what you need changed.
2. Work on a branch from `main`; one commit per step; open a PR; CI must be green.
3. Replace the stub bodies (or add `dates.py` / `fill.py` and point `chain.py`
   at them); do not change the input models without a new contract version.

Questions: Giulia.
