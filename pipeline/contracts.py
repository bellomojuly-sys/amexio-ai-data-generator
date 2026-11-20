"""Stage boundary contracts for the backend pipeline (pipeline contract v1.1).

The backend runs as one Python service; each step is a function with a typed
input and a typed output, validated at the boundary (decision BE-01). This
module names those boundaries (``docs/PIPELINE_CONTRACT.md`` §3–§8). It does
**not** rebuild the case model: where the case model already defines a shape,
the contract reuses it (``EmployeesIn``, ``EmployeeIn``, ``CompanyIn``,
``Case``, ``Correction`` and the closed value sets).

Every input model inherits the case model's input base (``_In``): camelCase
names, an unknown field is refused, and an ``id`` field is refused at every
level (rule 1, AX-012). Generation may only *echo* keys that code gave it: an
employee number, a slot key (``S01``), a document key (``D01``).

| Step | Boundary | Model |
|---|---|---|
| request | ``POST /runs`` | ``RunRequest`` (``RunConfig`` + seed employees) |
| 1 Personas (LLM) → 2 CM ID | | ``PersonasIn`` |
| 2 CM ID → 3 Plot | in process | ``CmIdOutput`` |
| 3 Plot → 4 Event content (LLM) | | ``PlotOutline`` |
| 4 Event content → 5 Dates & participants | | ``EventContentIn`` |
| 5 Dates & participants → ``ingest_storylines`` | | ``StorylinesIn`` (case model) |
| 6 Document plan → 7 Document text (LLM) | | ``DocumentPlan`` / ``CaseDocumentPlan`` |
| 7 Document text → 8 Fill | | ``DocumentTextsIn`` |
| every step | trace | ``TraceLine`` |
| response | ``POST /runs`` | ``RunResult`` / ``ErrorBody`` |
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from case_model import Case
from case_model.format_rules import DocumentType, Rating, TerminationReason
from case_model.ingest import (
    CompanyIn,
    Correction,
    EmployeeIn,
    EmployeesIn,
    _In,
)

EmployeeNumber = Annotated[str, Field(pattern=r"^\d{6}$")]
SlotKey = Annotated[str, Field(pattern=r"^S\d{2}$")]
DocKey = Annotated[str, Field(pattern=r"^D\d{2}$")]
EventId = Annotated[str, Field(pattern=r"^EVT-\d{3}$")]
RunId = Annotated[str, Field(pattern=r"^GEN-\d{4}-\d{4}$")]


def _unique(keys, what):
    seen = set()
    for key in keys:
        if key in seen:
            raise ValueError(f"{what} {key!r} appears twice")
        seen.add(key)


# --- Seed employees (v1.0's Option A input, kept in v1.1 §3) ----------------

class Analysis(EmployeesIn):
    """Seed employees in the ``employees.json`` shape (contract v1.1 §3).

    In v1.0 this was Daniel's analysis. In v1.1 it survives as the shape of
    *seed employees*: employees already known in full (e.g. AMEXIO's reference
    100101) that skip Personas and go straight to CM ID through
    ``map_analysis`` (BE-07). Everything is inherited from ``EmployeesIn``.
    """


# --- 0 · Run request (contract §3) ------------------------------------------

class PositionConfig(_In):
    title: str = Field(min_length=1)
    salary_min: Decimal = Field(gt=0)
    salary_max: Decimal = Field(gt=0)
    is_manager_role: bool = False

    @model_validator(mode="after")
    def _range(self):
        if self.salary_min > self.salary_max:
            raise ValueError(
                f"position {self.title!r}: salaryMin {self.salary_min} is above "
                f"salaryMax {self.salary_max}"
            )
        return self


class DepartmentConfig(_In):
    name: str = Field(min_length=1)
    positions: list[PositionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_titles(self):
        _unique((p.title for p in self.positions), f"department {self.name!r}: position")
        return self


class RunConfig(_In):
    """What Daniel's reviewed analysis hands to the backend (contract §3)."""

    company: CompanyIn
    departments: list[DepartmentConfig] = Field(min_length=1)
    employee_count: int = Field(ge=1, le=1000)
    temporary_share: float = Field(ge=0, le=1)
    part_time_share: float = Field(ge=0, le=1)
    as_of_date: dt.date
    notes: str | None = None

    @model_validator(mode="after")
    def _unique_departments(self):
        _unique((d.name for d in self.departments), "department")
        return self

    def position(self, department: str, title: str) -> PositionConfig | None:
        """The position ``title`` of ``department``, or None if the config has none."""
        for dep in self.departments:
            if dep.name == department:
                return next((p for p in dep.positions if p.title == title), None)
        return None


class RunOptions(_In):
    fake_llm: bool = Field(False, alias="fake_llm")


class RunRequest(_In):
    """The body of ``POST /runs`` (contract §3)."""

    config: RunConfig
    seed_employees: list[EmployeeIn] | None = None
    options: RunOptions = RunOptions()

    @model_validator(mode="after")
    def _seeds_fit(self):
        seeds = len(self.seed_employees or [])
        if seeds > self.config.employee_count:
            raise ValueError(
                f"seedEmployees has {seeds} employees, more than "
                f"employeeCount {self.config.employee_count}"
            )
        return self


# --- 1 · Personas → 2 · CM ID (contract §4) ---------------------------------

class PersonaIn(_In):
    """What the LLM writes per employee. Fix 1 (v1.1): no contract type, hours,
    manager flag, hire date or salary: those are facts, and CM ID decides them."""

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    department: str = Field(min_length=1)
    position: str = Field(min_length=1)


class PersonasIn(_In):
    employees: list[PersonaIn] = Field(min_length=1)


# --- 2 · CM ID → 3 · Plot (in process) --------------------------------------

class CmIdOutput(BaseModel):
    """The cases built by the case model (IDs assigned by code) plus the values
    the case model corrected on the way in. Also the shape after Dates &
    participants and after Fill: always the case model's own ``Case``."""

    cases: list[Case]
    corrections: list[Correction] = []


# --- 3 · Plot (contract §5) -------------------------------------------------

ChangeKind = Literal["salary_review", "promotion", "made_permanent", "hours_change"]


class _Slot(_In):
    slot: SlotKey


class TrainingSlot(_Slot):
    type: Literal["training"]
    duration_days: int = Field(ge=1, le=5)   # fix 2: Plot picks it, 1–5 in the HR template


class AppraisalSlot(_Slot):
    type: Literal["appraisal"]
    year: int = Field(ge=1990, le=2100)
    rating: Rating


class ContractChangeSlot(_Slot):
    type: Literal["contract_change"]
    change: ChangeKind
    new_position: str | None = None

    @model_validator(mode="after")
    def _position_only_on_promotion(self):
        if self.change == "promotion" and not self.new_position:
            raise ValueError(f"slot {self.slot}: a promotion needs newPosition")
        if self.change != "promotion" and self.new_position:
            raise ValueError(f"slot {self.slot}: newPosition only on a promotion")
        return self


class TerminationSlot(_Slot):
    type: Literal["termination"]
    reason: TerminationReason


class AbsenceSlot(_Slot):
    type: Literal["absence"]


class MedicalCheckSlot(_Slot):
    type: Literal["medical_check"]


# ``hire`` is not a slot: CM ID adds it. Any other type fails as unknown.
Slot = Annotated[
    Union[TrainingSlot, AppraisalSlot, ContractChangeSlot, TerminationSlot,
          AbsenceSlot, MedicalCheckSlot],
    Field(discriminator="type"),
]


class CaseOutline(_In):
    employee_number: EmployeeNumber
    slots: list[Slot] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _coherent(self):
        _unique((s.slot for s in self.slots), f"employee {self.employee_number}: slot")
        ends = [i for i, s in enumerate(self.slots) if s.type == "termination"]
        if len(ends) > 1:
            raise ValueError(f"employee {self.employee_number}: more than one termination")
        if ends and ends[0] != len(self.slots) - 1:
            raise ValueError(
                f"employee {self.employee_number}: nothing may come after the termination"
            )
        return self


class PlotOutline(_In):
    outlines: list[CaseOutline] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_per_employee(self):
        _unique((o.employee_number for o in self.outlines), "employeeNumber")
        return self


# --- 4 · Event content (LLM, Robin; contract §5) -----------------------------

class SlotContent(_In):
    """Per slot, the text the LLM writes. Which text a type needs is checked
    against the outline by ``check_event_content`` (the shape alone cannot
    know a slot's type)."""

    slot: SlotKey
    summary: str = Field(min_length=1)
    course: str | None = None      # training
    comment: str | None = None     # appraisal
    reason: str | None = None      # contract_change


class CaseContent(_In):
    employee_number: EmployeeNumber
    slots: list[SlotContent]


class EventContentIn(_In):
    content: list[CaseContent] = Field(min_length=1)


# Which text field each slot type needs from the LLM (contract §5 table).
TEXT_NEEDED = {"training": "course", "appraisal": "comment", "contract_change": "reason"}


def check_event_content(outline: PlotOutline, content: EventContentIn) -> None:
    """Every slot answered exactly once, no unknown slot, the text each type
    needs present and no text a type does not take. Raises ``ValueError``
    naming the employee, the slot and the field."""
    asked = {o.employee_number: {s.slot: s.type for s in o.slots} for o in outline.outlines}
    answered = {c.employee_number: c for c in content.content}
    for number in answered:
        if number not in asked:
            raise ValueError(f"content for employee {number}, which has no outline")
    for number, slots in asked.items():
        case = answered.get(number)
        if case is None:
            raise ValueError(f"employee {number}: no content")
        keys = [s.slot for s in case.slots]
        _unique(keys, f"employee {number}: slot")
        for key in keys:
            if key not in slots:
                raise ValueError(f"employee {number}: unknown slot {key}")
        for key in slots:
            if key not in keys:
                raise ValueError(f"employee {number}: slot {key} not answered")
        for answer in case.slots:
            need = TEXT_NEEDED.get(slots[answer.slot])
            for field in ("course", "comment", "reason"):
                value = getattr(answer, field)
                if field == need and not value:
                    raise ValueError(f"employee {number}, slot {answer.slot}: {field} is missing")
                if field != need and value is not None:
                    raise ValueError(
                        f"employee {number}, slot {answer.slot}: {field} is not written "
                        f"for a {slots[answer.slot]} slot"
                    )


# --- 6 · Document plan → 7 · Document text (contract §7) --------------------

# Documents that get LLM text (contract §7); the others stay templated.
LLM_TEXT_DOCUMENTS: dict[str, tuple[str, list[str]]] = {
    # event type: (document type, sections)
    "appraisal": ("performance_appraisal", ["feedback", "summary"]),
    "termination": ("termination_letter", ["letter_body"]),
    "contract_change": ("contract_amendment", ["cover_letter"]),
}


class PlannedDocument(_In):
    doc: DocKey
    type: DocumentType
    event_id: EventId
    sections: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _llm_text_type(self):
        allowed = {t for t, _ in LLM_TEXT_DOCUMENTS.values()}
        if self.type not in allowed:
            raise ValueError(
                f"{self.doc}: {self.type} is templated; only {sorted(allowed)} get LLM text"
            )
        _unique(self.sections, f"{self.doc}: section")
        return self


class CaseDocumentPlan(_In):
    """The plan for one case: what ``write_document_text`` receives."""

    employee_number: EmployeeNumber
    documents: list[PlannedDocument] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_docs(self):
        _unique((d.doc for d in self.documents), f"employee {self.employee_number}: doc")
        return self


class DocumentPlan(_In):
    """The plan for the whole run."""

    plans: list[CaseDocumentPlan]

    @model_validator(mode="after")
    def _one_per_employee(self):
        _unique((p.employee_number for p in self.plans), "employeeNumber")
        return self


class DocumentTextIn(_In):
    doc: DocKey
    sections: dict[str, str]


class DocumentTextsIn(_In):
    """What the LLM writes for one case (Part 3)."""

    employee_number: EmployeeNumber
    documents: list[DocumentTextIn]


def check_document_texts(plan: CaseDocumentPlan, texts: DocumentTextsIn) -> None:
    """Every planned document answered once with exactly its planned sections."""
    if texts.employee_number != plan.employee_number:
        raise ValueError(
            f"texts for employee {texts.employee_number}, plan for {plan.employee_number}"
        )
    planned = {d.doc: d.sections for d in plan.documents}
    keys = [d.doc for d in texts.documents]
    _unique(keys, f"employee {plan.employee_number}: doc")
    for key in keys:
        if key not in planned:
            raise ValueError(f"employee {plan.employee_number}: unknown doc {key}")
    for key in planned:
        if key not in keys:
            raise ValueError(f"employee {plan.employee_number}: doc {key} not written")
    for doc in texts.documents:
        if set(doc.sections) != set(planned[doc.doc]):
            raise ValueError(
                f"employee {plan.employee_number}, {doc.doc}: sections "
                f"{sorted(doc.sections)} differ from the plan {planned[doc.doc]}"
            )


class DocumentTexts(BaseModel):
    """Step 7's output for the whole run: one ``DocumentTextsIn`` per case that
    has planned documents (in process, not an owner boundary)."""

    texts: list[DocumentTextsIn] = []


# --- Trace (contract §8) and response (contract §3) -------------------------

class TraceLine(BaseModel):
    """One line per LLM call and per code step. Snake_case, as in the contract."""

    model_config = ConfigDict(extra="forbid")

    run_id: RunId
    stage: str
    kind: Literal["llm", "code"]
    ok: bool
    ms: int = Field(ge=0)
    model: str | None = None
    input_tokens: int | None = Field(None, ge=0)
    output_tokens: int | None = Field(None, ge=0)
    retries: int | None = Field(None, ge=0)
    cost_eur: float | None = Field(None, ge=0)
    error: str | None = None

    @model_validator(mode="after")
    def _code_has_no_tokens(self):
        if self.kind == "code" and any(
            v is not None for v in (self.model, self.input_tokens, self.output_tokens,
                                    self.retries, self.cost_eur)
        ):
            raise ValueError("a code step has no model, token, retry or cost fields")
        return self


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["validation", "llm", "chain"]
    stage: str | None = None
    message: str
    field: str | None = None


class ErrorBody(BaseModel):
    """The one error shape: ``{"error": {"kind", "stage", "message", "field"}}``."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class RunResult(BaseModel):
    """The response of ``POST /runs``."""

    model_config = ConfigDict(extra="forbid")

    run_id: RunId
    status: Literal["ok"]
    cases: list[Case]
    corrections: list[Correction] = []
    trace: list[TraceLine] = []
