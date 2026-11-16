"""Stub chain: the stages wired in order (BE-05).

The real stages come later (CM ID in BE-09, Plot in BE-16, Valentin's two
stages after). Here each is a **stub** with the right shape, so the chain runs
end to end on AMEXIO's example and the result loads with ``load_case``. The
runner validates the boundary between stages: a stage that returns the wrong
shape stops the chain and names the stage (``ChainError``).

The CM ID stub calls the case model's ``ingest_employees`` (the function the
real stage will use), so the cases it produces carry code-assigned IDs. The
other three stubs pass the cases through unchanged for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from case_model.ingest import ingest_employees
from case_model.storage import save_case

from .contracts import Analysis, CmIdOutput


class ChainError(RuntimeError):
    """A stage returned the wrong shape; the chain stops and names it."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"stage {stage!r}: {message}")


@dataclass
class Stage:
    name: str
    func: Callable[[object], object]
    output_type: type


# --- stub stages ------------------------------------------------------------

def cm_id_stub(analysis: Analysis) -> CmIdOutput:
    """Analysis -> cases with code-assigned IDs (via the case model)."""
    cases, corrections = ingest_employees(analysis.model_dump(by_alias=True))
    return CmIdOutput(cases=cases, corrections=corrections)


def plot_stub(cm: CmIdOutput) -> CmIdOutput:
    """Plot will add a storyline outline per case (BE-16). Stub: pass through."""
    return cm


def dates_stub(cm: CmIdOutput) -> CmIdOutput:
    """Valentin adds dates and participants. Stub: pass through."""
    return cm


def fill_stub(cm: CmIdOutput) -> CmIdOutput:
    """Valentin fills the document texts. Stub: pass through."""
    return cm


STAGES: list[Stage] = [
    Stage("cm_id", cm_id_stub, CmIdOutput),
    Stage("plot", plot_stub, CmIdOutput),
    Stage("dates", dates_stub, CmIdOutput),
    Stage("fill", fill_stub, CmIdOutput),
]


def run_chain(analysis: Analysis, out_dir, stages: list[Stage] = STAGES) -> CmIdOutput:
    """Run the stages in order on `analysis`, validating each boundary, then
    save the cases under `out_dir` (one folder per case). Returns the last
    stage's output.
    """
    value: object = analysis
    for stage in stages:
        value = stage.func(value)
        if not isinstance(value, stage.output_type):
            raise ChainError(
                stage.name,
                f"expected {stage.output_type.__name__}, got {type(value).__name__}",
            )

    out = Path(out_dir)
    for case in value.cases:
        case_dir = out / case.case_number
        case_dir.mkdir(parents=True, exist_ok=True)
        save_case(case, case_dir)
    return value
