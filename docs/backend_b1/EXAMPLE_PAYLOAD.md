# Worked example of the contract — AMEXIO 100101 (real data)

Draft for Friday. Every payload below is **real**: the output and the refusals
were produced by running the committed case model
(`python -m case_model.ingest`) on
`case_model/fixtures/generator/amexio_example/`. Nothing here is hand-written to
look nice — it is what the contract actually does today.

The point: the team can *see* the boundaries, not just read them. A stage that
sends the wrong shape is refused with the field named; IDs are assigned only by
code.

---

## A. The HTTP request — `POST /runs` (Daniel → backend)

```json
{
  "analysis": {
    "company": {
      "employerName": "Acme Logistics B.V. (fictional)",
      "trainingProvider": "Training Academy (fictional)",
      "examiner": "Occupational physician (fictional)",
      "absenceService": "Occupational health service (fictional)",
      "directorName": "H. de Wit (fictional)"
    },
    "employees": [
      {"firstName": "Jan", "lastName": "de Vries", "department": "IT",
       "position": "Software Developer", "hireDate": "2021-03-01",
       "startSalary": 4350, "isManager": false, "contractType": "Permanent",
       "hoursPerWeek": 40, "managerName": "M. Bakker (fictional)"}
    ]
  },
  "options": {"fake_llm": true}
}
```

> The exact shape of `analysis` is **Daniel's to confirm (BE-07)**. In this
> example it already carries the company + employee facts in the CM-ID input
> shape, so the mapping is the identity; BE-07 defines the mapping if Daniel's
> analysis looks different. `fake_llm: true` makes the run offline, no API key.

---

## B. The CM-ID boundary — what the LLM proposes / `ingest` receives

**`employees.json`** (the real fixture — the full 4 AMEXIO employees):

```json
{
  "company": {"employerName": "Acme Logistics B.V. (fictional)",
              "trainingProvider": "Training Academy (fictional)",
              "examiner": "Occupational physician (fictional)",
              "absenceService": "Occupational health service (fictional)",
              "directorName": "H. de Wit (fictional)"},
  "employees": [
    {"firstName": "Jan", "lastName": "de Vries", "department": "IT",
     "position": "Software Developer", "hireDate": "2021-03-01", "startSalary": 4350,
     "isManager": false, "contractType": "Permanent", "hoursPerWeek": 40,
     "managerName": "M. Bakker (fictional)"}
    // 100102 Sanne Jansen, 100103 Mohamed El Amrani, 100104 Lisa van den Berg …
  ]
}
```

**`storylines.json`** for 100101 (the Plot boundary — typed events, no IDs):

```json
{"storylines": [{"employeeId": "100101",
  "events": [
    {"type": "training", "date": "2026-02-20", "course": "Secure Coding Fundamentals", "durationDays": 2},
    {"type": "medical_check", "date": "2026-04-14", "result": "Fit for work"}
  ],
  "appraisals": [{"year": 2026, "rating": "Exceeds expectations"}]}]}
```

Note the input has **no IDs**, camelCase, `absence` with `startDate`/`endDate`.
The case model assigns the IDs and turns it into the case below.

---

## C. The `POST /runs` response — `200` (real output)

The backend ran the chain and returned **4 valid cases + a trace**. Here is
100101 in full (one object of `case.schema.json`, the joined four files);
100102–100104 are omitted for length.

```json
{
  "run_id": "GEN-2026-0001",
  "status": "completed",
  "corrections": [],
  "cases": [
    {
      "case_number": "100101",
      "dossier": {"employee_number": "100101", "folder_title": "100101 Jan de Vries", "description": null},
      "personas": {
        "P001": {"id": "P001", "name": "Jan de Vries", "role": "employee", "salutation": null, "date_of_birth": null, "address": null, "organisation_id": "ORG-01"},
        "P002": {"id": "P002", "name": "M. Bakker (fictional)", "role": "manager", "salutation": null, "date_of_birth": null, "address": null, "organisation_id": "ORG-01"},
        "P003": {"id": "P003", "name": "Occupational physician (fictional)", "role": "examiner", "salutation": null, "date_of_birth": null, "address": null, "organisation_id": "ORG-03"}
      },
      "organisations": {
        "ORG-01": {"id": "ORG-01", "name": "Acme Logistics B.V. (fictional)", "kind": "employer", "address": null},
        "ORG-02": {"id": "ORG-02", "name": "Training Academy (fictional)", "kind": "training_provider", "address": null},
        "ORG-03": {"id": "ORG-03", "name": "Occupational health service (fictional)", "kind": "occupational_health", "address": null}
      },
      "employments": [
        {"persona_id": "P001", "organisation_id": "ORG-01", "position": "Software Developer",
         "department": "IT", "start_date": "2021-03-01", "contract_type": "Permanent",
         "hours": 40.0, "salary": {"amount": "4350.00", "currency": "EUR"}}
      ],
      "events": {
        "EVT-001": {"id": "EVT-001", "date": "2021-03-01", "participant_ids": ["P001"], "label": null, "summary": null, "type": "hire"},
        "EVT-002": {"id": "EVT-002", "date": "2026-02-20", "participant_ids": ["P001"], "label": null, "summary": null, "type": "training", "course": "Secure Coding Fundamentals", "duration_days": 2, "provider_id": "ORG-02"},
        "EVT-003": {"id": "EVT-003", "date": "2026-04-14", "participant_ids": ["P001", "P003"], "label": null, "summary": null, "type": "medical_check", "result": "Fit for work"},
        "EVT-004": {"id": "EVT-004", "date": "2026-06-30", "participant_ids": ["P001", "P002"], "label": null, "summary": null, "type": "appraisal", "year": 2026, "rating": "Exceeds expectations", "comment": null}
      },
      "documents": {}
    }
    // … 100102, 100103, 100104 …
  ],
  "trace": [
    {"stage": "cm_id", "ok": true, "cases": 4, "llm": "FakeLLM", "ms": 3},
    {"stage": "plot",  "ok": true, "events_per_case": [4, 3, 5, 4], "llm": "FakeLLM", "ms": 7}
  ]
}
```

What the code did, not the LLM: assigned `P001`–`P003`, `ORG-01`–`ORG-03`,
`EVT-001`–`EVT-004`; added the `hire` event on the start date; linked the
examiner `P003` into the medical check and the manager `P002` into the
appraisal; stored the salary as `Money` (`"4350.00"` + `EUR`); dated the
appraisal 30 June. `documents` is empty until BR-00 (Robin's Q2). `corrections`
is empty because the input was already clean.

---

## D. What the contract refuses (real errors, from the same `ingest`)

Each maps to **HTTP 422, `error.kind = "refused"`**, and names where it failed —
so a teammate fixes it without asking anyone.

| The wrong input | The real error |
|---|---|
| An employee carries an `id` (LLM wrote it) | `employees.0 — IDs are assigned by the case model, not by the generator or the LLM. Remove the id field (got id='P001').` |
| `contractType: "Freelance"` (outside the closed list) | `Employee 100101: contractType 'Freelance' is not one of Permanent, Temporary.` |
| An unknown field `leaves` the shape does not name | `employees.0.leaves — Extra inputs are not permitted` |

This is exactly the class of mismatch that cost us time last week: here it stops
at the boundary, loudly, with the field named — not three stages later.

---

## E. Why this answers "does the contract prevent last week's problem?"

- **One shape, enforced.** The input is validated against
  `input.employees.schema.json` / `input.storylines.schema.json`; a wrong shape
  is refused, not silently re-mapped.
- **IDs only from code.** No two people assign IDs; an LLM-written `id` is
  refused.
- **Every owner has a row** (Part 2 of the proposal) and this example shows that
  row's input and output concretely.
- **Fail loud.** A bad answer stops the run with a named field and nothing
  half-written (BE-10).

Reproduce it:

```bash
python -m case_model.ingest \
  case_model/fixtures/generator/amexio_example/employees.json \
  case_model/fixtures/generator/amexio_example/storylines.json --out /tmp/run
```
