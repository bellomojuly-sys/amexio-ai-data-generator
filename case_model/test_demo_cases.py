"""The demo's cases load in the case model (bridge, R2/R3; BR-11 for the demo side).

The dossier generator demo (generator/demo_dossier_generator) writes its own
case folders with ``src/case/toCase.ts``. ``npm run fixtures`` commits a few
of them under ``fixtures/demo_cases/<scenario>/<number>/``. These tests prove
that both sides still agree on the format:

- every demo case folder loads with ``load_case``, and saving it again gives
  the same bytes (the demo writes exactly what ``save_case`` writes);
- the demo's run, given to ``ingest`` as input, gives the same cases (the
  documents aside: ingest does not make documents) — both paths end in the
  same format;
- the demo's 100101 holds the same facts as the reference case (BR-15);
- a case broken on purpose is refused (``fixtures/broken_demo_cases.json``;
  the demo's own pre-check is tested on the same list).

The fixtures are made by the demo; regenerate them there, do not edit them.
"""

import copy
import json
import shutil
from pathlib import Path

import pytest
from case_model.ingest import ingest_files
from case_model.reference_dossier import build_reference_case
from case_model.storage import load_case, save_case

FIXTURES = Path(__file__).with_name("fixtures")
DEMO_CASES = FIXTURES / "demo_cases"
BROKEN = json.loads((FIXTURES / "broken_demo_cases.json").read_text(encoding="utf-8"))
FILES = ("case.json", "cast.json", "storyline.json", "documents.json")

SCENARIOS = sorted(d for d in DEMO_CASES.iterdir() if d.is_dir())
CASE_FOLDERS = sorted(c for s in SCENARIOS for c in s.iterdir() if (c / "case.json").is_file())

# The ingest input of each scenario: the AMEXIO example is Giulia's own fixture,
# the others are written by the demo next to it (generator/demo_<scenario>).
INPUTS = {
    s.name: FIXTURES / "generator" / ("amexio_example" if s.name == "amexio_example" else f"demo_{s.name}")
    for s in SCENARIOS
}


def _cases(scenario):
    return [load_case(d) for d in sorted(scenario.iterdir()) if (d / "case.json").is_file()]


def test_there_are_demo_cases():
    assert {s.name for s in SCENARIOS} >= {"amexio_example", "small_company", "leavers"}
    assert all(any(s.iterdir()) for s in SCENARIOS)


@pytest.mark.parametrize("folder", CASE_FOLDERS, ids=lambda d: f"{d.parent.name}/{d.name}")
def test_demo_case_loads(folder, tmp_path):
    case = load_case(folder)
    assert case.case_number == folder.name == case.dossier.employee_number
    # The demo writes the documents too, each with an event unless it recurs.
    assert case.documents
    # Same bytes as save_case: the demo's writer and ours are interchangeable.
    # (Line endings aside: a Windows checkout may turn them into CRLF.)
    save_case(case, tmp_path)
    for name in FILES:
        theirs = (folder / name).read_bytes().replace(b"\r\n", b"\n")
        assert (tmp_path / name).read_bytes() == theirs, name


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda d: d.name)
def test_ingest_gives_the_same_cases(scenario):
    source = INPUTS[scenario.name]
    ingested, _ = ingest_files(source / "employees.json", source / "storylines.json")
    demo = _cases(scenario)
    assert [c.case_number for c in ingested] == [c.case_number for c in demo]
    for mine, theirs in zip(ingested, demo):
        assert mine == theirs.model_copy(update={"documents": {}}), mine.case_number


def test_demo_100101_holds_the_reference_facts():
    # BR-15 — the generator's 100101, written as a case, against the reference.
    demo = load_case(DEMO_CASES / "amexio_example" / "100101")
    assert demo.model_copy(update={"documents": {}}) == build_reference_case()


def test_a_changed_salary_is_noticed():
    demo = load_case(DEMO_CASES / "amexio_example" / "100101")
    job = demo.employments[0]
    changed = demo.model_copy(update={
        "documents": {},
        "employments": [job.model_copy(update={"salary": job.salary.model_copy(update={"amount": 4351})})],
    })
    assert changed != build_reference_case()


def _apply(data, change):
    """One change from broken_demo_cases.json on the parsed JSON of one file."""
    if "rename" in change:
        *parents, key = change["rename"]
        target = data
        for step in parents:
            target = target[step]
        part = target.pop(key)
        part["id"] = change["to"]
        target[change["to"]] = part
        return
    *parents, key = change["path"]
    target = data
    for step in parents:
        target = target[step]
    if change.get("delete"):
        del target[key]
    else:
        target[key] = copy.deepcopy(change["value"])


def test_the_base_of_the_broken_cases_loads():
    load_case(FIXTURES / BROKEN["base"])


@pytest.mark.parametrize("broken", BROKEN["cases"], ids=lambda b: b["name"])
def test_a_broken_demo_case_fails(broken, tmp_path):
    shutil.copytree(FIXTURES / BROKEN["base"], tmp_path, dirs_exist_ok=True)
    for change in broken["changes"]:
        path = tmp_path / change["file"]
        data = json.loads(path.read_text(encoding="utf-8"))
        _apply(data, change)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match=broken["error"]):
        load_case(tmp_path)
