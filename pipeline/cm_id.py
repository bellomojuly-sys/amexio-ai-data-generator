"""Step 2 · CM ID: from proposed personas to cases with IDs (contract v1.1 §4).

**Owner: Giulia.** The LLM proposed names, department and position
(``PersonasIn``). Code decides every fact (rule 2), by the HR template's rules:

| Fact | Rule |
|---|---|
| ``contractType`` | ``Temporary`` for ``temporaryShare`` of the run (rounded), the rest ``Permanent`` |
| ``hoursPerWeek`` | part time (24 or 32) for ``partTimeShare`` of the run (rounded), the rest 40 |
| ``isManager`` | from the position's ``isManagerRole`` |
| ``startSalary`` | whole euros inside the position's ``salaryMin``–``salaryMax`` |
| ``hireDate`` | before ``asOfDate``; managers get the earliest dates |

"Of the run" counts the seed employees too: their own facts count toward the
shares, and the proposed employees make up the rest. Then CM ID builds
``EmployeesIn`` (seeds first, so the reference 100101 keeps its number) and
calls the case model's ``ingest_employees``, which assigns the personnel numbers
and the ``P`` and ``ORG`` IDs.

A department or position outside the config is refused, naming the employee and
the field (a value code cannot place is never invented). Choices that need
chance use ``random.Random(seed)``, so the same run gives the same cases.
"""

from __future__ import annotations

import datetime as dt
import random
from collections.abc import Sequence

from case_model.ingest import EmployeeIn, ingest_employees

from .contracts import CmIdOutput, PersonasIn, RunConfig

FULL_TIME_HOURS = 40.0
PART_TIME_HOURS = (24.0, 32.0)
# The config has no earliest hire date; hires fall in the 10 years before asOfDate.
HIRE_WINDOW_DAYS = 10 * 365
# Nobody is hired in the last month before asOfDate: their dossier would be empty.
LATEST_HIRE_GAP_DAYS = 30


class CmIdError(ValueError):
    """A proposed employee code cannot place; names the employee and the field."""

    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field


def _share(share: float, total: int, already: int, available: int) -> int:
    """How many of the ``available`` new employees must have the property so
    that the run has ``round(share * total)``, given ``already`` seeds have it."""
    return max(0, min(available, round(share * total) - already))


def decide_facts(personas: PersonasIn | None, config: RunConfig,
                 seeds: Sequence[EmployeeIn] = (), seed: int = 0) -> list[dict]:
    """The employees JSON entries (camelCase) for the proposed personas, with
    every fact decided by code. Raises ``CmIdError`` on a department or position
    outside the config, or a count that does not add up to ``employeeCount``."""
    proposed = personas.employees if personas else []
    total = config.employee_count
    if len(proposed) + len(seeds) != total:
        raise CmIdError(
            f"{len(proposed)} proposed + {len(seeds)} seed employees, "
            f"but employeeCount is {total}",
            field="employees",
        )
    rng = random.Random(seed)

    positions = []
    for i, p in enumerate(proposed):
        if not any(d.name == p.department for d in config.departments):
            raise CmIdError(f"employees[{i}]: department {p.department!r} is not in the config",
                            field=f"employees.{i}.department")
        position = config.position(p.department, p.position)
        if position is None:
            raise CmIdError(
                f"employees[{i}]: position {p.position!r} is not a position of "
                f"department {p.department!r}",
                field=f"employees.{i}.position",
            )
        positions.append(position)

    n = len(proposed)
    managers = [i for i in range(n) if positions[i].is_manager_role]
    others = [i for i in range(n) if not positions[i].is_manager_role]

    # Temporary and part-time contracts go to non-managers first.
    temporary = set(_pick(others, managers, _share(
        config.temporary_share, total,
        sum(s.contract_type.lower() == "temporary" for s in seeds), n), rng))
    part_time = set(_pick(others, managers, _share(
        config.part_time_share, total,
        sum(s.hours_per_week < FULL_TIME_HOURS for s in seeds), n), rng))

    # Hire dates: n dates in the window, earliest to the managers.
    latest = config.as_of_date - dt.timedelta(days=LATEST_HIRE_GAP_DAYS)
    earliest = config.as_of_date - dt.timedelta(days=HIRE_WINDOW_DAYS)
    span = (latest - earliest).days
    dates = sorted(earliest + dt.timedelta(days=rng.randint(0, span)) for _ in range(n))
    order = managers + rng.sample(others, len(others))
    hire = {i: dates[k] for k, i in enumerate(order)}

    out = []
    for i, p in enumerate(proposed):
        pos = positions[i]
        out.append({
            "firstName": p.first_name,
            "lastName": p.last_name,
            "department": p.department,
            "position": p.position,
            "isManager": pos.is_manager_role,
            "hireDate": hire[i].isoformat(),
            "contractType": "Temporary" if i in temporary else "Permanent",
            "hoursPerWeek": rng.choice(PART_TIME_HOURS) if i in part_time else FULL_TIME_HOURS,
            "startSalary": rng.randint(int(pos.salary_min), int(pos.salary_max)),
        })
    return out


def _pick(first: list[int], then: list[int], k: int, rng: random.Random) -> list[int]:
    """``k`` indexes, drawn from ``first`` before ``then``."""
    a = rng.sample(first, min(k, len(first)))
    return a + rng.sample(then, k - len(a))


def cm_id(personas: PersonasIn | None, config: RunConfig,
          seeds: Sequence[EmployeeIn] = (), seed: int = 0,
          first_number: int = 100101) -> CmIdOutput:
    """Step 2: decide the facts, then let the case model assign the IDs."""
    employees = [s.model_dump(by_alias=True, mode="json", exclude_none=True) for s in seeds]
    employees += decide_facts(personas, config, seeds, seed)
    data = {
        "company": config.company.model_dump(by_alias=True, exclude_none=True),
        "employees": employees,
    }
    cases, corrections = ingest_employees(data, first_number)
    return CmIdOutput(cases=cases, corrections=corrections)
