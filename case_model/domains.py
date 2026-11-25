"""The domains the case model knows. HR (AMEXIO's mock data) is the first one.

HR is written here as data: the same lists the case model held in code until
v1.2 (``format_rules``), so every HR case validates exactly as before.
"""

from typing import get_args

from .domain import DomainConfig, register_domain
from .format_rules import (
    ContractType,
    DocumentType,
    MedicalResult,
    PersonaRole,
    RECURRING_DOCUMENT_TYPES,
    Rating,
    TerminationReason,
)


def _values(literal):
    return list(get_args(literal))


HR = register_domain(DomainConfig.model_validate({
    "name": "hr",
    "version": "1.3",
    "description": "HR dossiers (AMEXIO's mock data): an employee's employment history.",
    "case_number_pattern": "[0-9]{6}",
    "uses_employment": True,
    "roles": _values(PersonaRole),
    "event_types": {
        "hire": {"description": "The start of the employment. The agreed terms live in Employment."},
        "contract_change": {"fields": {
            "reason": {"format": "text", "required": True},
            "new_salary": {"format": "money", "gt": 0},
            "new_position": {"format": "text"},
            "new_contract_type": {"format": "text", "values": _values(ContractType)},
            "new_hours": {"format": "number", "gt": 0},
        }},
        "training": {"fields": {
            "course": {"format": "text", "required": True},
            "duration_days": {"format": "integer", "required": True, "gt": 0},
            "provider_id": {"format": "organisation", "required": True, "label": "training provider"},
        }},
        "appraisal": {"fields": {
            "year": {"format": "integer", "required": True},
            "rating": {"format": "text", "required": True, "values": _values(Rating)},
            "comment": {"format": "text"},
        }},
        "medical_check": {"fields": {
            "result": {"format": "text", "required": True, "values": _values(MedicalResult)},
        }},
        "absence": {"description": "A sick-leave period: dates only, never a cause or diagnosis.",
                    "fields": {"end_date": {"format": "date", "ends_period": True}}},
        "termination": {"description": "The last working day.", "fields": {
            "reason": {"format": "text", "required": True, "values": _values(TerminationReason)},
            "notice_date": {"format": "date", "not_after_event": True},
        }},
    },
    "document_types": {
        name: {"recurring": name in RECURRING_DOCUMENT_TYPES} for name in _values(DocumentType)
    },
    "rules": {"first_event": "hire", "first_event_starts_employment": True,
              "last_event": "termination", "last_event_label": "last working day"},
}))
