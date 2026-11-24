"""Domain configuration: the lists a case is checked against (case model v2.0, GD-01).

Until v1.2 the case model held HR's lists in code: seven event types with their
own fields, nine document types, four roles, the rules between events. Since
v2.0 those lists are **data**, one ``DomainConfig`` per domain. The case model
keeps what every domain shares (IDs made by code, references that must exist,
ISO dates, amounts as Money, documents tied to events) and reads the rest from
the configuration of the case's domain.

From a configuration the code builds one event class per event type (for HR:
``HireEvent``, ``AppraisalEvent`` with its ``rating`` …), so an event of any
domain has typed fields, is validated by pydantic and is read like before.

HR is the first configuration (``case_model.domains.HR``). A new domain is a
new ``DomainConfig``: Daniel's data configuration is turned into one, checked
here, and registered with ``register_domain``.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cached_property
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model, model_validator

from .format_rules import Money

# The formats a field of an event can have. A reference (persona, organisation)
# holds an ID of the case and is checked to exist.
FieldFormat = Literal["text", "date", "money", "integer", "number", "persona", "organisation"]
REFERENCE_FORMATS = ("persona", "organisation")

# Every event has these; an event type cannot redefine them.
BASE_EVENT_FIELDS = ("id", "type", "date", "participant_ids", "label", "summary", "signed_by")

_NAME = re.compile(r"[a-z][a-z0-9_]*")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldSpec(_Strict):
    """One field of an event type."""

    format: FieldFormat
    required: bool = False
    # A closed list: the field accepts only these values (text only).
    values: list[str] | None = None
    # Lower bound, exclusive (integer and number only): ``duration_days`` > 0.
    gt: float | None = None
    # A date that closes a period (an absence's ``end_date``): never before the
    # event's own date, and it counts as the event's end for "nothing after".
    ends_period: bool = False
    # How a refusal names what a reference points at ("training provider").
    label: str | None = None

    @model_validator(mode="after")
    def _options_fit_the_format(self):
        if self.values is not None and (self.format != "text" or not self.values):
            raise ValueError("values (a closed list) needs format 'text' and at least one value")
        if self.gt is not None and self.format not in ("integer", "number"):
            raise ValueError("gt needs format 'integer' or 'number'")
        if self.ends_period and self.format != "date":
            raise ValueError("ends_period needs format 'date'")
        return self


class EventTypeSpec(_Strict):
    """One event type: what happened, and the facts it carries."""

    description: str | None = None
    fields: dict[str, FieldSpec] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _field_names(self):
        for name in self.fields:
            if not _NAME.fullmatch(name):
                raise ValueError(f"field name {name!r} must be snake_case")
            if name in BASE_EVENT_FIELDS:
                raise ValueError(f"field {name!r} is common to every event and cannot be redefined")
        if sum(spec.ends_period for spec in self.fields.values()) > 1:
            raise ValueError("at most one field may end the period")
        return self


class DocumentTypeSpec(_Strict):
    """One document type. A recurring one (a payslip) may have no event (D3a)."""

    description: str | None = None
    recurring: bool = False


class StoryRules(_Strict):
    """Rules between events that no single event can check (BR-06)."""

    # The event that opens the story: at most one, nothing happens before it.
    first_event: str | None = None
    # The first event's date equals the start date of the employment it opens.
    first_event_starts_employment: bool = False
    # The event that closes the story: at most one, nothing happens or ends after it.
    last_event: str | None = None
    # How a refusal names the last event's date ("last working day" for HR).
    last_event_label: str | None = None


class EventBase(BaseModel):
    """What every event has, in every domain. The event classes of a domain
    extend it with the fields of their type."""

    # A field the event type does not define is refused, never silently dropped.
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    date: dt.date
    participant_ids: list[str]
    label: str | None = None
    summary: str | None = None
    # v1.2 (H4): who signs the event's documents, a persona of the case. Not
    # written when empty, so older cases are saved byte for byte as before.
    signed_by: str | None = Field(default=None, exclude_if=lambda value: value is None)


_FORMAT_TYPES = {
    "text": str, "date": dt.date, "money": Money,
    "integer": int, "number": float, "persona": str, "organisation": str,
}


def _class_name(event_type: str) -> str:
    return "".join(part.capitalize() for part in event_type.split("_")) + "Event"


class DomainConfig(_Strict):
    """Everything a case of one domain is checked against."""

    name: str
    version: str = "1"
    description: str | None = None
    # The dossier's key number (``dossier.employee_number`` for HR).
    case_number_pattern: str = "[0-9]{6}"
    roles: list[str] = Field(min_length=1)
    event_types: dict[str, EventTypeSpec] = Field(min_length=1)
    document_types: dict[str, DocumentTypeSpec] = Field(min_length=1)
    rules: StoryRules = Field(default_factory=StoryRules)

    model_config = ConfigDict(extra="forbid", frozen=True, ignored_types=(cached_property,))

    @model_validator(mode="after")
    def _consistent(self):
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"domain name {self.name!r} must be snake_case")
        for kind, names in (("event type", self.event_types), ("document type", self.document_types),
                            ("role", dict.fromkeys(self.roles))):
            for name in names:
                if not _NAME.fullmatch(name):
                    raise ValueError(f"{kind} {name!r} must be snake_case")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("roles must be unique")
        for rule in ("first_event", "last_event"):
            name = getattr(self.rules, rule)
            if name is not None and name not in self.event_types:
                raise ValueError(f"rules.{rule}: {name!r} is not an event type of this domain")
        if self.rules.first_event_starts_employment and self.rules.first_event is None:
            raise ValueError("rules.first_event_starts_employment needs rules.first_event")
        try:
            re.compile(self.case_number_pattern)
        except re.error as error:
            raise ValueError(f"case_number_pattern is not a regular expression: {error}")
        return self

    # --- what the case model reads ------------------------------------------

    def is_case_number(self, value) -> bool:
        return isinstance(value, str) and re.fullmatch(self.case_number_pattern, value) is not None

    def recurring_document_types(self) -> frozenset[str]:
        return frozenset(n for n, spec in self.document_types.items() if spec.recurring)

    @cached_property
    def event_classes(self) -> dict[str, type[EventBase]]:
        """One pydantic class per event type, built from the configuration."""
        classes = {}
        for name, spec in self.event_types.items():
            fields = {"type": (Literal[name], ...)}
            for field_name, field in spec.fields.items():
                kind = Literal[tuple(field.values)] if field.values else _FORMAT_TYPES[field.format]
                info = Field(gt=field.gt, json_schema_extra=(
                    {"reference": field.format} if field.format in REFERENCE_FORMATS else None))
                if field.required:
                    fields[field_name] = (kind, info)
                else:
                    info = Field(default=None, gt=field.gt, json_schema_extra=info.json_schema_extra)
                    fields[field_name] = (kind | None, info)
            classes[name] = create_model(
                _class_name(name), __base__=EventBase, __doc__=spec.description, **fields,
            )
        return classes

    @cached_property
    def event_adapter(self) -> TypeAdapter:
        """Validates an event of any type of this domain (``type`` picks the class)."""
        union = Union[tuple(self.event_classes.values())] if len(self.event_classes) > 1 \
            else next(iter(self.event_classes.values()))
        return TypeAdapter(Annotated[union, Field(discriminator="type")]
                           if len(self.event_classes) > 1 else union)

    def field_spec(self, event_type: str, field: str) -> FieldSpec | None:
        spec = self.event_types.get(event_type)
        return spec.fields.get(field) if spec else None


_DOMAINS: dict[str, DomainConfig] = {}


def register_domain(config: DomainConfig) -> DomainConfig:
    """Make a domain known by name. Registering the same name again replaces
    it only with an identical configuration; a different one needs a new name."""
    old = _DOMAINS.get(config.name)
    if old is not None and old != config:
        raise ValueError(f"domain {config.name!r} is already registered with another configuration")
    _DOMAINS[config.name] = config
    return config


def get_domain(name: str) -> DomainConfig:
    try:
        return _DOMAINS[name]
    except KeyError:
        raise ValueError(
            f"unknown domain {name!r}; known: {', '.join(sorted(_DOMAINS)) or 'none'}"
        ) from None
