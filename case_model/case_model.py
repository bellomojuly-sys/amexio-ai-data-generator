"""The case model — the single place where the facts of one dossier live.

Who is involved (personas, organisations), how they are employed, what
happened (events) and the documents that record it. Other modules do not
keep their own copy of a name, a date or an amount; they read it from here.

The parts (AX-006 to AX-010):

- Persona        a person in the dossier
- Organisation   a company or body (the employer, an agency, ...)
- Employment     a person's job at an organisation
- Event          something that happened, on a date, with participants
- Document       a record tied to an event, with AMEXIO's five metadata fields
- Dossier        the dossier-level facts (employee number, title, description)
- Case           one object that holds all of the above and validates in one call

IDs are assigned by code, never by a caller (AX-012); dates are ISO 8601
(AX-013); amounts are Money, a number plus a currency (AX-014).
"""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from .format_rules import (
    Money,
    is_valid_employee_number,
    next_id,
    reject_caller_id,
)


class Persona(BaseModel):
    id: str
    name: str
    role: str
    salutation: str
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
    """A person's job at an organisation. It has no ID of its own; it is
    identified by the persona and the organisation it links."""

    persona_id: str
    organisation_id: str
    position: str
    department: str
    start_date: date
    contract_type: str
    hours: float
    salary: Money


class DocumentMetadata(BaseModel):
    """AMEXIO's five metadata attributes for a document."""

    employee_id: str
    document_type: str
    document_date: date
    confidential: bool
    tags: list[str] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    type: str
    event_id: str
    participant_ids: list[str]
    text: str
    metadata: DocumentMetadata


class Event(BaseModel):
    id: str
    type: str
    label: str
    date: date
    participant_ids: list[str]
    summary: str


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
    single call: each part is filed under its own ID, every job and event
    points at a persona or organisation the Case holds, and every document
    points at an event the Case holds.
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
        for collection, label in (
            (self.personas, "Persona"),
            (self.organisations, "Organisation"),
            (self.events, "Event"),
            (self.documents, "Document"),
        ):
            for key, part in collection.items():
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

        for did, document in self.documents.items():
            if document.event_id not in self.events:
                raise ValueError(
                    f"Document {did} references unknown event {document.event_id!r}."
                )
            for pid in document.participant_ids:
                if pid not in self.personas:
                    raise ValueError(f"Document {did} references unknown persona {pid!r}.")
        return self


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
        reject_caller_id(fields)
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        new_id = next_id("event", self.events)
        self.events[new_id] = Event(id=new_id, **fields)
        return new_id

    def add_document(self, **fields):
        reject_caller_id(fields)
        if fields["event_id"] not in self.events:
            raise ValueError(f"Unknown event: {fields['event_id']}")
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
