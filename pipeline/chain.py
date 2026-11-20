"""The chain: steps 1–8 of pipeline contract v1.1, in fixed order (§3).

``run_chain`` takes a ``RunRequest`` and an LLM client and runs:

| # | Step | Kind | Owner | Here |
|---|---|---|---|---|
| 1 | personas | llm | Robin | ``generation.propose_personas`` (reference version) |
| 2 | cm_id | code | Giulia | ``cm_id.cm_id`` |
| 3 | plot | code | Giulia | ``plot.plot`` |
| 4 | event_content | llm | Robin | ``generation.write_event_content`` (reference version) |
| 5 | dates_participants | code | Valentin | stub → ``ingest_storylines`` |
| 6 | document_plan | code | Giulia | ``document_plan.document_plan`` |
| 7 | document_text | llm | Robin | ``generation.write_document_text`` (reference version) |
| 8 | fill | code | Valentin | stub (checks every placeholder resolves) |

Each step's output is checked against its contract type: a step that returns
the wrong shape stops the chain with ``ChainError`` naming the step. Any error
in a step stops the run too, and nothing is saved (rule 5). Every step adds one
trace line, and every LLM call one more (§8).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from case_model.storage import save_case

from . import fake_answers
from .cm_id import cm_id
from .contracts import (
    CmIdOutput,
    DocumentPlan,
    DocumentTexts,
    ErrorBody,
    EventContentIn,
    PersonasIn,
    PlotOutline,
    RunRequest,
    RunResult,
    TraceLine,
)
from .document_plan import document_plan
from .generation import propose_personas, write_document_text, write_event_content
from .llm import FakeLLM, LLMClient, LLMError
from .plot import plot
from .valentin_stubs import dates_and_participants_stub, fill_stub


class ChainError(RuntimeError):
    """A step failed or returned the wrong shape; the chain stops and names it."""

    def __init__(self, stage: str, message: str, kind: str = "chain",
                 field: str | None = None, trace: list[TraceLine] | None = None):
        self.stage = stage
        self.kind = kind
        self.field = field
        self.trace = trace or []
        super().__init__(f"stage {stage!r}: {message}")

    def body(self) -> ErrorBody:
        """The contract's one error shape (§3)."""
        return ErrorBody.model_validate({"error": {
            "kind": self.kind, "stage": self.stage,
            "message": str(self), "field": self.field,
        }})


@dataclass
class RunState:
    request: RunRequest
    llm: LLMClient
    seed: int = 0
    out: dict = field(default_factory=dict)   # step name -> its output


@dataclass
class Stage:
    name: str
    kind: str                         # "llm" or "code"
    func: Callable[[RunState], object]
    output_type: type


def _personas(s: RunState):
    seeds = len(s.request.seed_employees or [])
    count = s.request.config.employee_count - seeds
    return propose_personas(s.request.config, s.llm, count) if count else None


def _document_text(s: RunState):
    cases = {c.case_number: c for c in s.out["dates_participants"].cases}
    return DocumentTexts(texts=[
        write_document_text(cases[p.employee_number], p, s.llm)
        for p in s.out["document_plan"].plans if p.documents
    ])


STAGES: list[Stage] = [
    Stage("personas", "llm", _personas, (PersonasIn, type(None))),
    Stage("cm_id", "code", lambda s: cm_id(s.out["personas"], s.request.config,
                                           s.request.seed_employees or [], s.seed), CmIdOutput),
    Stage("plot", "code", lambda s: plot(s.out["cm_id"], s.request.config, s.seed), PlotOutline),
    Stage("event_content", "llm", lambda s: write_event_content(
        s.out["cm_id"].cases, s.out["plot"], s.llm), EventContentIn),
    Stage("dates_participants", "code", lambda s: dates_and_participants_stub(
        s.out["cm_id"], s.out["plot"], s.out["event_content"], s.request.config), CmIdOutput),
    Stage("document_plan", "code", lambda s: document_plan(s.out["dates_participants"]),
          DocumentPlan),
    Stage("document_text", "llm", _document_text, DocumentTexts),
    Stage("fill", "code", lambda s: fill_stub(s.out["dates_participants"],
                                              s.out["document_text"]), CmIdOutput),
]


def _type_name(t) -> str:
    return " or ".join(x.__name__ for x in t) if isinstance(t, tuple) else t.__name__


def run_chain(request: RunRequest, llm: LLMClient | None = None, out_dir=None,
              run_id: str = "GEN-2026-0001", seed: int = 0,
              stages: list[Stage] = STAGES) -> RunResult:
    """Run steps 1–8 on ``request``. Without ``llm``, ``options.fake_llm`` must
    be true and the run uses ``FakeLLM`` with the deterministic fake answers.
    With ``out_dir``, the cases are saved there (one folder per case) only after
    every step succeeded."""
    if llm is None:
        if not request.options.fake_llm:
            raise ChainError("request", "no LLM client given and options.fake_llm is false")
        llm = FakeLLM(fake_answers.answer)

    state = RunState(request=request, llm=llm, seed=seed)
    trace: list[TraceLine] = []
    for stage in stages:
        calls_before = len(llm.calls)
        start = time.perf_counter()
        error = None
        try:
            value = stage.func(state)
            if not isinstance(value, stage.output_type):
                error = ChainError(stage.name, f"expected {_type_name(stage.output_type)}, "
                                               f"got {type(value).__name__}")
        except LLMError as exc:
            error = ChainError(stage.name, str(exc), kind="llm", field=exc.field)
        except ValueError as exc:   # pydantic ValidationError is a ValueError
            error = ChainError(stage.name, str(exc), kind="validation",
                               field=getattr(exc, "field", None))
        for call in llm.calls[calls_before:]:
            trace.append(TraceLine(run_id=run_id, stage=stage.name, kind="llm", ok=call.ok,
                                   ms=call.ms, model=call.model, input_tokens=call.input_tokens,
                                   output_tokens=call.output_tokens, retries=call.retries,
                                   error=call.error))
        # One line per code step; an LLM step is traced by its calls, plus a
        # line for an error no call recorded (e.g. the wrong shape).
        llm_failed = any(not c.ok for c in llm.calls[calls_before:])
        if stage.kind == "code" or (error is not None and not llm_failed):
            trace.append(TraceLine(run_id=run_id, stage=stage.name, kind="code",
                                   ok=error is None,
                                   ms=int((time.perf_counter() - start) * 1000),
                                   error=None if error is None else str(error)))
        if error is not None:
            error.trace = trace
            raise error
        state.out[stage.name] = value

    final: CmIdOutput = state.out[stages[-1].name]
    if out_dir is not None:
        out = Path(out_dir)
        for case in final.cases:
            save_case(case, out / case.case_number)
    return RunResult(run_id=run_id, status="ok", cases=final.cases,
                     corrections=final.corrections, trace=trace)
