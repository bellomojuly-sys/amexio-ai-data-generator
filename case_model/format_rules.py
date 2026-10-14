"""M02 — ID and format rules.

The rules every part of the case model obeys, kept in one place because the
Persona, Organisation, Event, Document and the rest all share them.

- AX-011  Each type has one ID shape; a value in the wrong shape is refused.
          The employee number is six digits (e.g. 100101).
- AX-012  IDs are assigned by the case model, never by a caller or the LLM.
          Input that already carries an ``id`` is refused.
- AX-013  Dates are ISO 8601 (``YYYY-MM-DD``) and nothing else.
- AX-014  An amount is a number plus a currency, never a formatted string.
"""

import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator

# AX-011 — one ID pattern per type: a fixed prefix and a fixed digit count.
ID_PATTERNS = {
    "persona": ("P", 3),          # P001
    "organisation": ("ORG-", 2),  # ORG-01
    "vehicle": ("V", 3),          # V001
    "event": ("EVT-", 3),         # EVT-001
    "document": ("DOC-", 3),      # DOC-001
}

ID_REGEXES = {
    kind: re.compile(rf"^{re.escape(prefix)}\d{{{digits}}}$")
    for kind, (prefix, digits) in ID_PATTERNS.items()
}

# The employee number that titles a dossier: exactly six digits.
EMPLOYEE_NUMBER_REGEX = re.compile(r"^\d{6}$")


def _require_known(kind):
    if kind not in ID_PATTERNS:
        raise ValueError(
            f"Unknown entity type {kind!r}. Known types: {', '.join(ID_PATTERNS)}."
        )


def example_id(kind):
    """The first ID of a type, e.g. ``example_id("organisation") == "ORG-01"``."""
    _require_known(kind)
    prefix, digits = ID_PATTERNS[kind]
    return f"{prefix}{1:0{digits}d}"


def is_valid_id(kind, value):
    """True when ``value`` is a well-formed ID for ``kind`` (AX-011)."""
    _require_known(kind)
    return isinstance(value, str) and bool(ID_REGEXES[kind].match(value))


def validate_id(kind, value):
    """Return ``value`` if it fits the type's pattern, else raise (AX-011)."""
    if not is_valid_id(kind, value):
        prefix, digits = ID_PATTERNS[kind]
        raise ValueError(
            f"Invalid {kind} id {value!r}: expected {prefix} followed by "
            f"{digits} digits, e.g. {example_id(kind)}."
        )
    return value


def is_valid_employee_number(value):
    """True when ``value`` is a six-digit employee number (AX-011)."""
    return isinstance(value, str) and bool(EMPLOYEE_NUMBER_REGEX.match(value))


def next_id(kind, existing_ids):
    """The next free ID for a type, counting up from the IDs already in use.

    The case model owns this: callers never choose an ID (see AX-012).
    """
    _require_known(kind)
    prefix, digits = ID_PATTERNS[kind]
    numbers = [int(i[len(prefix):]) for i in existing_ids]
    number = max(numbers, default=0) + 1
    return f"{prefix}{number:0{digits}d}"


def reject_caller_id(fields):
    """AX-012 — refuse input that already carries an ID.

    IDs come from the case model, not from a caller or the LLM.
    """
    if "id" in fields:
        raise ValueError(
            "IDs are assigned by the case model, not supplied by the caller. "
            f"Remove the id field (got id={fields['id']!r})."
        )


class Money(BaseModel):
    """AX-014 — an amount as a number plus a currency.

    ``Money(amount=3240.00, currency="EUR")`` is valid. A formatted string
    such as ``"€3,240.00"`` is refused: the number and the currency arrive
    apart.
    """

    amount: Decimal
    currency: str

    @field_validator("amount", mode="before")
    @classmethod
    def _amount_is_a_number(cls, v):
        if isinstance(v, str):
            try:
                Decimal(v)
            except InvalidOperation:
                raise ValueError(
                    f"Amount must be a number, not formatted text like {v!r}. "
                    "Pass the number and the currency apart, e.g. "
                    "Money(amount=3240.00, currency='EUR')."
                )
        return v

    @field_validator("currency")
    @classmethod
    def _currency_is_an_iso_code(cls, v):
        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError(
                f"Currency must be a 3-letter ISO 4217 code like 'EUR', got {v!r}."
            )
        return v
