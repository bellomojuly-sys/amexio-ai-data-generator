"""BE-03 — the stage contracts accept a real payload and refuse broken ones.

Each refusal test checks the right reason (a named field or rule), not just that
something raised (F1). The accepted case is AMEXIO's own example, the same file
the case model ingests.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from case_model import Case
from case_model.ingest import ingest_employees
from pipeline import schema
from pipeline.contracts import Analysis, CmIdOutput

EXAMPLE = (Path(__file__).resolve().parent.parent
           / "case_model" / "fixtures" / "generator" / "amexio_example" / "employees.json")


def _example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


# --- Analysis: the accepted case -------------------------------------------

def test_analysis_accepts_amexio_example():
    analysis = Analysis.model_validate(_example())
    assert analysis.company.employer_name.startswith("Acme Logistics")
    assert len(analysis.employees) == 4
    jan = analysis.employees[0]
    assert jan.first_name == "Jan"
    assert str(jan.hire_date) == "2021-03-01"   # ISO string -> date
    assert jan.manager_name and "Bakker" in jan.manager_name


# --- Analysis: one refusal per rule ----------------------------------------

def test_analysis_refuses_an_id_from_the_llm():
    data = _example()
    data["employees"][0]["id"] = "P001"          # the LLM must not assign IDs
    with pytest.raises(ValidationError, match="id"):
        Analysis.model_validate(data)


def test_analysis_refuses_an_unknown_field():
    data = _example()
    data["employees"][0]["salaryBonus"] = 500    # a field the shape does not name
    with pytest.raises(ValidationError, match="salaryBonus|[Ee]xtra"):
        Analysis.model_validate(data)


def test_analysis_refuses_a_non_iso_date():
    data = _example()
    data["employees"][0]["hireDate"] = "01/03/2021"   # AX-013
    with pytest.raises(ValidationError, match="hireDate|date"):
        Analysis.model_validate(data)


def test_analysis_refuses_a_non_positive_salary():
    data = _example()
    data["employees"][0]["startSalary"] = 0           # start_salary gt=0
    with pytest.raises(ValidationError, match="startSalary|greater than 0"):
        Analysis.model_validate(data)


def test_analysis_refuses_an_empty_employee_list():
    data = _example()
    data["employees"] = []                            # min_length=1
    with pytest.raises(ValidationError, match="employees|at least 1"):
        Analysis.model_validate(data)


# --- CmIdOutput: it carries the case model's own cases and corrections ------

def test_cm_id_output_wraps_cases_and_corrections():
    cases, corrections = ingest_employees(_example())
    out = CmIdOutput(cases=cases, corrections=corrections)
    assert len(out.cases) == 4
    assert all(isinstance(c, Case) for c in out.cases)
    assert out.cases[0].case_number == "100101"       # IDs come from the case model


def test_cm_id_output_corrections_default_to_empty():
    cases, _ = ingest_employees(_example())
    out = CmIdOutput(cases=cases)
    assert out.corrections == []


# --- The committed JSON Schema matches the model (no drift) -----------------

def test_analysis_schema_matches_the_model():
    committed = (schema.SCHEMA_DIR / "analysis.schema.json").read_text(encoding="utf-8")
    assert committed == schema.render("analysis.schema.json"), (
        "pipeline/schema/analysis.schema.json is stale; run python3 -m pipeline.schema"
    )
