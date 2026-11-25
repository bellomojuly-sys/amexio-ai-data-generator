"""Case model v2.1 — case facts, domain metadata, employment and organisation kinds
from the domain configuration, and the generator of "fact" values."""

import datetime as dt
import random
from decimal import Decimal

import pytest
from pydantic import ValidationError
from case_model import Case, CaseModel, DomainConfig, Money, get_fact, register_domain
from case_model.facts import CannotGenerate, generate_fact, generate_facts
from case_model.fill import fact_paths, fill_text
from case_model.domain import FieldSpec
from case_model.storage import load_case, save_case

HOME = register_domain(DomainConfig.model_validate({
    "name": "home_insurance",
    "case_number_pattern": "HP[0-9]{6}",
    "roles": ["policyholder", "adjuster"],
    "organisation_kinds": ["insurer", "repair_company"],
    "event_types": {"policy_start": {}, "claim_filed": {"fields": {
        "claimed_amount": {"format": "money", "required": True, "currency": "EUR", "min": 1}}}},
    "document_types": {"policy": {}, "claim_form": {}},
    "case_facts": {
        "policy_number": {"format": "text", "required": True},
        "insured_sum": {"format": "money", "required": True, "currency": "EUR",
                        "min": 100000, "max": 450000},
        "deductible": {"format": "integer", "min": 0, "max": 1000},
        "risk_class": {"format": "text", "values": ["Low", "Medium", "High"]},
        "policy_since": {"format": "date", "min": "2015-01-01", "max": "2024-12-31"},
    },
    "metadata_fields": {"claim_reference": {"format": "text", "required": True}},
    "rules": {"first_event": "policy_start"},
}))

EUR = lambda n: Money(amount=n, currency="EUR")


def _home(**facts):
    case = CaseModel("HP000777", domain="home_insurance")
    case.set_dossier(employee_number="HP000777", folder_title="Home policy HP000777")
    case.set_facts(**({"policy_number": "HP-2019-0777", "insured_sum": EUR("320000.00"),
                       "risk_class": "Medium"} | facts))
    insurer = case.add_organisation(name="Delta Verzekeringen (fictional)", kind="insurer")
    holder = case.add_persona(name="Anna Jansen", role="policyholder", organisation_id=None)
    start = case.add_event(type="policy_start", date="2019-05-01", participant_ids=[holder])
    case.add_document(type="policy", event_id=start, participant_ids=[holder], metadata={
        "employee_id": "HP000777", "document_type": "policy", "document_date": "2019-05-01",
        "confidential": True, "claim_reference": "none"})
    return case


# Case facts: stored once, typed, read by every document.

def test_case_facts_are_kept_typed_and_read_by_path(tmp_path):
    case = _home().build()
    assert case.facts.insured_sum.amount == Decimal("320000.00")
    assert get_fact(case, "facts.policy_number") == "HP-2019-0777"
    save_case(case, tmp_path)
    assert load_case(tmp_path) == case


def test_a_letter_fills_from_the_case_facts():
    case = _home().build()
    assert "facts.insured_sum" in fact_paths(case)
    assert fill_text(case, "Policy {{ facts.policy_number }} insures {{ facts.insured_sum }}.") == \
        "Policy HP-2019-0777 insures EUR 320.000."


def test_a_missing_required_fact_is_refused():
    data = _home().build().model_dump(mode="json")
    del data["facts"]["policy_number"]
    with pytest.raises(ValidationError) as error:
        Case.model_validate(data)
    assert error.value.errors()[0]["loc"][-1] == "policy_number"


def test_a_case_without_its_required_facts_is_refused():
    data = _home().build().model_dump(mode="json")
    del data["facts"]
    with pytest.raises(ValidationError, match=r"misses the case facts policy_number, insured_sum \(field facts\)"):
        Case.model_validate(data)


def test_a_fact_the_domain_does_not_declare_is_refused():
    with pytest.raises(ValidationError) as error:
        _home(bonus=EUR("500"))
    assert error.value.errors()[0]["loc"] == ("bonus",)


@pytest.mark.parametrize("fact, value, message", [
    ("insured_sum", EUR("50000"), "below the minimum"),
    ("insured_sum", Money(amount="320000", currency="USD"), "currency USD is not EUR"),
    ("deductible", 5000, "above the maximum"),
    ("risk_class", "Extreme", "Low"),
    ("policy_since", "2030-01-01", "above the maximum"),
])
def test_a_fact_outside_its_rule_is_refused(fact, value, message):
    with pytest.raises(ValidationError, match=message):
        _home(**{fact: value})


def test_hr_declares_no_case_facts():
    case = CaseModel("100101")
    with pytest.raises(ValueError, match=r"Domain hr declares no case facts \(field facts\)"):
        case.set_facts(bonus=EUR("500"))


# Metadata, employment and organisation kinds from the configuration.

def test_the_domain_metadata_field_is_required():
    with pytest.raises(ValidationError) as error:
        _home().add_document(type="claim_form", event_id="EVT-001", participant_ids=["P001"], metadata={
            "employee_id": "HP000777", "document_type": "claim_form",
            "document_date": "2019-05-01", "confidential": True})
    assert error.value.errors()[0]["loc"] == ("claim_reference",)


def test_an_unknown_metadata_key_is_refused_in_hr_too():
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101")
    jan = case.add_persona(name="Jan de Vries", role="employee")
    with pytest.raises(ValidationError) as error:
        case.add_document(type="payslip", participant_ids=[jan], metadata={
            "employee_id": "100101", "document_type": "payslip", "document_date": "2026-09-25",
            "confidential": True, "claim_reference": "x"})
    assert error.value.errors()[0]["loc"] == ("claim_reference",)


def test_employment_only_where_the_domain_uses_it():
    case = _home()
    with pytest.raises(ValueError, match=r"Domain home_insurance has no employment \(field employments\)"):
        case.add_employment(persona_id="P001", organisation_id="ORG-01", position="x",
                            department="x", start_date="2019-05-01", contract_type="Permanent",
                            hours=40, salary=EUR("1"))


def test_a_case_read_from_json_with_employment_is_refused():
    data = _home().build().model_dump(mode="json")
    data["employments"] = [{"persona_id": "P001", "organisation_id": "ORG-01", "position": "x",
                            "department": "x", "start_date": "2019-05-01",
                            "contract_type": "Permanent", "hours": 40,
                            "salary": {"amount": "1.00", "currency": "EUR"}}]
    with pytest.raises(ValidationError, match=r"has no employment; remove it \(field employments\)"):
        Case.model_validate(data)


def test_an_organisation_kind_outside_the_list_is_refused():
    with pytest.raises(ValueError, match=r"Unknown organisation kind: 'bank'.*\(field kind\)"):
        _home().add_organisation(name="ING (fictional)", kind="bank")


def test_hr_files_do_not_change(tmp_path):
    from case_model.reference_dossier import build_reference_case
    case = build_reference_case()
    assert case.facts is None
    save_case(case, tmp_path)
    assert "facts" not in (tmp_path / "case.json").read_text(encoding="utf-8")


# The generator of "fact" values.

def test_generated_facts_follow_their_rules():
    for seed in range(50):
        facts = generate_facts(HOME, random.Random(seed), {"policy_number": f"HP-{seed}"})
        assert 100000 <= facts.insured_sum.amount <= 450000
        assert facts.insured_sum.currency == "EUR"
        assert 0 <= facts.deductible <= 1000
        assert facts.risk_class in ("Low", "Medium", "High")
        assert dt.date(2015, 1, 1) <= facts.policy_since <= dt.date(2024, 12, 31)


def test_the_same_seed_gives_the_same_facts():
    given = {"policy_number": "HP-1"}
    assert generate_facts(HOME, random.Random(7), given) == generate_facts(HOME, random.Random(7), given)


def test_a_given_value_wins_and_is_checked():
    facts = generate_facts(HOME, random.Random(1), {"policy_number": "HP-1", "risk_class": "High"})
    assert facts.risk_class == "High"
    with pytest.raises(ValidationError, match="below the minimum"):
        generate_facts(HOME, random.Random(1), {"policy_number": "HP-1", "insured_sum": EUR("1")})


def test_required_free_text_is_never_generated():
    with pytest.raises(CannotGenerate, match=r"policy_number: free text is written by the LLM"):
        generate_facts(HOME, random.Random(1))


def test_a_rule_without_bounds_cannot_generate():
    with pytest.raises(CannotGenerate, match="needs both min and max"):
        generate_fact("bonus", FieldSpec(format="money"), random.Random(1))


# A malformed v2.1 configuration is refused.

@pytest.mark.parametrize("change, message", [
    ({"case_facts": {"x": {"format": "money", "min": 10, "max": 1}}}, "min must not be above max"),
    ({"case_facts": {"x": {"format": "text", "currency": "EUR"}}}, "currency needs format 'money'"),
    ({"case_facts": {"x": {"format": "date", "min": 5}}}, "min/max of a date field must be ISO dates"),
    ({"case_facts": {"x": {"format": "persona"}}}, "a reference or a period end belongs on an event"),
    ({"metadata_fields": {"employee_id": {"format": "text"}}}, "cannot redefine AMEXIO's five attributes"),
    ({"rules": {"first_event": "hire", "first_event_starts_employment": True}}, "needs uses_employment"),
])
def test_a_malformed_v21_configuration_is_refused(change, message):
    config = {"name": "broken", "roles": ["x"], "event_types": {"hire": {}},
              "document_types": {"letter": {}}, **change}
    with pytest.raises(ValidationError, match=message):
        DomainConfig.model_validate(config)


def test_a_case_read_from_json_with_an_organisation_kind_outside_the_list_is_refused():
    data = _home().build().model_dump(mode="json")
    data["organisations"]["ORG-01"]["kind"] = "bank"
    with pytest.raises(ValidationError, match=r"Organisation ORG-01 has kind 'bank', not one of insurer, repair_company \(field kind\)"):
        Case.model_validate(data)
