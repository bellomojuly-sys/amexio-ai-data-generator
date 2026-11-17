# Backend handover — B1 is ready to build on (BE-06)

Date: 5 November 2026 · From: Giulia · To: Daniel, Valentin, Robin, Mike

B1 is done: the runtime is decided, the contract is confirmed, and there is a
running stub chain you can plug your stage into. Everything is Python, in the
team repo, folder `pipeline/`.

## What exists

| Thing | Where | Microphase |
|---|---|---|
| Runtime decision (one Python service, stages = functions, in-process) | `docs/decisions/BE-01-backend-runtime.md` | BE-01 |
| Pipeline contract (five stages, I/O, case-model function each uses) | `docs/PIPELINE_CONTRACT.md` (v1.0, signed off) | BE-02 |
| Stage contracts as pydantic models | `pipeline/contracts.py` (`Analysis`, `CmIdOutput`) | BE-03 |
| JSON Schema for the owner-to-owner boundary | `pipeline/schema/analysis.schema.json` | BE-03 |
| LLM client interface + offline fake | `pipeline/llm.py` (`LLMClient`, `FakeLLM`) | BE-04 |
| Stub chain, stages wired in order | `pipeline/chain.py` (`run_chain`) | BE-05 |
| Analysis → ingest mapping | `pipeline/mapping.py` (`map_analysis`) | BE-07 |
| Placeholder syntax `{{ path }}` | `docs/PIPELINE_CONTRACT.md`, section "Placeholder syntax" | AX-021 |
| Fact lookup for the Fill stage | `case_model/lookup.py` (`get_fact`) | AX-022 |

## How to run it

*Updated 17 Nov: contract v1.1, eight steps (see `docs/PIPELINE_CONTRACT.md` §11b).*

```python
import json
from pipeline import RunRequest, run_chain

request = RunRequest.model_validate(json.load(open("pipeline/fixtures/run_request.json")))
result = run_chain(request, out_dir="runs/demo")   # options.fake_llm: offline, no API key
# result.cases -> 10 cases with code-assigned IDs; result.trace -> one line per step / LLM call
```

Run the tests (offline, no API key):

```bash
python3 -m pytest pipeline/ -v
```

## What each owner does next

- **Daniel** — your analysis is an `Analysis` (same shape as
  `employees.json`, Option A). Send it as JSON matching
  `pipeline/schema/analysis.schema.json`. No `id` fields: the case model assigns
  every ID.
  *Update 16 Nov:* the `MockToTemplate` branch (PDF Template Studio) is still
  deterministic and does not produce an `Analysis` yet; with the API key released
  on 14 Nov the analysis call can now be built. Its `{{EMPLOYEE_NAME}}`-style
  placeholders differ from the agreed `{{ path }}` syntax (AX-021): to align at
  the next team meeting (a mapping table, or the templates switch to `{{ path }}`).
- **Robin** — *(17 Nov, v1.1)* write a provider as a subclass of
  `BaseLLMClient` that implements only `complete(prompt) -> Completion`
  (`complete_as` with the one retry is inherited), and replace the bodies of the
  three functions in `pipeline/generation.py` with your Python port. Their
  signatures and checks are the contract; the tests in
  `pipeline/test_generation.py` and `test_chain.py` must stay green.
- **Valentin** — your two stages (Date & participants, Fill placeholder) are the
  `dates` and `fill` steps in `pipeline/chain.py`, stubs in `pipeline/valentin_stubs.py` (17 Nov: the Plot output model,
  `PlotOutline`, exists; replace `dates_and_participants_stub` and `fill_stub`).
  **Fill placeholder can start now:** `get_fact(case, path)` (AX-022) reads any
  fact of the reference case 100101. **Date & participants waits for the Plot
  output model (BE-13, Giulia)**; it returns events for `ingest_storylines`.
- **Mike** — orchestration is one Python process calling `run_chain`. A stage
  that returns the wrong shape raises `ChainError` and names the stage.

## Not here yet (later microphases)

Real CM ID stage with retry and the corrections list (BE-08 … BE-10), the real
Plot output model (BE-13), the run ID and per-stage trace (BE-19) and the
real-model run (BE-11). Each extends the contract with a new version number.
While the later stages are stubs, `run_chain` checks only the type of each
stage's output; full re-validation comes with the real stages.
