from datetime import date
from pydantic import BaseModel


def next_id(prefix, digits, existing_ids):
    numbers = [int(i[len(prefix):]) for i in existing_ids]
    number = max(numbers, default=0) + 1
    return f"{prefix}{number:0{digits}d}"

class Persona(BaseModel):
    id: str
    name: str
    role: str
    salutation: str
    date_of_birth: date | None = None
    address: str | None = None
    organisation_id: str | None = None

class Event(BaseModel):
    id: str
    type: str
    label: str
    date: date
    participant_ids: list[str]
    summary: str


class Organisation(BaseModel):
    id: str
    name: str
    type: str

class Employment(BaseModel):
    id: str
    persona_id: str
    organisation_id: str
    position: str
    department: str
    start_date: date
    contract_type: str
    hours_per_week: int
    gross_monthly_salary: float


class DocumentMetadata(BaseModel):
    employee_id: str
    document_type: str
    document_date: date
    confidential: bool
    tags: list[str]


class Document(BaseModel):
    id: str
    type: str
    title: str
    event_id: str
    participant_ids: list[str]
    text: str | None = None
    metadata: DocumentMetadata


class CaseModel:
    def __init__(self, case_number):
        self.case_number = case_number
        self.personas = {}
        self.events = {}
        self.organisations = {}
        self.employments = {}
        self.documents = {}

    def add_organisation(self, **fields):
        new_id = next_id("ORG-", 2, self.organisations)
        self.organisations[new_id] = Organisation(id=new_id, **fields)
        return new_id

    def add_persona(self, **fields):
        org_id = fields.get("organisation_id")
        if org_id is not None and org_id not in self.organisations:
            raise ValueError(f"Unknown organisation: {org_id}")
        new_id = next_id("P", 3, self.personas)
        self.personas[new_id] = Persona(id=new_id, **fields)
        return new_id

    def add_employment(self, **fields):
        if fields["persona_id"] not in self.personas:
            raise ValueError(f"Unknown persona: {fields['persona_id']}")
        if fields["organisation_id"] not in self.organisations:
            raise ValueError(f"Unknown organisation: {fields['organisation_id']}")
        new_id = next_id("EMP-", 3, self.employments)
        self.employments[new_id] = Employment(id=new_id, **fields)
        return new_id

    def add_event(self, **fields):
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        new_id = next_id("EVT-", 3, self.events)
        self.events[new_id] = Event(id=new_id, **fields)
        return new_id

    def add_document(self, **fields):
        if fields["event_id"] not in self.events:
            raise ValueError(f"Unknown event: {fields['event_id']}")
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        new_id = next_id("DOC-", 3, self.documents)
        self.documents[new_id] = Document(id=new_id, **fields)
        return new_id
