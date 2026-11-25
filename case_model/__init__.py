"""AMEXIO case model — version 2.2 (lists from a domain configuration).

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
from .domain import DomainConfig, EventBase, get_domain, register_domain
from .domains import HR

# The HR event classes, built from the HR configuration (v2.0); same names as v1.x.
HireEvent = HR.event_classes["hire"]
ContractChangeEvent = HR.event_classes["contract_change"]
TrainingEvent = HR.event_classes["training"]
AppraisalEvent = HR.event_classes["appraisal"]
MedicalCheckEvent = HR.event_classes["medical_check"]
AbsenceEvent = HR.event_classes["absence"]
TerminationEvent = HR.event_classes["termination"]
from .format_rules import (
    Money,
    is_valid_employee_number,
    is_valid_id,
    next_id,
    reject_caller_id,
    validate_id,
)
from .fill import UnresolvedPlaceholders, fact_paths, fill_text, format_fact
from .lookup import UnknownPath, get_fact
from .ingest_any import CaseCorrection, ingest_cases

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
    "get_fact",
    "UnknownPath",
    "DomainConfig",
    "EventBase",
    "get_domain",
    "register_domain",
    "HR",
    "ingest_cases",
    "CaseCorrection",
    "fact_paths",
    "fill_text",
    "format_fact",
    "UnresolvedPlaceholders",
]
