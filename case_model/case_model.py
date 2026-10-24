"""The case model — the single place where the facts of one dossier live.

Who is involved (personas, organisations), how they are employed, what
happened (events) and the documents that record it. Other modules do not
keep their own copy of a name, a date or an amount; they read it from here.

The parts (AX-006 to AX-010, typed events in v1.1):

- Persona        a person in the dossier
- Organisation   a company or body (the employer, a training provider, ...)
- Employment     a person's job at an organisation, as agreed at hire
- Event          something that happened, on a date, with participants; one
                 class per type (hire, contract_change, training, appraisal,
                 medical_check, absence, termination), each with its own facts
- Document       a record tied to an event, with AMEXIO's five metadata fields
- Dossier        the dossier-level facts (employee number, title, description)
- Case           one object that holds all of the above and validates in one call

IDs are assigned by code, never by a caller (AX-012); dates are ISO 8601
(AX-013); amounts are Money, a number plus a currency (AX-014). Each fact is
stored once: document text is derived from the facts, so it is optional (D3b).
"""

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from .format_rules import (
    RECURRING_DOCUMENT_TYPES,
    ContractType,
    DocumentType,
    MedicalResult,
    Money,
    PersonaRole,
    Rating,
    TerminationReason,
    is_valid_employee_number,
    next_id,
    reject_caller_id,
    validate_id,
)


class Persona(BaseModel):
    id: str
    name: str
    role: PersonaRole
    salutation: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    # A professional persona (an HR officer, a manager) points at their org.
    organisation_id: str | None = None


class Organisation(BaseModel):
    id: str
    name: str
    kind: str | None = None
    address: str | None = None


class Employment(BaseModel):
    """A person's job at an organisation, as agreed at hire. It has no ID of
    its own; it is identified by the persona and the organisation it links.
    Later changes are ``contract_change`` events, not edits of this record."""

    persona_id: str
    organisation_id: str
    position: str
    department: str
    start_date: date
    contract_type: ContractType
    hours: float
    salary: Money


class DocumentMetadata(BaseModel):
    """AMEXIO's five metadata attributes for a document."""

    employee_id: str
    document_type: DocumentType
    document_date: date
    confidential: bool
    tags: list[str] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    type: DocumentType
    # Empty only for recurring documents such as payslips (D3a).
    event_id: str | None = None
    participant_ids: list[str]
    # Derived from the facts when needed; not a second copy of them (D3b).
    text: str | None = None
    metadata: DocumentMetadata


# Events (v1.1, BR-05). Every event has an id, a date and its participants;
# the "type" field tells pydantic which class to use, so an appraisal without
# a rating, or an event of an unknown type, is refused.

class _EventBase(BaseModel):
    id: str
    date: date
    participant_ids: list[str]
    label: str | None = None
    summary: str | None = None


class HireEvent(_EventBase):
    """The start of the employment. The agreed terms live in Employment."""

    type: Literal["hire"]


class ContractChangeEvent(_EventBase):
    type: Literal["contract_change"]
    reason: str
    new_salary: Money | None = None
    new_position: str | None = None
    new_contract_type: ContractType | None = None
    new_hours: float | None = None


class TrainingEvent(_EventBase):
    type: Literal["training"]
    course: str
    duration_days: int = Field(gt=0)
    provider_id: str


class AppraisalEvent(_EventBase):
    type: Literal["appraisal"]
    year: int
    rating: Rating
    comment: str | None = None


class MedicalCheckEvent(_EventBase):
    type: Literal["medical_check"]
    result: MedicalResult


class AbsenceEvent(_EventBase):
    """A sick-leave period: dates only, never a cause or diagnosis."""

    type: Literal["absence"]
    end_date: date | None = None


class TerminationEvent(_EventBase):
    """The last working day."""

    type: Literal["termination"]
    reason: TerminationReason
    notice_date: date | None = None


Event = Annotated[
    Union[
        HireEvent,
        ContractChangeEvent,
        TrainingEvent,
        AppraisalEvent,
        MedicalCheckEvent,
        AbsenceEvent,
        TerminationEvent,
    ],
    Field(discriminator="type"),
]

_EVENT = TypeAdapter(Event)


class Dossier(BaseModel):
    """Dossier-level facts (AX-009). Without an employee number it fails."""

    employee_number: str
    folder_title: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _employee_number_is_six_digits(self):
        if not is_valid_employee_number(self.employee_number):
            raise ValueError(
                f"Employee number must be six digits, got {self.employee_number!r}."
            )
        return self


class Case(BaseModel):
    """AX-010 — one object that holds all the parts of a dossier.

    Building a Case validates every part and the links between them in a
    single call: each part is filed under its own well-formed ID, every job
    and event points at a persona or organisation the Case holds, every
    document points at an event the Case holds, and the events tell a
    possible story.
    """

    case_number: str
    dossier: Dossier
    personas: dict[str, Persona] = Field(default_factory=dict)
    organisations: dict[str, Organisation] = Field(default_factory=dict)
    employments: list[Employment] = Field(default_factory=list)
    events: dict[str, Event] = Field(default_factory=dict)
    documents: dict[str, Document] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _links_hold(self):
        for collection, label, kind in (
            (self.personas, "Persona", "persona"),
            (self.organisations, "Organisation", "organisation"),
            (self.events, "Event", "event"),
            (self.documents, "Document", "document"),
        ):
            for key, part in collection.items():
                # AX-011b — a case read from JSON obeys the ID patterns too.
                validate_id(kind, key)
                if part.id != key:
                    raise ValueError(
                        f"{label} filed under {key!r} carries id {part.id!r}."
                    )

        for pid, persona in self.personas.items():
            if persona.organisation_id and persona.organisation_id not in self.organisations:
                raise ValueError(
                    f"Persona {pid} points at unknown organisation "
                    f"{persona.organisation_id!r}."
                )

        for job in self.employments:
            if job.persona_id not in self.personas:
                raise ValueError(f"Employment points at unknown persona {job.persona_id!r}.")
            if job.organisation_id not in self.organisations:
                raise ValueError(
                    f"Employment points at unknown organisation {job.organisation_id!r}."
                )

        for eid, event in self.events.items():
            for pid in event.participant_ids:
                if pid not in self.personas:
                    raise ValueError(f"Event {eid} references unknown persona {pid!r}.")
            if event.type == "training" and event.provider_id not in self.organisations:
                raise ValueError(
                    f"Event {eid} points at unknown training provider {event.provider_id!r}."
                )

        self._events_tell_a_possible_story()

        for did, document in self.documents.items():
            if document.event_id is None:
                if document.type not in RECURRING_DOCUMENT_TYPES:
                    raise ValueError(
                        f"Document {did} ({document.type}) needs an event; only "
                        f"{', '.join(sorted(RECURRING_DOCUMENT_TYPES))} may have none."
                    )
            elif document.event_id not in self.events:
                raise ValueError(
                    f"Document {did} references unknown event {document.event_id!r}."
                )
            for pid in document.participant_ids:
                if pid not in self.personas:
                    raise ValueError(f"Document {did} references unknown persona {pid!r}.")
            if document.metadata.document_type != document.type:
                raise ValueError(
                    f"Document {did} is a {document.type} but its metadata says "
                    f"{document.metadata.document_type}."
                )
            if document.metadata.employee_id != self.dossier.employee_number:
                raise ValueError(
                    f"Document {did} belongs to employee {document.metadata.employee_id}, "
                    f"not to this dossier ({self.dossier.employee_number})."
                )
        return self

    def _events_tell_a_possible_story(self):
        """BR-06 — rules between events that no single event can check."""
        hires = [e for e in self.events.values() if e.type == "hire"]
        if len(hires) > 1:
            raise ValueError(f"A case has at most one hire event, found {len(hires)}.")
        if hires:
            hire = hires[0]
            starts = {
                job.start_date for job in self.employments
                if job.persona_id in hire.participant_ids
            }
            if starts and hire.date not in starts:
                raise ValueError(
                    f"Hire event {hire.id} is dated {hire.date}, but the employment "
                    f"starts on {min(starts)}."
                )
            for event in self.events.values():
                if event.date < hire.date:
                    raise ValueError(
                        f"Event {event.id} ({event.type}, {event.date}) happens before "
                        f"the hire on {hire.date}."
                    )

        terminations = [e for e in self.events.values() if e.type == "termination"]
        if len(terminations) > 1:
            raise ValueError(
                f"A case has at most one termination event, found {len(terminations)}."
            )
        if terminations:
            last_day = terminations[0].date
            for event in self.events.values():
                ends = getattr(event, "end_date", None) or event.date
                if ends > last_day:
                    raise ValueError(
                        f"Event {event.id} ({event.type}) runs to {ends}, after the "
                        f"last working day {last_day}."
                    )

        for event in self.events.values():
            if event.type == "absence" and event.end_date and event.end_date < event.date:
                raise ValueError(
                    f"Absence {event.id} ends on {event.end_date}, before it starts "
                    f"on {event.date}."
                )


class CaseModel:
    """Builds a case step by step, assigning every ID in code (AX-011, AX-012).

    When the parts are in, ``build()`` returns a validated :class:`Case`.
    """

    def __init__(self, case_number):
        self.case_number = case_number
        self.dossier = None
        self.personas = {}
        self.organisations = {}
        self.employments = []
        self.events = {}
        self.documents = {}

    @classmethod
    def from_case(cls, case):
        """A builder that continues from an existing case, e.g. to add the
        storyline to the cases made from the employees JSON."""
        builder = cls(case.case_number)
        builder.dossier = case.dossier
        builder.personas = dict(case.personas)
        builder.organisations = dict(case.organisations)
        builder.employments = list(case.employments)
        builder.events = dict(case.events)
        builder.documents = dict(case.documents)
        return builder

    def set_dossier(self, **fields):
        reject_caller_id(fields)
        self.dossier = Dossier(**fields)
        return self.dossier

    def add_organisation(self, **fields):
        reject_caller_id(fields)
        new_id = next_id("organisation", self.organisations)
        self.organisations[new_id] = Organisation(id=new_id, **fields)
        return new_id

    def add_persona(self, **fields):
        reject_caller_id(fields)
        org_id = fields.get("organisation_id")
        if org_id and org_id not in self.organisations:
            raise ValueError(f"Unknown organisation: {org_id}")
        new_id = next_id("persona", self.personas)
        self.personas[new_id] = Persona(id=new_id, **fields)
        return new_id

    def add_employment(self, **fields):
        reject_caller_id(fields)
        if fields["persona_id"] not in self.personas:
            raise ValueError(f"Unknown persona: {fields['persona_id']}")
        if fields["organisation_id"] not in self.organisations:
            raise ValueError(f"Unknown organisation: {fields['organisation_id']}")
        job = Employment(**fields)
        self.employments.append(job)
        return job

    def add_event(self, **fields):
        """Add an event of any type; ``type`` picks the class and its fields."""
        reject_caller_id(fields)
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        provider = fields.get("provider_id")
        if provider and provider not in self.organisations:
            raise ValueError(f"Unknown organisation: {provider}")
        new_id = next_id("event", self.events)
        self.events[new_id] = _EVENT.validate_python({"id": new_id, **fields})
        return new_id

    def add_document(self, **fields):
        reject_caller_id(fields)
        event_id = fields.get("event_id")
        if event_id is not None and event_id not in self.events:
            raise ValueError(f"Unknown event: {event_id}")
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        new_id = next_id("document", self.documents)
        self.documents[new_id] = Document(id=new_id, **fields)
        return new_id

    def build(self):
        if self.dossier is None:
            raise ValueError("A case needs dossier facts; call set_dossier() first.")
        return Case(
            case_number=self.case_number,
            dossier=self.dossier,
            personas=self.personas,
            organisations=self.organisations,
            employments=self.employments,
            events=self.events,
            documents=self.documents,
        )
