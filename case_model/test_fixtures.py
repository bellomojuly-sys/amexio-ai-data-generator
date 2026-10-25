"""BR-11 — every generator fixture goes in, and every case comes back out;
BR-10 — the committed schemas match the code."""

import json

import pytest
from case_model.ingest import EmployeesIn, StorylinesIn, ingest_files, load_cases
from case_model.reference_dossier import FIXTURE_DIR
from case_model.schema import SCHEMA_DIR, SCHEMAS, render

FIXTURES = sorted(d for d in FIXTURE_DIR.parent.iterdir() if (d / "employees.json").is_file())


def test_there_are_fixtures():
    assert {d.name for d in FIXTURES} >= {"amexio_example", "leaver_example"}

@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda d: d.name)
def test_fixture_ingests_and_every_case_loads_back(fixture, tmp_path):
    storylines = fixture / "storylines.json"
    cases, _ = ingest_files(fixture / "employees.json",
                            storylines if storylines.is_file() else None, tmp_path)
    assert load_cases(tmp_path) == cases

def test_a_broken_fixture_fails(tmp_path):
    # A storyline that points at an employee the batch does not have.
    broken = json.loads((FIXTURE_DIR / "storylines.json").read_text())
    broken["storylines"][0]["employeeId"] = "100999"
    (tmp_path / "storylines.json").write_text(json.dumps(broken))
    with pytest.raises(ValueError):
        ingest_files(FIXTURE_DIR / "employees.json", tmp_path / "storylines.json")

@pytest.mark.parametrize("name", list(SCHEMAS))
def test_committed_schema_is_up_to_date(name):
    # If this fails, a model changed: run python3 -m case_model.schema and commit.
    assert (SCHEMA_DIR / name).read_text(encoding="utf-8") == render(name)

def test_input_schemas_describe_the_fixtures():
    for fixture in FIXTURES:
        EmployeesIn.model_validate_json((fixture / "employees.json").read_text())
        StorylinesIn.model_validate_json((fixture / "storylines.json").read_text())
