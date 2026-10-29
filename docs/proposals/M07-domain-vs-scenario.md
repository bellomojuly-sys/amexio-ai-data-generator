# M07 / AX-036 — the line between domain and scenario (proposal for the team)

Draft, 29 October 2026 · author: Giulia (Datanova) · study objective A-E.

**Status: proposal, not a decision.** AX-036 is a decision the team takes
together; this is what I bring to the meeting on **Fri 30 Oct**, next to the B1
contract and the placeholder syntax (AX-021). It does **not** change the
case-model schema and does **not** close any microphase. The real config code
(AX-037–AX-040) is written only after the team agrees this line.

---

## The question

`config.json` (AX-037) will carry both a `domain` and a `scenario`. Before we
write the loader we must agree **what belongs to which**, so that:

- anything HR-specific lives in the **domain** (and a second domain later, M10/M11,
  is pure configuration, no code change — Gate M10);
- the choices of **one run** live in the **scenario**;
- Valentin's validator, Mike's "run from config" (AX-040) and the batch work
  (M12) all read the same two levels.

Today the fixtures already show the two levels without a name for them:
`amexio_example`, `small_company` and `leavers` (`case_model/fixtures/demo_cases/`)
are **three scenarios of the same HR domain** — they differ in how many
employees, how many years of history, who leaves, temporary-vs-permanent,
sick leave, part time and the seed, but share the same entity types, document
types, event types and coherence rules.

## Proposed line — three buckets

**1. Domain (HR): the vocabulary and the rules of this *kind* of dossier.**
What an HR dossier *is*, independent of any single run:

- the entity types (persona, organisation, employment, event, document);
- the closed list of **event types** (hire, appraisal, medical_check, absence,
  termination, …);
- the closed list of **document types** and their metadata attributes
  (employment_contract, payslip, medical_check, performance_appraisal,
  training_certificate, … 9 in total);
- the **coherence rules** as rules (net = gross − wage tax; payslip gross =
  contract salary; no document before the start date; exactly one hire, first;
  nothing after termination);
- which roles exist (manager, examiner, provider).

Changing anything here gives a **different kind of dossier** → it is domain, and
it belongs in the HR template (M10), never in a run's config.

**2. Scenario: the shape of *one run* inside the domain.**
The same HR vocabulary, a different story:

- number of dossiers and documents per dossier (M12, AX-061);
- time span (how many years of history) and the as-of date;
- **outcome(s)**: leaver, temporary→permanent, promotion, sick leave, part time —
  the things that make `leavers` differ from `small_company`;
- **which document types to include, in process order** (AX-038) — a subset of
  the domain's list;
- language / locale, target system (OpenText), seed, AI vs no-AI.

**3. Rule parameters: the numbers the domain's rules need to compute.**
The grey zone, and the reason this decision is worth writing down. The rules
are domain (bucket 1); the **values they plug in** can change per run:

- wage-tax rate, medical-check interval, appraisal review cycle, payslip payment
  day (the 25th).

**Proposal:** each rule parameter has a **default in the domain template**, and a
scenario **may override** it. So `wage_tax_rate` is HR's default, but a run can
set a different rate without touching code or the domain. This keeps bucket 1
free of magic numbers and keeps a run reproducible from its own config.

## The one-line test (for AX-036)

> If changing it would give a **different kind of dossier**, it is **domain**.
> If it varies **one run** of the same kind, it is **scenario**.
> If it is a **number a domain rule needs**, it is a **rule parameter**: domain
> default, scenario override.

## Classification — concrete examples (the "two teammates agree" check)

The roadmap's verify for AX-036 is that two examples are classified the same way
by a teammate. Here is the table to test that on Friday:

| Example | Bucket | Why |
|---|---|---|
| Add a new document type `disciplinary_letter` | **Domain** | changes what an HR dossier can contain |
| Add a new event type | **Domain** | new vocabulary |
| "net = gross − wage tax" | **Domain** (rule) | true for every HR run |
| The examiner signs the medical check | **Domain** | a role of the case model |
| wage-tax rate = 0.37 | **Rule parameter** | a number the rule plugs in |
| medical-check interval = 24 months | **Rule parameter** | a number a derivation needs |
| Include only 5 of the 9 document types | **Scenario** (AX-038) | one run's subset |
| 8 employees, 2 years of history, seed 2026 | **Scenario** | the `small_company` shape |
| This run is a leaver / temp→permanent | **Scenario** | outcome of one run |
| Language = nl vs en | **Scenario** | formatting of one run (A-B) |
| 1 dossier × 5 docs vs 10 × 20 | **Scenario** (M12) | volume of one run |

**Open / to confirm with Valentin (AX-039):** the *set* of metadata fields is
domain; whether a given field is **required or optional for a run** feels like
scenario/config (his validator reads the list). Flag to agree, not to decide
alone.

## Shape of `config.json` (sketch for AX-037/038/039 — to agree, not final)

```json
{
  "domain": "hr",
  "scenario": {
    "outcome": "leaver",
    "language": "nl",
    "target_system": "opentext",
    "dossiers": 1,
    "documents_per_dossier": 5,
    "document_types": ["employment_contract", "payslip", "medical_check",
                       "performance_appraisal", "training_certificate"],
    "as_of_date": "2026-09-30",
    "seed": 2026
  },
  "rule_overrides": {
    "wage_tax_rate": "0.37",
    "medical_check_interval_months": 24
  }
}
```

- `domain` names the HR template (M10); the template holds the vocabulary, the
  rules and the **default** rule parameters.
- `scenario` is one run; `document_types` is the ordered subset (AX-038).
- `rule_overrides` is optional; empty means "use the domain defaults".
- A missing or wrong field fails with a clear message (AX-037).

## What the team must confirm

1. The three-bucket line and the one-line test (AX-036) — **Mike, Valentin, Daniel**.
2. Rule parameters = domain default + scenario override — **Mike, Robin**
   (Robin listed wage-tax rate and medical-check interval).
3. Required-vs-optional metadata = scenario/config, validator reads it (AX-039) —
   **Valentin**.
4. `config.json` as the single input to a run (AX-040) — **Mike**.

## Not in this draft (on purpose)

- No config loader code (AX-037) and no HR template yet (M10): written after the
  line is agreed, with guidance, so I can explain each field.
- No schema change. This draft is the input to the AX-036 decision only.
