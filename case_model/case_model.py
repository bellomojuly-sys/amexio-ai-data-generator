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

class Event(BaseModel):
    id: str
    type: str
    label: str
    date: date
    participant_ids: list[str]
    summary: str

class CaseModel:
    def __init__(self, case_number):
        self.case_number = case_number
        self.personas = {}
        self.events = {}

    def add_persona(self, **fields):
        new_id = next_id("P", 3, self.personas)
        self.personas[new_id] = Persona(id=new_id, **fields)
        return new_id

    def add_event(self, **fields):
        for pid in fields["participant_ids"]:
            if pid not in self.personas:
                raise ValueError(f"Unknown persona: {pid}")
        new_id = next_id("EVT-", 3, self.events)
        self.events[new_id] = Event(id=new_id, **fields)
        return new_id

