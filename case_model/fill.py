"""Fill a text from the case: every placeholder resolves, or the run stops (M04).

The pipeline's Fill step (step 8, Valentin) writes each document text by
replacing the ``{{ path }}`` placeholders (AX-021) with facts read through
``get_fact`` (AX-022). This module gives that step three guarantees:

- AX-023 ``fact_paths(case)`` lists every path that resolves to one printable
  fact, so the Document text prompt can offer exactly these placeholders and a
  test can prove that all of them resolve;
- AX-024 ``fill_text(case, text)`` refuses a text with any placeholder that
  does not resolve, resolves to no value, points at an internal ID, or is
  malformed, and names all of them at once: never a silent blank;
- AX-025 ``format_fact(value, fmt)`` formats a fact only when it is printed,
  in the formats of AMEXIO's PDFs (the same as the generator's
  ``src/spec/format.ts``). The case keeps ISO dates and numeric amounts.

The syntax stays ``{{ path }}``. Without an explicit format, the format follows
the value: a date prints as DD-MM-YYYY, an amount as "EUR 4.350".
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

from .case_model import Case
from .format_rules import Money
from .lookup import UnknownPath, get_fact

# The pipeline's placeholder pattern (contract §7): spaces inside the braces are ignored.
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

# Robin's FieldFormat (src/spec/types.ts), the closed list of print formats.
FieldFormat = Literal["text", "date", "dateRange", "monthYear", "eurGrouped",
                      "eurPlain", "days", "number"]
FORMATS = ("text", "date", "dateRange", "monthYear", "eurGrouped", "eurPlain", "days", "number")

# Fields that hold an internal reference (P001, ORG-01, EVT-001): never printed.
# The employee number (dossier.employee_number, metadata.employee_id) is a real,
# printed fact and stays.
INTERNAL_IDS = {"id", "persona_id", "organisation_id", "provider_id", "event_id", "signed_by"}

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


class UnresolvedPlaceholders(ValueError):
    """A text cannot be filled; ``problems`` maps each placeholder to its reason."""

    def __init__(self, problems: dict[str, str]):
        self.problems = problems
        listed = "; ".join(f"{{{{ {p} }}}}: {why}" for p, why in problems.items())
        super().__init__(f"{len(problems)} placeholder(s) cannot be filled: {listed}")


def _whole_euros(amount) -> int:
    return int(Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_fact(value, fmt: str | None = None) -> str:
    """One stored fact as the PDF prints it (AX-025). ``fmt`` is one of
    ``FORMATS``; without it, the format follows the value's type."""
    if fmt is not None and fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; use one of {', '.join(FORMATS)}")
    if isinstance(value, Money):
        value = value.amount
        fmt = fmt or "eurGrouped"
    if isinstance(value, dt.date):
        fmt = fmt or "date"
        if fmt == "date":
            return value.strftime("%d-%m-%Y")                    # 14-04-2026
        if fmt == "monthYear":
            return f"{MONTHS[value.month - 1]} {value.year}"     # September 2026
    if fmt == "eurGrouped":
        euros = _whole_euros(value)
        return f"EUR {'-' if euros < 0 else ''}{abs(euros):,}".replace(",", ".")  # EUR 4.350
    if fmt == "eurPlain":
        return f"EUR {_whole_euros(value)}"                      # EUR 4350
    if fmt == "days":
        n = int(value)
        return f"{n} {'day' if n == 1 else 'days'}"              # 2 days
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))                                   # 40.0 -> 40
    return str(value)


def _is_reference(info) -> bool:
    """A field of a domain's event that holds a persona or organisation ID (v2.0)."""
    extra = info.json_schema_extra
    return isinstance(extra, dict) and "reference" in extra


def _points_at_an_id(case, path) -> bool:
    if path.rsplit(".", 1)[-1] in INTERNAL_IDS:
        return True
    parent, _, name = path.rpartition(".")
    try:
        owner = get_fact(case, parent) if parent.count(".") >= 1 else None
    except UnknownPath:
        return False
    info = type(owner).model_fields.get(name) if isinstance(owner, BaseModel) else None
    return info is not None and _is_reference(info)


def _leaves(obj, prefix):
    """Every dotted path under ``obj`` that ends in one printable value."""
    if isinstance(obj, Money):
        yield prefix, obj
        return
    if isinstance(obj, BaseModel):
        for name, info in type(obj).model_fields.items():
            if name not in INTERNAL_IDS and not _is_reference(info):
                yield from _leaves(getattr(obj, name), f"{prefix}.{name}")
        return
    if obj is None or isinstance(obj, (list, dict)):
        return          # no value, or several: not one fact a text can print
    yield prefix, obj


def fact_paths(case: Case) -> list[str]:
    """AX-023 — every placeholder path that resolves to one printable fact."""
    paths = [p for p, _ in _leaves(case.dossier, "dossier")]
    for name in ("personas", "organisations", "events", "documents"):
        for key, part in getattr(case, name).items():
            paths += [p for p, _ in _leaves(part, f"{name}.{key}")]
    for job in case.employments:
        paths += [p for p, _ in _leaves(job, f"employments.{job.persona_id}")]
    return paths


def fill_text(case: Case, text: str, formats: dict[str, str] | None = None) -> str:
    """AX-024 — the text with every ``{{ path }}`` replaced by its fact.

    ``formats`` may give a print format per path (from the template's field).
    Raises ``UnresolvedPlaceholders`` naming every placeholder that does not
    resolve, resolves to no value or to several, or is malformed; the case is
    never changed.
    """
    formats = formats or {}
    problems: dict[str, str] = {}
    values: dict[str, str] = {}
    for path in dict.fromkeys(PLACEHOLDER.findall(text)):
        if _points_at_an_id(case, path):
            problems[path] = ("an internal ID, not a printable fact (use the name, "
                              "e.g. personas.<id>.name)")
            continue
        try:
            value = get_fact(case, path)
        except UnknownPath as error:
            problems[path] = str(error)
            continue
        if value is None:
            problems[path] = "the case holds no value for it"
        elif isinstance(value, (list, dict)):
            problems[path] = "it names several values, not one fact"
        else:
            values[path] = format_fact(value, formats.get(path))

    filled = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)
    if not problems:
        leftover = re.findall(r"\{\{|\}\}", filled)
        if leftover:
            problems["(malformed)"] = (
                f"{len(leftover)} unmatched brace pair(s) left in the text, e.g. "
                f"{{{{ }}}} or a missing closing brace"
            )
    if problems:
        raise UnresolvedPlaceholders(problems)
    return filled
