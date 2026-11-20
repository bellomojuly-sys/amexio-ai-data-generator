"""Steps 5 and 8 · Dates & participants, Fill — **stubs** (owner: Valentin).

They have the shapes of contract v1.1 so the chain runs end to end; Valentin's
real steps replace the bodies.

- ``dates_and_participants_stub`` dates every slot by a simple rule and hands a
  ``storylines.json`` to the case model's ``ingest_storylines``, which assigns
  the event IDs and the participants (employee, manager, examiner, provider).
- ``fill_stub`` checks that every placeholder in the texts resolves with
  ``get_fact`` (an unknown path stops the run — no silent blank) and returns the
  cases unchanged: the case model has no document records for these texts yet
  (open point, see ``docs/PIPELINE_CONTRACT.md`` §10).
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from decimal import Decimal

from case_model.ingest import ingest_storylines
from case_model.lookup import get_fact

from .contracts import CmIdOutput, DocumentTexts, EventContentIn, PlotOutline, RunConfig

PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
RAISE = {"salary_review": Decimal("1.03"), "promotion": Decimal("1.08")}


def _month_end(day: dt.date) -> dt.date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def dates_and_participants_stub(cm: CmIdOutput, outline: PlotOutline,
                                content: EventContentIn, config: RunConfig) -> CmIdOutput:
    by_number = {c.case_number: c for c in cm.cases}
    texts = {(c.employee_number, s.slot): s for c in content.content for s in c.slots}
    storylines = []
    for o in outline.outlines:
        case = by_number[o.employee_number]
        job = case.employments[0]
        hire, as_of = job.start_date, config.as_of_date
        salary = job.salary.amount
        dated = [s for s in o.slots if s.type != "appraisal"]
        step = (as_of - hire).days // (len(dated) + 1)
        when = {s.slot: hire + dt.timedelta(days=step * (k + 1)) for k, s in enumerate(dated)}
        events, appraisals = [], []
        for s in o.slots:
            text = texts[(o.employee_number, s.slot)]
            if s.type == "appraisal":
                appraisals.append({"year": s.year, "rating": s.rating, "comment": text.comment})
            elif s.type == "training":
                events.append({"type": "training", "date": when[s.slot].isoformat(),
                               "course": text.course, "durationDays": s.duration_days})
            elif s.type == "contract_change":
                change = {"type": "contract_change", "date": when[s.slot].isoformat(),
                          "reason": text.reason}
                if s.change in RAISE:
                    salary = (salary * RAISE[s.change]).quantize(Decimal("1"))
                    change["newSalary"] = str(salary)
                if s.change == "promotion":
                    change["newPosition"] = s.new_position
                if s.change == "made_permanent":
                    change["newContractType"] = "Permanent"
                events.append(change)
            elif s.type == "medical_check":
                events.append({"type": "medical_check", "date": when[s.slot].isoformat(),
                               "result": "Fit for work"})
            elif s.type == "absence":
                start = when[s.slot]
                events.append({"type": "absence", "startDate": start.isoformat(),
                               "endDate": (start + dt.timedelta(days=5)).isoformat()})
            elif s.type == "termination":
                events.append({"type": "termination",
                               "date": _month_end(when[s.slot]).isoformat(),
                               "reason": s.reason})
        storylines.append({"employeeId": o.employee_number, "events": events,
                           "appraisals": appraisals})
    cases, corrections = ingest_storylines(cm.cases, {"storylines": storylines})
    return CmIdOutput(cases=cases, corrections=[*cm.corrections, *corrections])


def fill_stub(cm: CmIdOutput, texts: DocumentTexts) -> CmIdOutput:
    by_number = {c.case_number: c for c in cm.cases}
    for case_texts in texts.texts:
        case = by_number[case_texts.employee_number]
        for doc in case_texts.documents:
            for section, text in doc.sections.items():
                for path in PLACEHOLDER.findall(text):
                    get_fact(case, path)   # raises UnknownPath on a bad placeholder
    return cm
