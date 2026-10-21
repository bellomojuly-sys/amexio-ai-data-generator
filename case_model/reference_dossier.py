"""The HR reference dossier 100101 (Jan de Vries) as data — AX-016, AX-017.

A small set of hand-entered facts the case model uses as its own reference:
a regression fixture (AX-019) and the case that save/load round-trips
(AX-018). It is test data, not generated content — the document ``text`` is
a one-line stub. Writing the real document bodies is the generation module's
job, not the case model's; it reads these facts from here.

All people and companies here are fictitious.
"""

import json
from pathlib import Path

from .case_model import CaseModel, Money


def build_reference_case():
    """Build and return the validated reference :class:`Case` 100101."""
    case = CaseModel("100101")

    case.set_dossier(
        employee_number="100101",
        folder_title="Personeelsdossier Jan de Vries",
        description="HR dossier for Jan de Vries, Software Developer.",
    )

    employer = case.add_organisation(name="AMEXIO B.V.", kind="employer")

    jan = case.add_persona(
        name="Jan de Vries",
        role="employee",
        salutation="Mr",
        date_of_birth="1988-07-12",
    )
    hr_officer = case.add_persona(
        name="Petra Jansen",
        role="hr_officer",
        salutation="Ms",
        organisation_id=employer,
    )
    manager = case.add_persona(
        name="Dirk Bakker",
        role="manager",
        salutation="Mr",
        organisation_id=employer,
    )

    case.add_employment(
        persona_id=jan,
        organisation_id=employer,
        position="Software Developer",
        department="Engineering",
        start_date="2021-03-01",
        contract_type="permanent",
        hours=40,
        salary=Money(amount="3850.00", currency="EUR"),
    )

    # Storyline: one event per thing that happened, in time order.
    hiring = case.add_event(
        type="hiring", label="Employment contract signed", date="2021-03-01",
        participant_ids=[jan, hr_officer], summary="Jan de Vries starts as Software Developer.",
    )
    payroll = case.add_event(
        type="payroll", label="First payslip issued", date="2021-03-31",
        participant_ids=[jan], summary="First monthly payslip.",
    )
    review = case.add_event(
        type="review", label="Annual performance review", date="2022-02-15",
        participant_ids=[jan, manager], summary="Annual review with the line manager.",
    )
    raise_ = case.add_event(
        type="salary_change", label="Salary increase", date="2022-03-01",
        participant_ids=[jan, hr_officer], summary="Salary raised after the review.",
    )
    resignation = case.add_event(
        type="offboarding", label="Resignation received", date="2024-06-28",
        participant_ids=[jan, hr_officer], summary="Jan de Vries hands in his resignation.",
    )

    # Five documents, each tied to its event. The text is a stub (see module docstring).
    case.add_document(
        type="employment_contract", event_id=hiring, participant_ids=[jan, hr_officer],
        text="[stub] Employment contract for Jan de Vries.",
        metadata={"employee_id": "100101", "document_type": "employment_contract",
                  "document_date": "2021-03-01", "confidential": True,
                  "tags": ["contract", "hr"]},
    )
    case.add_document(
        type="payslip", event_id=payroll, participant_ids=[jan],
        text="[stub] Payslip for March 2021.",
        metadata={"employee_id": "100101", "document_type": "payslip",
                  "document_date": "2021-03-31", "confidential": True,
                  "tags": ["payroll"]},
    )
    case.add_document(
        type="performance_review", event_id=review, participant_ids=[jan, manager],
        text="[stub] Performance review 2022.",
        metadata={"employee_id": "100101", "document_type": "performance_review",
                  "document_date": "2022-02-15", "confidential": True,
                  "tags": ["review"]},
    )
    case.add_document(
        type="salary_change_letter", event_id=raise_, participant_ids=[jan, hr_officer],
        text="[stub] Salary change letter.",
        metadata={"employee_id": "100101", "document_type": "salary_change_letter",
                  "document_date": "2022-03-01", "confidential": True,
                  "tags": ["salary", "hr"]},
    )
    case.add_document(
        type="resignation_letter", event_id=resignation, participant_ids=[jan, hr_officer],
        text="[stub] Resignation letter.",
        metadata={"employee_id": "100101", "document_type": "resignation_letter",
                  "document_date": "2024-06-28", "confidential": False,
                  "tags": ["offboarding"]},
    )

    return case.build()


# The frozen export of the reference dossier (AX-019). The golden test in
# test_reference_dossier.py compares build_reference_case() against this file,
# so any change to a fact above fails the test. Regenerate it only when the
# change is intended, with: python3 -m case_model.reference_dossier
GOLDEN_PATH = Path(__file__).with_name("reference_dossier.golden.json")


def write_golden():
    """Write the reference dossier's exported form to reference_dossier.golden.json."""
    payload = build_reference_case().model_dump(mode="json")
    GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return GOLDEN_PATH


if __name__ == "__main__":
    print(f"wrote {write_golden()}")
