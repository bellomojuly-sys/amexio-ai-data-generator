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

from pydantic import BaseModel, Field, SerializeAsAny, model_validator

from .domain import REFERENCE_FORMATS, EventBase, get_domain
from .domains import HR  # registers the HR domain
from .format_rules import ContractType, Money, next_id, reject_caller_id, validate_id

# Every event class of every domain extends EventBase (case model v2.0).
Event = EventBase


class Persona(BaseModel):
    id: str
    name: str
    # One of the roles of the case's domain (v2.0); HR: employee, manager, ...
    role: str
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
    # One of the document types of the case's domain (v2.0).
    document_type: str
    document_date: date
    confidential: bool
    tags: list[str] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    # One of the document types of the case's domain (v2.0).
    type: str
    # Empty only for recurring documents such as payslips (D3a).
    event_id: str | None = None
    participant_ids: list[str]
    # Derived from the facts when needed; not a second copy of them (D3b).
    text: str | None = None
    metadata: DocumentMetadata


class Dossier(BaseModel):
    """Dossier-level facts (AX-009). The key number (``employee_number`` for
    HR) must match the pattern of the case's domain; HR: six digits."""

    employee_number: str
    folder_title: str | None = None
    description: str | None = None


def _case_number_error(domain, number):
    if domain.name == "hr":
        return f"Employee number must be six digits, got {number!r} (field employee_number)."
    return (f"Case number {number!r} does not match the {domain.name} pattern "
            f"{domain.case_number_pattern} (field employee_number).")


def _event_of(domain, event):
    """``event`` as an instance of the domain's class for its type (a dict
    from JSON, or an event built for this domain)."""
    if isinstance(event, EventBase) and domain.event_classes.get(event.type) is type(event):
        return event
    raw = event.model_dump() if isinstance(event, BaseModel) else event
    return domain.event_adapter.validate_python(raw)


class Case(BaseModel):
    """AX-010 — one object that holds all the parts of a dossier.

    Building a Case validates every part and the links between them in a
    single call: each part is filed under its own well-formed ID, every job
    and event points at a persona or organisation the Case holds, every
    document points at an event the Case holds, and the events tell a
    possible story. Since v2.0 the event types, document types, roles and the
    rules between events come from the configuration of the case's domain.
    """

    case_number: str
    # The case's domain (v2.0). Not written for HR, so HR files stay as before.
    domain: str = Field(default="hr", exclude_if=lambda value: value == "hr")
    dossier: Dossier
    personas: dict[str, Persona] = Field(default_factory=dict)
    organisations: dict[str, Organisation] = Field(default_factory=dict)
    employments: list[Employment] = Field(default_factory=list)
    events: dict[str, SerializeAsAny[EventBase]] = Field(default_factory=dict)
    documents: dict[str, Document] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _events_of_the_domain(cls, data):
        """Each event becomes the class its domain gives its type, so an
        appraisal without a rating, or a type the domain lacks, is refused."""
        if isinstance(data, dict) and isinstance(data.get("events"), dict):
            domain = get_domain(data.get("domain") or "hr")
            data = {**data, "events": {key: _event_of(domain, event)
                                       for key, event in data["events"].items()}}
        return data

    @model_validator(mode="after")
    def _links_hold(self):
        domain = get_domain(self.domain)
        if not domain.is_case_number(self.dossier.employee_number):
            raise ValueError(_case_number_error(domain, self.dossier.employee_number))

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
                        f"{label} filed under {key!r} carries id {part.id!r} (field id)."
                    )

        for pid, persona in self.personas.items():
            if persona.role not in domain.roles:
                raise ValueError(
                    f"Persona {pid} has role {persona.role!r}, not one of "
                    f"{', '.join(domain.roles)} (field role)."
                )
            if persona.organisation_id and persona.organisation_id not in self.organisations:
                raise ValueError(
                    f"Persona {pid} points at unknown organisation "
                    f"{persona.organisation_id!r} (field organisation_id)."
                )

        for job in self.employments:
            if job.persona_id not in self.personas:
                raise ValueError(f"Employment points at unknown persona {job.persona_id!r} (field persona_id).")
            if job.organisation_id not in self.organisations:
                raise ValueError(
                    f"Employment of {job.persona_id} points at unknown organisation {job.organisation_id!r} (field organisation_id)."
                )

        for eid, event in self.events.items():
            for pid in event.participant_ids:
                if pid not in self.personas:
                    raise ValueError(f"Event {eid} references unknown persona {pid!r} (field participant_ids).")
            if event.signed_by is not None and event.signed_by not in self.personas:
                raise ValueError(
                    f"Event {eid} is signed by unknown persona {event.signed_by!r} "
                    "(field signed_by)."
                )
            for name, spec in domain.event_types[event.type].fields.items():
                value = getattr(event, name)
                if value is None or spec.format not in REFERENCE_FORMATS:
                    continue
                held = self.personas if spec.format == "persona" else self.organisations
                if value not in held:
                    raise ValueError(
                        f"Event {eid} points at unknown {spec.label or spec.format} "
                        f"{value!r} (field {name})."
                    )

        self._events_tell_a_possible_story(domain)

        recurring = domain.recurring_document_types()
        for did, document in self.documents.items():
            if document.type not in domain.document_types:
                raise ValueError(
                    f"Document {did} has type {document.type!r}, not one of the "
                    f"{domain.name} document types (field type)."
                )
            if document.event_id is None:
                if document.type not in recurring:
                    raise ValueError(
                        f"Document {did} ({document.type}) needs an event; only "
                        f"{', '.join(sorted(recurring)) or 'recurring types'} may have none (field event_id)."
                    )
            elif document.event_id not in self.events:
                raise ValueError(
                    f"Document {did} references unknown event {document.event_id!r} (field event_id)."
                )
            for pid in document.participant_ids:
                if pid not in self.personas:
                    raise ValueError(f"Document {did} references unknown persona {pid!r} (field participant_ids).")
            if document.metadata.document_type != document.type:
                raise ValueError(
                    f"Document {did} is a {document.type} but its metadata says "
                    f"{document.metadata.document_type} (field metadata.document_type)."
                )
            if document.metadata.employee_id != self.dossier.employee_number:
                raise ValueError(
                    f"Document {did} belongs to employee {document.metadata.employee_id}, "
                    f"not to this dossier ({self.dossier.employee_number}) (field metadata.employee_id)."
                )
        return self

    def _events_tell_a_possible_story(self, domain):
        """BR-06, GD-03 — the rules between events of the case's domain."""
        rules = domain.rules

        def period_end(event):
            for name, spec in domain.event_types[event.type].fields.items():
                if spec.ends_period and getattr(event, name) is not None:
                    return name, getattr(event, name)
            return "date", event.date

        if rules.first_event:
            firsts = [e for e in self.events.values() if e.type == rules.first_event]
            if len(firsts) > 1:
                raise ValueError(f"A case has at most one {rules.first_event} event, found {len(firsts)}: "
                                 f"{', '.join(e.id for e in firsts)} (field type).")
            if firsts:
                first = firsts[0]
                if rules.first_event_starts_employment:
                    starts = {
                        job.start_date for job in self.employments
                        if job.persona_id in first.participant_ids
                    }
                    if starts and first.date not in starts:
                        raise ValueError(
                            f"{rules.first_event.capitalize()} event {first.id} is dated {first.date}, "
                            f"but the employment starts on {min(starts)} (field date)."
                        )
                for event in self.events.values():
                    if event.date < first.date:
                        raise ValueError(
                            f"Event {event.id} ({event.type}, {event.date}) happens before "
                            f"the {rules.first_event} on {first.date} (field date)."
                        )

        if rules.last_event:
            lasts = [e for e in self.events.values() if e.type == rules.last_event]
            if len(lasts) > 1:
                raise ValueError(
                    f"A case has at most one {rules.last_event} event, found {len(lasts)}: "
                    f"{', '.join(e.id for e in lasts)} (field type)."
                )
            if lasts:
                last_day = lasts[0].date
                for event in self.events.values():
                    field, ends = period_end(event)
                    if ends > last_day:
                        raise ValueError(
                            f"Event {event.id} ({event.type}) runs to {ends}, after the "
                            f"{rules.last_event_label or rules.last_event + ' on'} {last_day} (field {field})."
                        )

        for event in self.events.values():
            field, ends = period_end(event)
            if ends < event.date:
                raise ValueError(
                    f"{event.type.replace('_', ' ').capitalize()} {event.id} ends on {ends}, "
                    f"before it starts on {event.date} (field {field})."
                )


class CaseModel:
    """Builds a case step by step, assigning every ID in code (AX-011, AX-012).

    ``domain`` names the configuration the case is checked against (HR by
    default). When the parts are in, ``build()`` returns a validated :class:`Case`.
    """

    def __init__(self, case_number, domain="hr"):
        self.case_number = case_number
        self.domain = get_domain(domain)
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
        builder = cls(case.case_number, case.domain)
        builder.dossier = case.dossier
        builder.personas = dict(case.personas)
        builder.organisations = dict(case.organisations)
        builder.employments = list(case.employments)
        builder.events = dict(case.events)
        builder.documents = dict(case.documents)
        return builder

    def set_dossier(self, **fields):
        reject_caller_id(fields)
        dossier = Dossier(**fields)
        if not self.domain.is_case_number(dossier.employee_number):
            raise ValueError(_case_number_error(self.domain, dossier.employee_number))
        self.dossier = dossier
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
            raise ValueError(f"Unknown organisation: {org_id} (field organisation_id)")
        role = fields.get("role")
        if role not in self.domain.roles:
            raise ValueError(
                f"Unknown role: {role!r}, not one of {', '.join(self.domain.roles)} (field role)"
            )
        new_id = next_id("persona", self.personas)
        self.personas[new_id] = Persona(id=new_id, **fields)
        return new_id

    def add_employment(self, **fields):
        reject_caller_id(fields)
        if fields["persona_id"] not in self.personas:
            raise ValueError(f"Unknown persona: {fields['persona_id']} (field persona_id)")
        if fields["organisation_id"] not in self.organisations:
            raise ValueError(f"Unknown organisation: {fields['organisation_id']} (field organisation_id)")
        job = Employment(**fields)
        self.employments.append(job)
        return job

    def add_event(self, **fields):
        """Add an event of any type of the domain; ``type`` picks the class and its fields."""
        reject_caller_id(fields)
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid} (field participant_ids)")
        spec = self.domain.event_types.get(fields.get("type"))
        for name, field in (spec.fields.items() if spec else ()):
            value = fields.get(name)
            if value is None or field.format not in REFERENCE_FORMATS:
                continue
            held = self.personas if field.format == "persona" else self.organisations
            if value not in held:
                kind = "persona" if field.format == "persona" else "organisation"
                raise ValueError(f"Unknown {kind}: {value} (field {name})")
        signer = fields.get("signed_by")
        if signer is not None and signer not in self.personas:
            raise ValueError(f"Unknown persona: {signer} (field signed_by)")
        new_id = next_id("event", self.events)
        self.events[new_id] = self.domain.event_adapter.validate_python({"id": new_id, **fields})
        return new_id

    def add_document(self, **fields):
        reject_caller_id(fields)
        if fields.get("type") not in self.domain.document_types:
            raise ValueError(
                f"Unknown document type: {fields.get('type')!r} for domain "
                f"{self.domain.name} (field type)"
            )
        event_id = fields.get("event_id")
        if event_id is not None and event_id not in self.events:
            raise ValueError(f"Unknown event: {event_id} (field event_id)")
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid} (field participant_ids)")
        new_id = next_id("document", self.documents)
        self.documents[new_id] = Document(id=new_id, **fields)
        return new_id

    def build(self):
        if self.dossier is None:
            raise ValueError("A case needs dossier facts; call set_dossier() first (field dossier).")
        return Case(
            case_number=self.case_number,
            domain=self.domain.name,
            dossier=self.dossier,
            personas=self.personas,
            organisations=self.organisations,
            employments=self.employments,
            events=self.events,
            documents=self.documents,
        )
