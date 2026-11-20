"""Step 2 · CM ID (contract v1.1 §4): code decides every fact, then the case
model assigns the IDs. Accepted case first, then one refusal per rule."""

import pytest

from case_model.ingest import EmployeeIn
from pipeline.cm_id import CmIdError, cm_id, decide_facts
from pipeline.contracts import PersonasIn


def _personas(n, department="IT", position="Software Developer"):
    return PersonasIn.model_validate({"employees": [
        {"firstName": f"Name{i}", "lastName": "Jansen", "department": department,
         "position": position} for i in range(n)]})


def _mixed(n):
    """n proposed employees, the first two managers of IT and HR."""
    rows = [{"firstName": "Ada", "lastName": "Visser", "department": "IT", "position": "IT Manager"},
            {"firstName": "Bo", "lastName": "Smit", "department": "Human Resources",
             "position": "HR Manager"}]
    rows += [{"firstName": f"N{i}", "lastName": "Bos", "department": "IT",
              "position": "Software Developer"} for i in range(n - 2)]
    return PersonasIn.model_validate({"employees": rows})


def test_cases_get_ids_from_the_case_model(config):
    out = cm_id(_mixed(10), config)
    assert [c.case_number for c in out.cases] == [f"{100101 + i}" for i in range(10)]
    assert all(set(c.personas) >= {"P001"} for c in out.cases)


def test_temporary_and_part_time_shares_are_hit_exactly(config):
    facts = decide_facts(_mixed(10), config)            # 0.2 and 0.3 of 10
    assert sum(f["contractType"] == "Temporary" for f in facts) == 2
    assert sum(f["hoursPerWeek"] < 40 for f in facts) == 3


def test_managers_follow_the_position_and_are_hired_first(config):
    facts = decide_facts(_mixed(10), config)
    assert [f["isManager"] for f in facts[:2]] == [True, True]
    assert not any(f["isManager"] for f in facts[2:])
    latest_manager = max(f["hireDate"] for f in facts[:2])
    assert all(f["hireDate"] >= latest_manager for f in facts[2:])


def test_temporary_contracts_go_to_non_managers_first(config):
    facts = decide_facts(_mixed(10), config)
    assert all(f["contractType"] == "Permanent" for f in facts[:2])


def test_salary_is_inside_the_position_range(config):
    for f in decide_facts(_mixed(10), config):
        low, high = (5500, 7000) if f["position"] == "IT Manager" else \
                    (5000, 6500) if f["position"] == "HR Manager" else (3800, 5200)
        assert low <= f["startSalary"] <= high


def test_hire_dates_are_before_as_of_date(config):
    assert all(f["hireDate"] < "2026-10-31" for f in decide_facts(_mixed(10), config))


def test_the_same_seed_gives_the_same_facts(config):
    assert decide_facts(_mixed(10), config, seed=3) == decide_facts(_mixed(10), config, seed=3)


def test_seed_employees_come_first_and_keep_their_facts(config, amexio_employees):
    seeds = [EmployeeIn.model_validate(e) for e in amexio_employees["employees"]]
    out = cm_id(_personas(6), config, seeds)
    jan = out.cases[0]
    assert jan.case_number == "100101"
    assert jan.personas["P001"].name == "Jan de Vries"
    assert jan.employments[0].salary.amount == 4350


def test_seeds_count_toward_the_shares(config, amexio_employees):
    amexio_employees["employees"][1]["contractType"] = "Temporary"   # one seed is temporary
    seeds = [EmployeeIn.model_validate(e) for e in amexio_employees["employees"]]
    facts = decide_facts(_personas(6), config, seeds)
    # 0.2 of 10 = 2 temporaries in the run: the seed is one, so code adds one.
    assert sum(f["contractType"] == "Temporary" for f in facts) == 1


def test_a_department_outside_the_config_is_refused(config):
    with pytest.raises(CmIdError, match="department 'Sales' is not in the config") as exc:
        decide_facts(_personas(10, department="Sales"), config)
    assert exc.value.field == "employees.0.department"


def test_a_position_outside_the_department_is_refused(config):
    with pytest.raises(CmIdError, match="'HR Advisor' is not a position of department 'IT'"):
        decide_facts(_personas(10, position="HR Advisor"), config)


def test_a_count_that_does_not_add_up_is_refused(config):
    with pytest.raises(CmIdError, match="but employeeCount is 10") as exc:
        decide_facts(_personas(9), config)
    assert exc.value.field == "employees"
