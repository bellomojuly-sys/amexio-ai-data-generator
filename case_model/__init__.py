"""AMEXIO case model — version 1.

The single place where the facts of one dossier live. Import the parts and
the builder from here:

    from case_model import CaseModel, Case, Persona, Event, Money
"""

from .case_model import (
    Case,
    CaseModel,
    Document,
    DocumentMetadata,
    Dossier,
    Employment,
    Event,
    Organisation,
    Persona,
)
from .format_rules import (
    Money,
    is_valid_employee_number,
    is_valid_id,
    next_id,
    reject_caller_id,
    validate_id,
)

__all__ = [
    "Case",
    "CaseModel",
    "Document",
    "DocumentMetadata",
    "Dossier",
    "Employment",
    "Event",
    "Organisation",
    "Persona",
    "Money",
    "is_valid_employee_number",
    "is_valid_id",
    "next_id",
    "reject_caller_id",
    "validate_id",
]
