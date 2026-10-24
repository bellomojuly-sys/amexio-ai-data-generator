"""D4 — the generator's JSON goes in, cases come out (T5, T6)."""

import json

import pytest
from case_model.ingest import ingest_employees, ingest_files, ingest_storylines, load_cases, main
from case_model.reference_dossier import FIXTURE_DIR

LEAVERS = FIXTURE_DIR.parent / "leaver_example"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jan(**overrides):
    employee = {"firstName": "Jan", "lastName": "de Vries", "department": "IT",
                "position": "Software Developer", "isManager": False,
                "hireDate": "2021-03-01", "contractType": "Permanent",
                "hoursPerWeek": 40, "startSalary": 4350,
                "managerName": "M. Bakker (fictional)"}
    return {"company": {"employerName": "Acme Logistics B.V. (fictional)",
                        "trainingProvider": "Training Academy (fictional)"},
            "employees": [{**employee, **overrides}]}


def test_one_case_per_employee_numbered_in_order():
    cases, _ = ingest_employees(_read(FIXTURE_DIR / "employees.json"))
    assert [c.case_number for c in cases] == ["100101", "100102", "100103", "100104"]
    assert cases[0].dossier.folder_title == "100101 Jan de Vries"

def test_numbering_can_start_elsewhere():
    cases, _ = ingest_employees(_read(FIXTURE_DIR / "employees.json"), first_number=200001)
    assert cases[-1].case_number == "200004"

def test_a_case_holds_employee_manager_employer_and_hire():
    cases, _ = ingest_employees(_jan())
    case = cases[0]
    roles = sorted(p.role for p in case.personas.values())
    assert roles == ["employee", "manager"]
    assert str(case.employments[0].salary.amount) == "4350.00"
    assert [e.type for e in case.events.values()] == ["hire"]

def test_department_manager_comes_from_ismanager():
    cases, _ = ingest_employees(_read(LEAVERS / "employees.json"))
    planner = cases[1]
    manager = next(p for p in planner.personas.values() if p.role == "manager")
    assert manager.name == "Femke Visser"
    # The head of the department reports to the director.
    head = next(p for p in cases[0].personas.values() if p.role == "manager")
    assert head.name == "H. de Wit (fictional)"

def test_an_id_in_the_input_is_refused():
    # AX-012 — IDs come from the case model, never from the generator or the LLM.
    with pytest.raises(ValueError, match="IDs are assigned by the case model"):
        ingest_employees(_jan(id="100101"))

def test_a_field_the_shape_does_not_name_is_refused():
    with pytest.raises(ValueError, match="leaves"):
        ingest_employees(_jan(leaves=True))

def test_values_written_differently_are_corrected_and_recorded():
    cases, corrections = ingest_employees(_jan(contractType="permanent", firstName=" Jan"))
    assert cases[0].employments[0].contract_type == "Permanent"
    assert [c.message for c in corrections] == [
        "firstName: extra spaces removed (' Jan' -> 'Jan').",
        "contractType: 'permanent' written as 'Permanent'.",
    ]

def test_a_value_that_cannot_be_placed_is_refused():
    with pytest.raises(ValueError, match="contractType 'Freelance'"):
        ingest_employees(_jan(contractType="Freelance"))

def test_storylines_add_typed_events_with_ids():
    cases, _ = ingest_employees(_read(FIXTURE_DIR / "employees.json"))
    cases, _ = ingest_storylines(cases, _read(FIXTURE_DIR / "storylines.json"))
    jan = cases[0]
    assert [(e.id, e.type) for e in jan.events.values()] == [
        ("EVT-001", "hire"), ("EVT-002", "training"),
        ("EVT-003", "medical_check"), ("EVT-004", "appraisal"),
    ]
    appraisal = jan.events["EVT-004"]
    manager = next(p.id for p in jan.personas.values() if p.role == "manager")
    assert manager in appraisal.participant_ids
    assert str(appraisal.date) == "2026-06-30"

def test_storyline_for_unknown_employee_is_refused():
    cases, _ = ingest_employees(_jan())
    with pytest.raises(ValueError, match="unknown employee '100999'"):
        ingest_storylines(cases, {"storylines": [{"employeeId": "100999", "events": []}]})

def test_two_storylines_for_one_employee_are_refused():
    cases, _ = ingest_employees(_jan())
    story = {"employeeId": "100101", "events": []}
    with pytest.raises(ValueError, match="Two storylines"):
        ingest_storylines(cases, {"storylines": [story, story]})

def test_an_impossible_story_is_refused():
    # The case model's rules (BR-06) hold for generated data too.
    cases, _ = ingest_employees(_jan())
    story = {"employeeId": "100101", "events": [
        {"type": "medical_check", "date": "2020-01-15", "result": "Fit for work"}]}
    with pytest.raises(ValueError, match="before the hire"):
        ingest_storylines(cases, {"storylines": [story]})

def test_training_without_a_provider_is_refused():
    data = _jan()
    del data["company"]["trainingProvider"]
    cases, _ = ingest_employees(data)
    story = {"employeeId": "100101", "events": [
        {"type": "training", "date": "2026-02-20", "course": "Secure Coding Fundamentals",
         "durationDays": 2}]}
    with pytest.raises(ValueError, match="trainingProvider"):
        ingest_storylines(cases, {"storylines": [story]})

def test_command_writes_one_folder_per_employee(tmp_path, capsys):
    main([str(FIXTURE_DIR / "employees.json"), str(FIXTURE_DIR / "storylines.json"),
          "--out", str(tmp_path)])
    assert "wrote 4 cases" in capsys.readouterr().out
    loaded = load_cases(tmp_path)
    assert [c.case_number for c in loaded] == ["100101", "100102", "100103", "100104"]
    assert json.loads((tmp_path / "corrections.json").read_text()) == []

def test_command_refuses_bad_input(tmp_path, capsys):
    bad = tmp_path / "employees.json"
    bad.write_text(json.dumps(_jan(id="P001")))
    with pytest.raises(SystemExit) as stop:
        main([str(bad), "--out", str(tmp_path / "out")])
    assert stop.value.code == 1
    assert "refused" in capsys.readouterr().err
