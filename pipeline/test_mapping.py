"""BE-07 — Daniel's sample analysis maps to the ingest input; an unknown field
is refused.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from case_model.ingest import ingest_employees
from pipeline.mapping import map_analysis

EXAMPLE = (Path(__file__).resolve().parent.parent
           / "case_model" / "fixtures" / "generator" / "amexio_example" / "employees.json")


def _example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_sample_analysis_maps_and_ingests():
    data = map_analysis(_example())
    assert set(data) == {"company", "employees"}
    cases, _ = ingest_employees(data)          # the mapped dict is accepted
    assert [c.case_number for c in cases] == ["100101", "100102", "100103", "100104"]


def test_unknown_field_is_refused():
    data = _example()
    data["employees"][0]["salaryBonus"] = 500
    with pytest.raises(ValidationError, match="salaryBonus|[Ee]xtra"):
        map_analysis(data)


def test_an_id_is_refused():
    data = _example()
    data["company"]["id"] = "ORG-01"           # AX-012
    with pytest.raises(ValidationError, match="id"):
        map_analysis(data)
