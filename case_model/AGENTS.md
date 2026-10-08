# Instructions for AI coding agents — `case_model/`

This folder is the case model module of the AMEXIO AI Data Generator (team DATANOVA, Fontys MA-AAI).
Owner: Giulia Bellomo. These rules apply only inside `case_model/`. The rest of the repository belongs to other team members.

## What this module is

The case model is the single place where the facts of one dossier live: personas, organisations, employment, events, documents and their metadata. Other modules (generation, validation, export) read facts from here. The team rule is: **AI writes text, code keeps the facts.**

Current domain: **HR** (team decision of 7 October 2026), based on AMEXIO's mock data: 4 employees of Acme Logistics B.V., 5 documents each (employment contract, payslip, medical check, performance appraisal, training certificate), imported into OpenText through `import.xml`. Reference dossier: `100101 Jan de Vries`.

The public contract of the module is `README.md` in this folder. Keep it up to date when you add or change a public function.

## How Giulia wants to work

1. **Explain, do not just produce.** Giulia must be able to explain every line in front of her teachers. Answer in Italian; code, comments, tests and commit messages are in English.
2. **Repetitive work: she writes the first two.** When a task repeats the same structure (for example a new model class plus its `add_...` function and tests), guide her step by step through the first two items of that kind. Only after she writes explicitly "ok, ho capito la logica" (or similar) do you write the remaining items yourself.
3. **Small steps.** One roadmap microphase at a time (IDs `AX-001` … `AX-080`). Do not add more than one new concept per step.
4. **She commits and pushes.** Never run `git commit` or `git push` yourself. Give her the commands, including a commit message.
5. When something fails, show the error, explain the cause in plain words, and propose the smallest fix.

## Code rules

- Models are pydantic `BaseModel` classes. Everything is stored inside `CaseModel` in one dictionary per entity, keyed by ID.
- **IDs are assigned by code only**, through `next_id(prefix, digits, existing)`: `P001`, `ORG-01`, `EMP-001`, `EVT-001`, `DOC-001`. A caller never passes an ID.
- **References are IDs, never names.** Every `add_...` function checks that each referenced ID exists and raises `ValueError("Unknown <entity>: <id>")` otherwise.
- **Checks go before the object is created and before `return`.** Code after `return` never runs.
- Dates are stored as `date` (ISO `YYYY-MM-DD`). Amounts are numbers, never text like `"EUR 4.350"`.
- Do not change the existing schema of a model after case model v1 (tag `v1`) without a new version and team agreement.

## Tests

- Every new check gets a test: one for the accepted case and one for each refusal. A refusal test also asserts that nothing was stored.
- Run `python3 -m pytest -v` from the repository root before telling Giulia a step is done. All tests must pass.
- Use realistic HR data from the mock dossier (Jan de Vries, Acme Logistics B.V., M. Bakker), not invented domains.

## Stop and ask Giulia before you

- touch any file outside `case_model/`;
- change a public function that is already in `README.md`;
- add a new dependency to `requirements.txt`;
- make a choice that could become a Decision Log (a design choice where another option would change the outcome of the project).
