# Demo cases

Case folders written by the dossier generator demo (`generator/demo_dossier_generator`,
`src/case/toCase.ts`), one folder per employee, in the four files of `save_case`.
`test_demo_cases.py` loads every one with `load_case`, so a change on either side that
breaks the shared format fails CI.

Do not edit by hand. Regenerate from the demo with `npm run fixtures`.

| Scenario | What it covers |
| --- | --- |
| `amexio_example` | AMEXIO's four employees and 20 documents (the demo's AMEXIO preset). Input: fixtures/generator/amexio_example. |
| `small_company` | No-AI run, seed 2026: 8 employees, 2 years of history, all 9 document types. Two leavers, a temporary contract made permanent (100108), promotions, sick leave, part time. |
| `leavers` | No-AI run, seed 7: 6 employees, 1 year of history. Three leave (two at the end of a temporary contract), most have sick leave, some work part time. |
