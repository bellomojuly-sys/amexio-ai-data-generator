"""Ingest — the generator's JSON goes in, cases come out (v1.1, decision D4).

The dossier generator (branch Demo-Generator) asks the LLM for two JSON
objects, in the shapes its prompts fix (``src/ai/prompts.ts``):

1. ``{"company": {...}, "employees": [...]}``  — who works here, without IDs
2. ``{"storylines": [{"employeeId": ..., "events": [...], "appraisals": [...]}]}``

This module is the gate those objects pass through. It

- refuses any ``id`` in the input (AX-012): IDs are assigned here;
- creates one case per employee, numbering them from ``first_number`` in the
  order of the list (the first employee gets 100101, the next 100102, ...);
- normalizes values that are only written differently from the closed lists
  ("permanent" -> "Permanent") and records each change as a correction;
- refuses values it cannot place, rather than inventing one;
- accepts a reference to something that already exists (a storyline's
  ``employeeId``) and checks that it exists.

The input field names stay exactly as the generator writes them (camelCase,
decision D6); the cases use the case model's own names. Run it on files with::

    python -m case_model.ingest employees.json storylines.json --out DIR
"""

import argparse
import json
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.alias_generators import to_camel

from .case_model import Case, CaseModel
from .format_rules import (
    ContractType,
    MedicalResult,
    Money,
    Rating,
    TerminationReason,
    is_valid_employee_number,
)
from .storage import load_case, save_case

CURRENCY = "EUR"


def _eur(amount):
    """Whole euros from the generator become Money with cents: 4350 -> 4350.00."""
    return Money(amount=Decimal(amount).quantize(Decimal("0.01")), currency=CURRENCY)


class _In(BaseModel):
    """Input models mirror the generator's JSON: camelCase names, nothing
    extra. An ``id`` (or any field the shape does not name) is refused."""

    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _no_id(cls, data):
        if isinstance(data, dict) and "id" in data:
            raise ValueError(
                "IDs are assigned by the case model, not by the generator or the "
                f"LLM. Remove the id field (got id={data['id']!r})."
            )
        return data


# 1 — the employees JSON

class CompanyIn(_In):
    employer_name: str
    training_provider: str | None = None
    examiner: str | None = None
    absence_service: str | None = None
    director_name: str | None = None


class EmployeeIn(_In):
    first_name: str
    last_name: str
    department: str
    position: str
    is_manager: bool = False
    hire_date: dt.date
    contract_type: str
    hours_per_week: float = Field(gt=0)
    start_salary: Decimal = Field(gt=0)
    # Only when the manager is not one of the employees (as in AMEXIO's example).
    manager_name: str | None = None


class EmployeesIn(_In):
    company: CompanyIn
    employees: list[EmployeeIn] = Field(min_length=1)


# 2 — the storylines JSON (the event shapes of the generator's prompt)

class ContractChangeIn(_In):
    type: Literal["contract_change"]
    date: dt.date
    reason: str
    new_salary: Decimal | None = None
    new_position: str | None = None
    new_contract_type: str | None = None
    new_hours: float | None = None


class TrainingIn(_In):
    type: Literal["training"]
    date: dt.date
    course: str
    duration_days: int = Field(gt=0)


class AbsenceIn(_In):
    type: Literal["absence"]
    start_date: dt.date
    end_date: dt.date | None = None


class TerminationIn(_In):
    type: Literal["termination"]
    date: dt.date
    reason: str
    notice_date: dt.date | None = None


class MedicalCheckIn(_In):
    """Added by the generator's rules (every two years), not by the LLM."""

    type: Literal["medical_check"]
    date: dt.date
    result: str


class AppraisalIn(_In):
    """In the prompt's ``appraisals`` list (no ``type``), or among the events
    (``"type": "appraisal"``) once the generator has planned them."""

    type: Literal["appraisal"] = "appraisal"
    year: int
    rating: str
    comment: str | None = None
    # Without a date, an appraisal is dated 30 June of its year, as the generator does.
    date: dt.date | None = None


EventIn = Annotated[
    Union[ContractChangeIn, TrainingIn, AbsenceIn, TerminationIn, MedicalCheckIn, AppraisalIn],
    Field(discriminator="type"),
]


class StorylineIn(_In):
    employee_id: str
    events: list[EventIn] = Field(default_factory=list)
    appraisals: list[AppraisalIn] = Field(default_factory=list)


class StorylinesIn(_In):
    storylines: list[StorylineIn]


class Correction(BaseModel):
    """A value the case model changed on the way in, shown to the user."""

    step: Literal["employees", "storylines"]
    employee_id: str
    message: str


def _closed(value, allowed, field, step, employee_id, corrections):
    """Place ``value`` in a closed list. A value written differently (case,
    spaces) is corrected and recorded; anything else is refused."""
    options = get_args(allowed)
    if value in options:
        return value
    wanted = " ".join(str(value).split()).casefold()
    for option in options:
        if option.casefold() == wanted:
            corrections.append(Correction(
                step=step, employee_id=employee_id,
                message=f"{field}: {value!r} written as {option!r}.",
            ))
            return option
    raise ValueError(
        f"Employee {employee_id}: {field} {value!r} is not one of {', '.join(options)}."
    )


def _clean(text, field, step, employee_id, corrections):
    """Collapse repeated and surrounding spaces in a name."""
    cleaned = " ".join(text.split())
    if cleaned != text:
        corrections.append(Correction(
            step=step, employee_id=employee_id,
            message=f"{field}: extra spaces removed ({text!r} -> {cleaned!r}).",
        ))
    return cleaned


def ingest_employees(data, first_number=100101):
    """Create one case per employee in the employees JSON.

    Returns ``(cases, corrections)``. Each case holds the employee, their
    manager, the employer, the employment as agreed at hire and the hire
    event; the training provider and the examiner are added when the company
    names them, so the storyline can point at them.
    """
    batch = EmployeesIn.model_validate(data)
    company = batch.company
    last = first_number + len(batch.employees) - 1
    if not (is_valid_employee_number(f"{first_number:06d}") and last <= 999999):
        raise ValueError(f"Employee numbers {first_number}..{last} are not all six digits.")

    corrections = []
    full_names = []
    for i, emp in enumerate(batch.employees):
        number = f"{first_number + i:06d}"
        first = _clean(emp.first_name, "firstName", "employees", number, corrections)
        last_name = _clean(emp.last_name, "lastName", "employees", number, corrections)
        full_names.append(f"{first} {last_name}")

    # A department's manager is the employee marked isManager there.
    heads = {}
    for i, emp in enumerate(batch.employees):
        if emp.is_manager:
            heads.setdefault(emp.department, full_names[i])

    cases = []
    for i, emp in enumerate(batch.employees):
        number = f"{first_number + i:06d}"
        name = full_names[i]

        case = CaseModel(number)
        case.set_dossier(employee_number=number, folder_title=f"{number} {name}")
        employer = case.add_organisation(name=company.employer_name, kind="employer")
        employee = case.add_persona(name=name, role="employee", organisation_id=employer)

        manager_name = emp.manager_name or (
            heads.get(emp.department) if not emp.is_manager else company.director_name
        )
        if manager_name and manager_name != name:
            case.add_persona(name=manager_name, role="manager", organisation_id=employer)

        if company.training_provider:
            case.add_organisation(name=company.training_provider, kind="training_provider")
        if company.examiner:
            service = None
            if company.absence_service:
                service = case.add_organisation(
                    name=company.absence_service, kind="occupational_health",
                )
            case.add_persona(name=company.examiner, role="examiner", organisation_id=service)

        case.add_employment(
            persona_id=employee,
            organisation_id=employer,
            position=emp.position,
            department=emp.department,
            start_date=emp.hire_date,
            contract_type=_closed(emp.contract_type, ContractType, "contractType",
                                  "employees", number, corrections),
            hours=emp.hours_per_week,
            salary=_eur(emp.start_salary),
        )
        case.add_event(type="hire", date=emp.hire_date, participant_ids=[employee])
        cases.append(case.build())
    return cases, corrections


def _find(case, role=None, kind=None):
    """The ID of the first persona with ``role`` or organisation of ``kind``."""
    if role:
        return next((p.id for p in case.personas.values() if p.role == role), None)
    return next((o.id for o in case.organisations.values() if o.kind == kind), None)


def ingest_storylines(cases, data):
    """Add each storyline's events to the case of its employee.

    Returns ``(cases, corrections)`` with the cases in the order given. A
    storyline for an employee number that has no case is refused, and so is a
    second storyline for the same employee.
    """
    batch = StorylinesIn.model_validate(data)
    by_number = {case.case_number: case for case in cases}
    corrections = []
    seen = set()

    for story in batch.storylines:
        number = story.employee_id
        if number not in by_number:
            raise ValueError(f"Storyline for unknown employee {number!r}.")
        if number in seen:
            raise ValueError(f"Two storylines for employee {number}.")
        seen.add(number)

        case = CaseModel.from_case(by_number[number])
        employee = _find(case, role="employee")
        manager = _find(case, role="manager")
        examiner = _find(case, role="examiner")
        provider = _find(case, kind="training_provider")

        events = [*story.events, *story.appraisals]
        events.sort(key=lambda e: e.start_date if e.type == "absence"
                    else e.date or dt.date(e.year, 6, 30))
        for e in events:
            fields = {"type": e.type, "participant_ids": [employee]}
            if e.type == "contract_change":
                fields.update(
                    date=e.date, reason=e.reason, new_position=e.new_position,
                    new_hours=e.new_hours,
                    new_salary=_eur(e.new_salary)
                    if e.new_salary is not None else None,
                    new_contract_type=_closed(e.new_contract_type, ContractType,
                                              "newContractType", "storylines", number,
                                              corrections)
                    if e.new_contract_type is not None else None,
                )
            elif e.type == "training":
                if provider is None:
                    raise ValueError(
                        f"Employee {number}: a training needs a provider; name it in "
                        "company.trainingProvider of the employees JSON."
                    )
                fields.update(date=e.date, course=e.course, duration_days=e.duration_days,
                              provider_id=provider)
            elif e.type == "absence":
                fields.update(date=e.start_date, end_date=e.end_date)
            elif e.type == "termination":
                fields.update(date=e.date, notice_date=e.notice_date,
                              reason=_closed(e.reason, TerminationReason, "reason",
                                             "storylines", number, corrections))
            elif e.type == "medical_check":
                if examiner:
                    fields["participant_ids"] = [employee, examiner]
                fields.update(date=e.date, result=_closed(e.result, MedicalResult, "result",
                                                          "storylines", number, corrections))
            elif e.type == "appraisal":
                if manager:
                    fields["participant_ids"] = [employee, manager]
                fields.update(date=e.date or dt.date(e.year, 6, 30), year=e.year,
                              comment=e.comment,
                              rating=_closed(e.rating, Rating, "rating", "storylines",
                                             number, corrections))
            case.add_event(**fields)
        by_number[number] = case.build()

    return [by_number[case.case_number] for case in cases], corrections


def ingest_files(employees_path, storylines_path=None, out_dir=None, first_number=100101):
    """Ingest the generator's JSON files and, with ``out_dir``, write one case
    folder per employee (``out_dir/100101/case.json`` ...) plus
    ``out_dir/corrections.json``. Returns ``(cases, corrections)``."""
    read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    cases, corrections = ingest_employees(read(employees_path), first_number)
    if storylines_path:
        cases, more = ingest_storylines(cases, read(storylines_path))
        corrections += more
    if out_dir:
        out = Path(out_dir)
        for case in cases:
            save_case(case, out / case.case_number)
        (out / "corrections.json").write_text(
            json.dumps([c.model_dump() for c in corrections], indent=2,
                       ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return cases, corrections


def load_cases(directory):
    """Read back every case folder that ``ingest_files`` wrote."""
    return [load_case(d) for d in sorted(Path(directory).iterdir())
            if (d / "case.json").is_file()]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m case_model.ingest",
        description="Turn the generator's employees and storylines JSON into case folders.",
    )
    parser.add_argument("employees", help="employees JSON: {company, employees}")
    parser.add_argument("storylines", nargs="?", help="storylines JSON: {storylines}")
    parser.add_argument("--out", required=True, help="folder for the case folders")
    parser.add_argument("--first-number", type=int, default=100101,
                        help="employee number of the first employee (default 100101)")
    args = parser.parse_args(argv)
    try:
        cases, corrections = ingest_files(args.employees, args.storylines, args.out,
                                          args.first_number)
    except (ValidationError, ValueError) as error:
        parser.exit(1, f"refused: {error}\n")
    print(f"wrote {len(cases)} cases to {args.out} ({len(corrections)} corrections)")


if __name__ == "__main__":
    main()
