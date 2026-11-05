"""Read one fact from a built Case by a dotted path (AX-022).

The placeholder syntax ``{{ path }}`` (AX-021) and this function are two sides of
one contract: a template holds ``{{ personas.P001.name }}``, and the Fill
placeholder stage reads each path with ``get_fact``. An unknown path raises
``UnknownPath`` with a clear message — never a silent blank (StrictUndefined).

Path grammar::

    dossier.<field>                       dossier.employee_number
    personas.<id>.<field...>              personas.P001.name
    organisations.<id>.<field...>         organisations.ORG-01.name
    events.<id>.<field...>                events.EVT-001.date
    documents.<id>.<field...>             documents.DOC-001.metadata.document_date
    employments.<persona_id>.<field...>   employments.P001.salary.amount

``employments`` is a list, not a dict, so it is addressed by the employee's
persona id (team decision, 5 Nov): the employment whose ``persona_id`` matches.
The rule is one employment per persona; if a persona has more than one, the path
is ambiguous and ``get_fact`` raises rather than guessing the first.

Traversal stops at the first segment that is not a declared field of a case-model
model, so a path can only reach stored facts — never a method or an attribute of
a plain value.
"""

from __future__ import annotations

from pydantic import BaseModel

from .case_model import Case

# The collections of a Case that are keyed by ID.
_BY_ID = {"personas", "organisations", "events", "documents"}


class UnknownPath(ValueError):
    """A placeholder path does not resolve against the case."""


def get_fact(case: Case, path: str):
    """Return the value at ``path`` in ``case``. Raise ``UnknownPath`` if the
    path names a collection, an id or a field that is not there.
    """
    parts = path.split(".") if path else []
    if not parts:
        raise UnknownPath(f"empty path: {path!r}")
    head = parts[0]

    if head == "dossier":
        obj, rest = case.dossier, parts[1:]
    elif head in _BY_ID:
        if len(parts) < 2:
            raise UnknownPath(f"path {path!r}: {head} needs an id, e.g. {head}.<id>.<field>")
        collection = getattr(case, head)
        key = parts[1]
        if key not in collection:
            raise UnknownPath(f"path {path!r}: no {head[:-1]} {key!r}")
        obj, rest = collection[key], parts[2:]
    elif head == "employments":
        if len(parts) < 2:
            raise UnknownPath(
                f"path {path!r}: employments needs a persona id, e.g. employments.<persona_id>.<field>"
            )
        persona_id = parts[1]
        matches = [e for e in case.employments if e.persona_id == persona_id]
        if not matches:
            raise UnknownPath(f"path {path!r}: no employment for persona {persona_id!r}")
        if len(matches) > 1:
            # One employment per persona is the current rule; more than one means
            # the path is ambiguous, so fail loud instead of guessing the first.
            raise UnknownPath(
                f"path {path!r}: {len(matches)} employments for persona {persona_id!r}; "
                f"address by persona id assumes one employment per persona"
            )
        obj, rest = matches[0], parts[2:]
    else:
        raise UnknownPath(f"path {path!r}: unknown collection {head!r}")

    for seg in rest:
        if not isinstance(obj, BaseModel) or seg not in type(obj).model_fields:
            raise UnknownPath(f"path {path!r}: cannot read {seg!r} on {type(obj).__name__}")
        obj = getattr(obj, seg)
    return obj
