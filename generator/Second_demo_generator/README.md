# Second demo generator (v2)

Robin's second version of the interactive dossier generator, built on the
Python backend that follows pipeline contract v1.1 (`docs/PIPELINE_CONTRACT.md`).
v1 (TypeScript, `generator/demo_dossier_generator/`, tag `demo-2026-10-30`) is
frozen and unchanged.

**Written with Claude.** The code of this folder and Robin's parts of
`pipeline/` (the LLM provider, the three generation prompts, the placeholder
check) were written with Claude (Anthropic, model Claude Opus 5.5) in a Claude
Code session, and reviewed and committed by Robin. The reasons for each choice
are below, so they can be checked and defended.

## Build order

| # | What | Where | State |
|---|---|---|---|
| 1 | A real LLM provider behind the one client (contract §8, rule 6) | `pipeline/llm.py`, tests in `pipeline/test_llm_providers.py` | done |
| 2 | v1's prompts ported to the three generation calls, cut to what v1.1 lets the LLM write | `pipeline/generation.py` | next |
| 3 | The placeholder check for Parts 2 and 3 (contract §7, rule 3) | `pipeline/` | — |
| 4 | The Streamlit demo app | this folder | — |

## 1 · The LLM provider

### Use it

```python
from pipeline import create_llm, run_chain, RunRequest
llm = create_llm()                    # AnthropicLLM, Claude Sonnet 5.5
result = run_chain(request, llm=llm)
```

| Setting | How | Default |
|---|---|---|
| API key | environment variable `ANTHROPIC_API_KEY` only (contract §8) | none: a `setup` error |
| Model | `AMEXIO_LLM_MODEL`, or `MODEL_DEFAULTS` in `pipeline/llm.py` for everyone | `claude-sonnet-5-5` (Model Selection document) |
| Provider | `AMEXIO_LLM_PROVIDER`: `anthropic` or `fake` (offline, no key) | `anthropic` |
| Address | `ANTHROPIC_BASE_URL`, for a gateway that speaks the same API | `https://api.anthropic.com` |
| Answer size, timeout | `create_llm(max_tokens=..., timeout=...)` | 8000 tokens, 120 s |

The key is an API key from the Claude Console (`sk-ant-…`). A claude.ai
subscription does not by itself give API access.

**Switching keys.** The key is read when a client is made, so changing the
variable and making a new client switches it; nothing is stored in the repo.
On Windows, either for one PowerShell session:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

or stored in the conda environment (outside the repo), active after
`conda activate amexio` again:

```powershell
conda env config vars set ANTHROPIC_API_KEY=sk-ant-... -n amexio
```

The demo app (step 4) will also read a `.env` file next to it. `.env` and
`.env.*` are in `.gitignore` (commit "Ignore .env files before any API key is
used").

### Errors

A provider that gets no usable answer raises `ProviderError`, a kind of
`LLMError`, so the chain reports it as a failed LLM step that names the stage.
Its `kind` is v1's (`src/ai/types.ts`), and says what the user can do:

| Kind | Means | When |
|---|---|---|
| `setup` | fix the settings | no key; 401, 403 (key); 402 or "credit balance" (billing); 404 (model or address); service unreachable; answer cut off at `max_tokens` |
| `retry` | try again later | 429 (rate limit) and 529 (overloaded), after one wait; 500, 504 and other statuses; timeout; dropped connection; empty answer |
| `refused` | change the request | 400, 413 (e.g. prompt too long); the model's own refusal; context window full |
| `cancelled` | the run was stopped | `llm.cancel()` before the next call or during the wait |

The API's own message is added to the error text, with the key and anything
that looks like a key replaced by `[redacted]`.

### Choices

- **Standard library HTTP (`urllib`), not the `anthropic` SDK.** The v1
  providers did the same with `fetch`, and so does Daniel's `ai_gateway.py`,
  so the three can be merged into the one client (rule 6) without a new
  dependency in the shared CI. Every status → kind mapping is in one place
  (`_HttpLLM._http_error`) and tested offline with a fake transport.
- **One wait-and-retry for 429 and 529 only.** Those two say "not now"; the
  others will not change by waiting. The wait is the service's `Retry-After`
  (default 10 s); a `Retry-After` over 60 s is not waited for. This is a
  transport retry, separate from the answer retry of `complete_as`, and not
  counted in the trace's `retries`, which the contract defines as answer
  retries.
- **A cut-off answer fails at once.** Retrying the same prompt would be cut off
  again and spend the one answer retry; the error names `max_tokens` instead.
- **One `max_tokens` for every call (8000, v1's default).** The interface
  `complete(prompt)` has no per-call size. The largest call, 25 personas, is
  about 3,300 tokens by v1's own estimate (300 + 120 per employee).
- **Key read once, when the client is made**, and never written into an error,
  a record or the client's `repr`.
- **No streaming.** The answer is validated as one JSON object, so a partial
  answer is of no use to the pipeline; the app shows each answer when it is
  complete.
- **No structured-output mode yet.** It needs the JSON Schema in the request,
  and `complete(prompt)` has no place for it: that would change the shared
  interface. `complete_as` already validates every answer.

### Changes to the shared client (`BaseLLMClient`), both backward compatible

- **A call that fails at the provider is recorded** as a failed `CallRecord`
  before the error is raised. Before, it left no record, and the chain wrote a
  `code` trace line for an LLM stage; now every call has its `llm` line
  (contract §8: "every call adds one trace line").
- **Each attempt is kept** on the record (`CallRecord.attempts`: prompt, answer,
  why code refused it), so the demo can show the prompt, the answer and the
  corrections of every call. The trace line does not change.

Tests: `python -m pytest -v` from the repo root (offline, no key).
