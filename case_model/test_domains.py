"""Case model v2.0 — the lists come from a domain configuration (GD-01 … GD-04).

HR is the first domain and all HR tests run unchanged. Here: the HR
configuration holds exactly v1.2's lists, a malformed configuration is refused,
and a second domain (insurance claims) gets its own timeline, checked by its
own rules, through the same case model.
"""

import pytest
from pydantic import ValidationError
from case_model import Case, CaseModel, DomainConfig, Money, register_domain
from case_model.domains import HR
from case_model.fill import UnresolvedPlaceholders, fact_paths, fill_text
from case_model.format_rules import DocumentType, PersonaRole, RECURRING_DOCUMENT_TYPES
from case_model.storage import load_case, save_case
from typing import get_args

CLAIMS = register_domain(DomainConfig.model_validate({
    "name": "insurance_claim",
    "description": "A home-insurance claim: from the policy to the payout.",
    "case_number_pattern": "CL[0-9]{6}",
    "roles": ["policyholder", "adjuster", "inspector"],
    "event_types": {
        "policy_start": {"fields": {"premium": {"format": "money", "required": True}}},
        "claim_filed": {"fields": {
            "cause": {"format": "text", "required": True,
                      "values": ["Water damage", "Fire", "Theft", "Storm"]},
            "claimed_amount": {"format": "money", "required": True},
        }},
        "inspection": {"fields": {
            "inspector_id": {"format": "persona", "required": True, "label": "inspector"},
            "finding": {"format": "text", "required": True},
        }},
        "repair": {"fields": {"end_date": {"format": "date", "ends_period": True}}},
        "payout": {"fields": {"amount": {"format": "money", "required": True}}},
        "claim_closed": {},
    },
    "document_types": {
        "policy": {}, "claim_form": {}, "inspection_report": {},
        "premium_statement": {"recurring": True},
    },
    "rules": {"first_event": "policy_start", "last_event": "claim_closed"},
}))


def _claim():
    case = CaseModel("CL000123", domain="insurance_claim")
    case.set_dossier(employee_number="CL000123", folder_title="Claim CL000123 Fam. Jansen")
    insurer = case.add_organisation(name="Delta Verzekeringen (fictional)", kind="insurer")
    holder = case.add_persona(name="Anna Jansen", role="policyholder")                      # P001
    inspector = case.add_persona(name="R. de Groot", role="inspector", organisation_id=insurer)  # P002
    eur = lambda n: Money(amount=n, currency="EUR")
    case.add_event(type="policy_start", date="2024-01-01", participant_ids=[holder],
                   premium=eur("38.50"))
    case.add_event(type="claim_filed", date="2025-03-04", participant_ids=[holder],
                   cause="Water damage", claimed_amount=eur("4200.00"))
    case.add_event(type="inspection", date="2025-03-11", participant_ids=[holder, inspector],
                   inspector_id=inspector, finding="Leaking pipe under the kitchen floor.",
                   signed_by=inspector)
    case.add_event(type="repair", date="2025-03-20", end_date="2025-04-02", participant_ids=[holder])
    case.add_event(type="payout", date="2025-04-10", participant_ids=[holder], amount=eur("3850.00"))
    case.add_event(type="claim_closed", date="2025-04-15", participant_ids=[holder])
    case.add_document(type="inspection_report", event_id="EVT-003",
                      participant_ids=[holder, inspector],
                      metadata={"employee_id": "CL000123", "document_type": "inspection_report",
                                "document_date": "2025-03-11", "confidential": True})
    return case


# GD-01 — the HR configuration is v1.2's lists, as data.

def test_hr_configuration_holds_the_v12_lists():
    assert HR.roles == list(get_args(PersonaRole))
    assert set(HR.document_types) == set(get_args(DocumentType))
    assert HR.recurring_document_types() == RECURRING_DOCUMENT_TYPES
    assert list(HR.event_types) == ["hire", "contract_change", "training", "appraisal",
                                    "medical_check", "absence", "termination"]
    required = {t: sorted(f for f, s in spec.fields.items() if s.required)
                for t, spec in HR.event_types.items()}
    assert required["appraisal"] == ["rating", "year"]
    assert required["training"] == ["course", "duration_days", "provider_id"]


@pytest.mark.parametrize("change, message", [
    ({"rules": {"first_event": "birthday"}}, "rules.first_event: 'birthday' is not an event type"),
    ({"roles": ["employee", "employee"]}, "roles must be unique"),
    ({"event_types": {"hire": {"fields": {"rating": {"format": "date", "values": ["x"]}}}}},
     r"values \(a closed list\) needs format 'text'"),
    ({"event_types": {"hire": {"fields": {"date": {"format": "date"}}}}},
     "field 'date' is common to every event"),
    ({"event_types": {"Hire": {}}}, "event type 'Hire' must be snake_case"),
    ({"case_number_pattern": "[0-9"}, "case_number_pattern is not a regular expression"),
])
def test_a_malformed_configuration_is_refused(change, message):
    config = {"name": "broken", "roles": ["employee"], "event_types": {"hire": {}},
              "document_types": {"letter": {}}, **change}
    with pytest.raises(ValidationError, match=message):
        DomainConfig.model_validate(config)


def test_a_second_configuration_cannot_take_an_existing_name():
    with pytest.raises(ValueError, match="already registered"):
        register_domain(DomainConfig.model_validate(
            {"name": "hr", "roles": ["x"], "event_types": {"a": {}}, "document_types": {"b": {}}}))


# GD-02 — a second domain, with its own timeline, through the same case model.

def test_a_claim_case_validates_with_its_own_event_types():
    case = _claim().build()
    assert case.domain == "insurance_claim"
    assert [e.type for e in case.events.values()] == [
        "policy_start", "claim_filed", "inspection", "repair", "payout", "claim_closed"]
    assert type(case.events["EVT-002"]).__name__ == "ClaimFiledEvent"
    assert case.events["EVT-002"].claimed_amount.amount == Money(amount="4200", currency="EUR").amount


def test_an_event_type_of_another_domain_is_refused():
    case = _claim()
    with pytest.raises(ValidationError, match="appraisal"):
        case.add_event(type="appraisal", date="2025-06-30", participant_ids=["P001"],
                       year=2025, rating="Meets expectations")


def test_a_value_outside_the_domain_list_is_refused():
    case = _claim()
    with pytest.raises(ValidationError) as error:
        case.add_event(type="claim_filed", date="2025-05-01", participant_ids=["P001"],
                       cause="Meteorite", claimed_amount=Money(amount="1", currency="EUR"))
    assert error.value.errors()[0]["loc"] == ("claim_filed", "cause")


def test_a_field_the_event_type_does_not_define_is_refused():
    case = _claim()
    with pytest.raises(ValidationError) as error:
        case.add_event(type="claim_closed", date="2025-04-15", participant_ids=["P001"],
                       reason="Paid in full")
    assert error.value.errors()[0]["loc"] == ("claim_closed", "reason")


def test_a_role_of_another_domain_is_refused():
    with pytest.raises(ValueError, match=r"Unknown role: 'employee'.*\(field role\)"):
        _claim().add_persona(name="Jan de Vries", role="employee")


def test_a_document_type_of_another_domain_is_refused():
    with pytest.raises(ValueError, match=r"Unknown document type: 'payslip'.*\(field type\)"):
        _claim().add_document(type="payslip", participant_ids=["P001"], metadata={
            "employee_id": "CL000123", "document_type": "payslip",
            "document_date": "2025-03-25", "confidential": True})


def test_the_case_number_follows_the_domain_pattern():
    with pytest.raises(ValueError, match=r"'100101' does not match the insurance_claim pattern"):
        CaseModel("100101", domain="insurance_claim").set_dossier(employee_number="100101")


def test_a_reference_field_must_point_at_a_persona_of_the_case():
    data = _claim().build().model_dump(mode="json")
    data["events"]["EVT-003"]["inspector_id"] = "P009"
    with pytest.raises(ValidationError, match=r"EVT-003 points at unknown inspector 'P009' \(field inspector_id\)"):
        Case.model_validate(data)


def test_an_unknown_domain_is_refused():
    with pytest.raises(ValueError, match="unknown domain 'legal'"):
        CaseModel("123", domain="legal")


# GD-03 — the domain's own rules between events.

def test_nothing_happens_before_the_policy_starts():
    data = _claim().build().model_dump(mode="json")
    data["events"]["EVT-002"]["date"] = "2023-12-01"
    with pytest.raises(ValidationError, match="happens before the policy_start on 2024-01-01"):
        Case.model_validate(data)


def test_a_repair_cannot_end_after_the_claim_is_closed():
    data = _claim().build().model_dump(mode="json")
    data["events"]["EVT-004"]["end_date"] = "2025-05-01"
    with pytest.raises(ValidationError, match=r"runs to 2025-05-01, after the claim_closed on 2025-04-15 \(field end_date\)"):
        Case.model_validate(data)


def test_a_repair_cannot_end_before_it_starts():
    data = _claim().build().model_dump(mode="json")
    data["events"]["EVT-004"]["end_date"] = "2025-03-01"
    with pytest.raises(ValidationError, match=r"Repair EVT-004 ends on 2025-03-01, before it starts"):
        Case.model_validate(data)


def test_two_closings_are_refused():
    data = _claim().build().model_dump(mode="json")
    data["events"]["EVT-005"] = {"id": "EVT-005", "type": "claim_closed", "date": "2025-04-10",
                                 "participant_ids": ["P001"]}
    with pytest.raises(ValidationError, match="at most one claim_closed event"):
        Case.model_validate(data)


# GD-04 — save, load and fill work for any domain.

def test_a_claim_case_survives_save_and_load(tmp_path):
    case = _claim().build()
    save_case(case, tmp_path)
    assert load_case(tmp_path) == case


def test_a_claim_letter_fills_from_the_case():
    case = _claim().build()
    text = ("Dear {{ personas.P001.name }}, for your claim of {{ events.EVT-002.claimed_amount }} "
            "({{ events.EVT-002.cause }}) we pay {{ events.EVT-005.amount }} on {{ events.EVT-005.date }}.")
    assert fill_text(case, text) == (
        "Dear Anna Jansen, for your claim of EUR 4.200 (Water damage) we pay EUR 3.850 on 10-04-2025.")


def test_a_reference_field_is_never_printed():
    case = _claim().build()
    assert "events.EVT-003.inspector_id" not in fact_paths(case)
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(case, "Inspected by {{ events.EVT-003.inspector_id }}")
    assert "internal ID" in error.value.problems["events.EVT-003.inspector_id"]


def test_a_case_read_from_json_with_a_role_of_another_domain_is_refused():
    data = _claim().build().model_dump(mode="json")
    data["personas"]["P001"]["role"] = "employee"
    with pytest.raises(ValidationError, match=r"Persona P001 has role 'employee', not one of .*\(field role\)"):
        Case.model_validate(data)


def test_a_case_read_from_json_with_a_document_type_of_another_domain_is_refused():
    data = _claim().build().model_dump(mode="json")
    data["documents"]["DOC-001"]["type"] = "payslip"
    data["documents"]["DOC-001"]["metadata"]["document_type"] = "payslip"
    with pytest.raises(ValidationError, match=r"DOC-001 has type 'payslip', not one of the insurance_claim document types"):
        Case.model_validate(data)
