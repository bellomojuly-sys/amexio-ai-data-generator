"""Demo of case model v1: build the HR reference dossier 100101, show it,
save it to four JSON files, load it back, and show one refusal.

Run from the repository root:  python demo.py
"""

from case_model import CaseModel
from case_model.reference_dossier import build_reference_case
from case_model.storage import save_case, load_case

case = build_reference_case()

print(f"Dossier {case.case_number} — {case.dossier.folder_title}\n")

print("Organisations:")
for oid, org in case.organisations.items():
    print(f"  {oid}  {org.name}")

print("Personas:")
for pid, person in case.personas.items():
    print(f"  {pid}  {person.name} ({person.role})")

print("Storyline:")
for eid, event in case.events.items():
    print(f"  {eid}  {event.date}  {event.label}  participants: {event.participant_ids}")

print("Documents:")
for did, doc in case.documents.items():
    print(f"  {did}  {doc.type:<22} event {doc.event_id}  metadata date {doc.metadata.document_date}")

folder = save_case(case, "demo_output/100101")
print(f"\nSaved to {folder}/ (case.json, cast.json, storyline.json, documents.json)")
print("Loaded back and equal to the original:", load_case(folder) == case)

print("\nRefusal test — a date that is not ISO 8601:")
try:
    CaseModel("100102").add_persona(
        name="Test", role="employee", salutation="Mr", date_of_birth="12/03/1988"
    )
except Exception as error:
    print("  refused:", str(error).splitlines()[0])
