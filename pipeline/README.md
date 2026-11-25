# pipeline

The backend chain (see `docs/PIPELINE_CONTRACT.md`).

The LLM API key is read only from the environment variable `LLM_API_KEY`
(copy `.env.example` to `.env` locally); it is never written in code, config
or fixtures, and CI fails if gitleaks finds a secret in the git history.
