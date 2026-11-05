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

## How to run it

```python
import json
from pipeline import Analysis, run_chain

analysis = Analysis.model_validate(json.load(open(
    "case_model/fixtures/generator/amexio_example/employees.json")))
out = run_chain(analysis, "runs/demo")      # writes one case folder per employee
# out.cases -> 4 cases with code-assigned IDs; load them with case_model.load_case
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
- **Robin** — implement `LLMClient.generate(prompt, output_model) -> validated
  object` for the real model (`pipeline/llm.py`). The stages already run against
  `FakeLLM`, so nothing else blocks on you.
- **Valentin** — your two stages (Date & participants, Fill placeholder) are the
  `dates` and `fill` steps in `pipeline/chain.py`, currently pass-through stubs.
  Date & participants returns events for `ingest_storylines`; Fill placeholder
  uses the fact lookup (AX-022, coming next).
- **Mike** — orchestration is one Python process calling `run_chain`. A stage
  that returns the wrong shape raises `ChainError` and names the stage.

## Not here yet (later microphases)

Real CM ID stage with retry and the corrections list (BE-09, BE-10), the real
Plot output model (BE-13), the run ID and per-stage trace (BE-19), the real-model
run (BE-11), and the placeholder syntax (AX-021). Each extends the contract with
a new version number.
