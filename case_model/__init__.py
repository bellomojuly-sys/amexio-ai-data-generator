"""AMEXIO case model — version 1.1.

The single place where the facts of one dossier live. Import the parts and
the builder from here:

    from case_model import CaseModel, Case, Persona, Event, Money
"""

from .case_model import (
    AbsenceEvent,
    AppraisalEvent,
    Case,
    CaseModel,
    Document,
    DocumentMetadata,
    Dossier,
    ContractChangeEvent,
    Employment,
    Event,
    HireEvent,
    MedicalCheckEvent,
    Organisation,
    Persona,
    TerminationEvent,
    TrainingEvent,
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
    "AbsenceEvent",
    "AppraisalEvent",
    "Case",
    "ContractChangeEvent",
    "HireEvent",
    "MedicalCheckEvent",
    "TerminationEvent",
    "TrainingEvent",
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
