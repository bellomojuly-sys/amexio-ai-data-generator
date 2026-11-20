"""Step 3 · Plot: the storyline outline of each case (contract v1.1 §5).

**Owner: Giulia.** Per employee number, 1–10 **slots**, each with a key from code
(``S01``, ``S02``, …) and every value code decides: the event type and the
closed-list values (appraisal rating, contract-change kind, the new position on
a promotion, a training's ``durationDays`` — fix 2). No dates, participants or
IDs: Dates & participants (Valentin) adds them.

Coherence between events is a property of the plot, so it stays in code:

- one appraisal per year whose 30 June falls between the hire and ``asOfDate``
  (at most the last four);
- a temporary contract is made permanent after a year;
- a promotion only after an "Exceeds expectations" appraisal, to a better-paid
  non-manager position of the same department;
- a training only when the company names a training provider;
- a medical check after two years; nothing after a termination (``CaseOutline``).

Chance uses ``random.Random(seed)`` forked per employee, so a run is repeatable.
The config has no leaver share yet, so Plot plans no termination (open question
in ``docs/PIPELINE_CONTRACT.md`` §10).
"""

from __future__ import annotations

import datetime as dt
import random

from case_model import Case

from .contracts import CmIdOutput, PlotOutline, RunConfig

MAX_SLOTS = 10
MAX_APPRAISALS = 4
RATINGS = ["Below expectations", "Meets expectations", "Exceeds expectations"]
RATING_WEIGHTS = [15, 60, 25]


def _years(hire: dt.date, as_of: dt.date) -> float:
    return (as_of - hire).days / 365.25


def outline_case(case: Case, config: RunConfig, rng: random.Random) -> dict:
    """The outline of one case, as the ``CaseOutline`` JSON (camelCase)."""
    job = case.employments[0]
    hire, as_of = job.start_date, config.as_of_date
    years = _years(hire, as_of)
    slots: list[dict] = []

    if job.contract_type == "Temporary" and years >= 1:
        slots.append({"type": "contract_change", "change": "made_permanent"})

    trainings = rng.randint(0, min(2, int(years) + 1)) if config.company.training_provider else 0
    for _ in range(trainings):
        slots.append({"type": "training", "durationDays": rng.randint(1, 5)})

    appraisal_years = [y for y in range(hire.year, as_of.year + 1)
                       if hire < dt.date(y, 6, 30) <= as_of][-MAX_APPRAISALS:]
    ratings = rng.choices(RATINGS, RATING_WEIGHTS, k=len(appraisal_years))
    for year, rating in zip(appraisal_years, ratings):
        slots.append({"type": "appraisal", "year": year, "rating": rating})

    if years >= 1:
        slots.append({"type": "contract_change", "change": "salary_review"})

    if ratings and ratings[-1] == "Exceeds expectations":
        better = _better_position(config, job.department, job.position)
        if better:
            slots.append({"type": "contract_change", "change": "promotion",
                          "newPosition": better})

    if years >= 2:
        slots.append({"type": "medical_check"})
    if rng.random() < 0.3:
        slots.append({"type": "absence"})
    if not slots:
        slots.append({"type": "medical_check"})

    # Over ten: drop the oldest appraisals first.
    while len(slots) > MAX_SLOTS:
        oldest = next(i for i, s in enumerate(slots) if s["type"] == "appraisal")
        slots.pop(oldest)

    for k, slot in enumerate(slots, 1):
        slot["slot"] = f"S{k:02d}"
    return {"employeeNumber": case.case_number, "slots": slots}


def _better_position(config: RunConfig, department: str, title: str) -> str | None:
    """A better-paid non-manager position in the same department, if any."""
    current = config.position(department, title)
    if current is None:
        return None
    dep = next(d for d in config.departments if d.name == department)
    better = [p for p in dep.positions
              if not p.is_manager_role and p.salary_max > current.salary_max]
    return min(better, key=lambda p: p.salary_max).title if better else None


def plot(cm: CmIdOutput, config: RunConfig, seed: int = 0) -> PlotOutline:
    """Step 3: one outline per case, validated as ``PlotOutline``."""
    rng = random.Random(seed)
    return PlotOutline.model_validate({"outlines": [
        outline_case(case, config, random.Random(rng.random()))
        for case in cm.cases
    ]})
