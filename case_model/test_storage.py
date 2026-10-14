"""AX-018 — save a case to files and load it back; the two are equal."""

import json

from case_model.reference_dossier import build_reference_case
from case_model.storage import load_case, save_case


def test_round_trip_is_equal(tmp_path):
    case = build_reference_case()
    save_case(case, tmp_path)
    assert load_case(tmp_path) == case

def test_the_four_files_are_written(tmp_path):
    case = build_reference_case()
    save_case(case, tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"case.json", "cast.json", "storyline.json", "documents.json"}

def test_files_are_valid_json_and_split_as_documented(tmp_path):
    case = build_reference_case()
    save_case(case, tmp_path)
    case_json = json.loads((tmp_path / "case.json").read_text())
    cast_json = json.loads((tmp_path / "cast.json").read_text())
    assert case_json["case_number"] == "100101"
    assert set(cast_json) == {"personas", "organisations", "employments"}

def test_saving_is_stable(tmp_path):
    # Same case saved twice gives identical bytes (deterministic output).
    case = build_reference_case()
    first = tmp_path / "a"
    second = tmp_path / "b"
    save_case(case, first)
    save_case(case, second)
    for name in ("case.json", "cast.json", "storyline.json", "documents.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
