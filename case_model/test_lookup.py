"""AX-022 — read one fact by its path; an unknown or ambiguous path fails loud.

The case is AMEXIO's 100101, built through ingest (persona, employment and hire
event with code-assigned IDs). Each refusal checks the right reason (F1).
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from case_model import Money
from case_model.case_model import Employment
from case_model.ingest import ingest_employees
from case_model.lookup import UnknownPath, get_fact

EXAMPLE = (Path(__file__).resolve().parent
           / "fixtures" / "generator" / "amexio_example" / "employees.json")


def _case():
    cases, _ = ingest_employees(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    return cases[0]                      # 100101, Jan de Vries


def _jan_id(case):
    return next(p.id for p in case.personas.values() if p.name == "Jan de Vries")


# --- the accepted paths -----------------------------------------------------

def test_dossier_fact():
    assert get_fact(_case(), "dossier.employee_number") == "100101"


def test_persona_fact():
    case = _case()
    assert get_fact(case, f"personas.{_jan_id(case)}.name") == "Jan de Vries"


def test_employment_fact_by_persona_id():
    case = _case()
    jan = _jan_id(case)
    assert get_fact(case, f"employments.{jan}.salary.amount") == Decimal("4350.00")
    assert get_fact(case, f"employments.{jan}.salary.currency") == "EUR"
    assert get_fact(case, f"employments.{jan}.position") == "Software Developer"


def test_event_fact():
    case = _case()
    hire = next(e.id for e in case.events.values() if e.type == "hire")
    assert str(get_fact(case, f"events.{hire}.date")) == "2021-03-01"


# --- the refusals (one clear error each) ------------------------------------

def test_unknown_collection():
    with pytest.raises(UnknownPath, match="unknown collection"):
        get_fact(_case(), "projects.X1.name")


def test_unknown_id():
    with pytest.raises(UnknownPath, match="no persona 'P999'"):
        get_fact(_case(), "personas.P999.name")


def test_unknown_field():
    case = _case()
    with pytest.raises(UnknownPath, match="cannot read 'nickname'"):
        get_fact(case, f"personas.{_jan_id(case)}.nickname")


def test_no_employment_for_persona():
    # A manager added by ingest has a persona but no employment of their own.
    case = _case()
    managers = [p.id for p in case.personas.values() if p.role == "manager"]
    assert managers, "expected a manager persona in the fixture"
    with pytest.raises(UnknownPath, match="no employment for persona"):
        get_fact(case, f"employments.{managers[0]}.salary.amount")


def test_ambiguous_employment_fails_loud():
    # Two employments for the same persona: the path must raise, not guess.
    case = _case()
    jan = _jan_id(case)
    case.employments.append(Employment(
        persona_id=jan, organisation_id="ORG-01", position="Team Lead",
        department="IT", start_date="2024-01-01", contract_type="Permanent",
        hours=40, salary=Money(amount="5000.00", currency="EUR")))
    with pytest.raises(UnknownPath, match="2 employments for persona"):
        get_fact(case, f"employments.{jan}.salary.amount")


def test_empty_path():
    with pytest.raises(UnknownPath, match="empty path"):
        get_fact(_case(), "")
