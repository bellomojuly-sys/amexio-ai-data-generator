"""BE-05 — the stub chain runs end to end and its output loads with load_case;
a stage that returns the wrong shape stops the chain and names the stage.
"""

import json
from pathlib import Path

import pytest

from case_model.storage import load_case
from pipeline.chain import ChainError, Stage, cm_id_stub, run_chain
from pipeline.contracts import Analysis, CmIdOutput

EXAMPLE = (Path(__file__).resolve().parent.parent
           / "case_model" / "fixtures" / "generator" / "amexio_example" / "employees.json")


def _analysis():
    return Analysis.model_validate(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_chain_runs_and_output_loads_with_load_case(tmp_path):
    out = run_chain(_analysis(), tmp_path)
    assert len(out.cases) == 4
    assert out.cases[0].case_number == "100101"       # IDs from the case model
    loaded = load_case(tmp_path / "100101")
    assert loaded == out.cases[0]                      # saved and reloaded equal


def test_a_wrong_shape_stops_the_chain_and_names_the_stage(tmp_path):
    broken = [
        Stage("cm_id", cm_id_stub, CmIdOutput),
        Stage("plot", lambda cm: "not a CmIdOutput", CmIdOutput),   # wrong shape
    ]
    with pytest.raises(ChainError) as exc:
        run_chain(_analysis(), tmp_path, stages=broken)
    assert exc.value.stage == "plot"
    assert "expected CmIdOutput" in str(exc.value)
