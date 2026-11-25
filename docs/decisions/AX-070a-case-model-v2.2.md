# [DL] Which rules does the case model add in v2.2, and how?

Date: 2026-11-25 · Microphase: AX-070a · Study objective: A-A (review), F2 · Decided by: Giulia, contract change to be confirmed by the team

## Context

The code review of 25 Nov (case model on `main`, v2.1 + GD-05) found ten gaps
that no test caught: `fill_text` printed a whole record with its internal
IDs, `case_number` was never checked, hours and salaries could be zero or
negative, a persona could hold two employments, a notice date could fall after
the last working day, a wrong print format crashed the run, and the fact
generator could produce values outside its own bounds. The integration trial
with Daniel's studio and Robin's demo is next week, so the gaps had to close
first. Closing them changes what the case model refuses, so the contract gets
a new version (v2.2; domain contract 1.2).

## Options

1. **`case_number`.** (a) Must equal `dossier.employee_number`: one number per
   case, no field removed; old files stay readable. (b) Drop `case_number` and
   read the dossier's number: cleaner, but every saved case and Robin's types
   change. → (a).
2. **Notice date.** (a) A field option `not_after_event` in the domain
   configuration: any domain can use it, HR sets it on `notice_date`. (b) A
   hard-coded HR check on `termination.notice_date`: shorter, but goes against
   v2.0 (the rules are data). → (a).
3. **Money fact with no whole euro between min and max.** (a) Raise
   `CannotGenerate` naming the field. (b) Fall back to cents. AMEXIO's
   documents print whole euros, and such a range is almost surely a
   configuration mistake. → (a).
4. **Whole records in `fill_text`.** (a) Refuse any model value except `Money`.
   (b) Print a chosen field (e.g. `name`) for a persona: convenient, but a
   hidden rule the template author cannot see. → (a).

## Decision

Options 1a, 2a, 3a, 4a. Hours, salaries, `new_hours` and `new_salary` must be
above zero (`gt` allowed on money fields). One employment per persona.
Integer bounds must be whole numbers. A format that does not fit the value is
reported per placeholder.

## Why

Each rule has a test for the accepted case and one for each refusal
(`case_model/test_v22_rules.py`, 48 tests). Three rules were broken on purpose
and the right test failed each time. Robin's Demo-Generator branch, merged
with v2.2, still passes (545 passed, 1 skipped), so the change is safe for his
PR.

## Consequences

- Daniel: his analysis must give `hoursPerWeek` > 0. A fixed value for a whole
  dossier goes through a "fact" field with a constant value, not through the
  studio's preview values (proposal sent on 25 Nov).
- Robin: `fill_text` now refuses `{{ personas.P001 }}` with "a whole Persona:
  ... not one fact"; his check keeps working.
- Valentin (Fill): a template's format map that does not fit a value now gives
  `UnresolvedPlaceholders` naming the path, not a `TypeError`.
- Every module: a case whose `case_number` differs from its employee number is
  refused when it is loaded.

## Evidence

Commit `dde1fc3` on branch `claude/confident-clarke-ck1jjh` (team repo);
`case_model/README.md` section "v2.1 → v2.2"; `docs/DOMAIN_CONTRACT.md` v1.2.
