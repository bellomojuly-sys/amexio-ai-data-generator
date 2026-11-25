"""Case model v2.2 — the rules the review of 25 Nov found missing.

One test for the accepted case and one for each refusal, per rule. A refusal
checks the field it names, so the test fails for the right reason when the
rule is removed.
"""

import datetime as dt
import random
from decimal import Decimal

import pytest
from pydantic import ValidationError

from case_model import Case, CaseModel, Money
from case_model.domain import FieldSpec
from case_model.facts import CannotGenerate, generate_fact
from case_model.fill import UnresolvedPlaceholders, fact_paths, fill_text, format_fact
from case_model.reference_dossier import build_reference_case

EUR = "EUR"


def _jan():
    """Jan de Vries at Acme Logistics B.V. with his manager M. Bakker; no job yet."""
    case = CaseModel("100101")
    case.set_dossier(employee_number="100101", folder_title="100101 Jan de Vries")
    acme = case.add_organisation(name="Acme Logistics B.V.", kind="employer")
    jan = case.add_persona(name="Jan de Vries", role="employee", organisation_id=acme)
    bakker = case.add_persona(name="M. Bakker", role="manager", organisation_id=acme)
    return case, acme, jan, bakker


def _employ(case, acme, jan, **changes):
    fields = dict(persona_id=jan, organisation_id=acme, position="Logistics Planner",
                  department="Operations", start_date=dt.date(2021, 3, 1),
                  contract_type="Permanent", hours=40,
                  salary=Money(amount=Decimal("4350.00"), currency=EUR))
    return case.add_employment(**{**fields, **changes})


def _hired(**employment):
    case, acme, jan, bakker = _jan()
    _employ(case, acme, jan, **employment)
    case.add_event(type="hire", date=dt.date(2021, 3, 1), participant_ids=[jan])
    return case, acme, jan, bakker


@pytest.fixture
def reference():
    return build_reference_case()


# 1 — fill_text refuses a whole record (it would print internal IDs).

def test_a_field_of_a_persona_fills(reference):
    assert fill_text(reference, "{{ personas.P001.name }}") == "Jan de Vries"


@pytest.mark.parametrize("path", ["personas.P001", "dossier", "events.EVT-001", "employments.P001"])
def test_a_whole_record_is_refused_not_printed(reference, path):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(reference, f"Dear {{{{ {path} }}}}")
    assert "several values" in error.value.problems[path]


def test_an_amount_is_one_fact_and_fills(reference):
    assert fill_text(reference, "{{ employments.P001.salary }}") == "EUR 4.350"


# 2 — the case number and the dossier's employee number are one number.

def test_case_number_equal_to_the_employee_number_builds():
    case, *_ = _jan()
    assert case.build().case_number == "100101"


def test_set_dossier_refuses_another_employee_number():
    case = CaseModel("100101")
    with pytest.raises(ValueError, match="field employee_number"):
        case.set_dossier(employee_number="100102")
    assert case.dossier is None


def test_a_loaded_case_with_two_numbers_is_refused():
    data = _jan()[0].build().model_dump()
    data["case_number"] = "abc"
    with pytest.raises(ValidationError, match="field case_number"):
        Case.model_validate(data)


# 3 — hours and salaries are above zero; one employment per persona.

def test_a_job_with_hours_and_a_salary_builds():
    case, *_ = _hired()
    assert case.build().employments[0].hours == 40


@pytest.mark.parametrize("change, field", [
    ({"hours": 0}, "hours"),
    ({"hours": -40}, "hours"),
    ({"salary": Money(amount=Decimal("0"), currency=EUR)}, "salary"),
    ({"salary": Money(amount=Decimal("-100"), currency=EUR)}, "salary"),
])
def test_a_job_without_hours_or_pay_is_refused(change, field):
    case, acme, jan, _ = _jan()
    with pytest.raises(ValidationError) as error:
        _employ(case, acme, jan, **change)
    assert error.value.errors()[0]["loc"] == (field,)
    assert case.employments == []


def test_a_second_employment_for_the_same_persona_is_refused():
    case, acme, jan, _ = _hired()
    with pytest.raises(ValueError, match="field persona_id"):
        _employ(case, acme, jan, hours=20)
    assert len(case.employments) == 1


def test_a_loaded_case_with_two_employments_for_one_persona_is_refused():
    data = _hired()[0].build().model_dump()
    data["employments"].append(dict(data["employments"][0]))
    with pytest.raises(ValidationError, match="field employments"):
        Case.model_validate(data)


def test_every_fact_path_resolves_with_one_employment_per_persona(reference):
    for path in fact_paths(reference):
        fill_text(reference, f"{{{{ {path} }}}}")


def test_a_contract_change_with_a_raise_and_new_hours_builds():
    case, acme, jan, bakker = _hired()
    case.add_event(type="contract_change", date=dt.date(2023, 1, 1), participant_ids=[jan, bakker],
                   reason="promotion", new_hours=36,
                   new_salary=Money(amount=Decimal("4800.00"), currency=EUR))
    assert case.build().events["EVT-002"].new_hours == 36


@pytest.mark.parametrize("change, field", [
    ({"new_hours": 0}, "new_hours"),
    ({"new_hours": -5}, "new_hours"),
    ({"new_salary": Money(amount=Decimal("-100"), currency=EUR)}, "new_salary"),
    ({"new_salary": Money(amount=Decimal("0"), currency=EUR)}, "new_salary"),
])
def test_a_contract_change_to_zero_or_less_is_refused(change, field):
    case, acme, jan, bakker = _hired()
    with pytest.raises(ValidationError, match=field):
        case.add_event(type="contract_change", date=dt.date(2023, 1, 1),
                       participant_ids=[jan, bakker], reason="promotion", **change)
    assert len(case.events) == 1


# 4 — an integer field takes whole bounds.

def test_an_integer_field_with_whole_bounds_is_accepted():
    assert FieldSpec(format="integer", min=1, max=3).min == 1


@pytest.mark.parametrize("bounds", [{"min": 1.5, "max": 3}, {"min": 1, "max": 2.5}, {"gt": 0.5}])
def test_an_integer_field_with_a_decimal_bound_is_refused(bounds):
    with pytest.raises(ValidationError, match="whole number"):
        FieldSpec(format="integer", **bounds)


# 5 — a number fact is generated inside its bounds, or not at all.

def test_a_number_fact_stays_inside_its_bounds():
    spec = FieldSpec(format="number", min=1.234, max=1.256)
    values = {generate_fact("rate", spec, random.Random(seed)) for seed in range(200)}
    assert values and all(1.234 <= v <= 1.256 for v in values)


def test_a_number_fact_with_no_hundredth_in_its_bounds_names_the_field():
    with pytest.raises(CannotGenerate, match="field rate"):
        generate_fact("rate", FieldSpec(format="number", min=1.234, max=1.236), random.Random(1))


# 6 — a money fact needs a whole euro in its bounds.

def test_a_money_fact_is_a_whole_euro_inside_its_bounds():
    value = generate_fact("premium", FieldSpec(format="money", min=10.2, max=11.8), random.Random(1))
    assert value.amount == Decimal("11.00")


def test_a_money_fact_without_a_whole_euro_in_its_bounds_names_the_field():
    with pytest.raises(CannotGenerate, match="field premium"):
        generate_fact("premium", FieldSpec(format="money", min=10.2, max=10.8), random.Random(1))


# 7 — a termination's notice date comes on or before the last working day.

def test_a_notice_before_the_last_working_day_builds():
    case, acme, jan, bakker = _hired()
    case.add_event(type="termination", date=dt.date(2024, 1, 31), participant_ids=[jan, bakker],
                   reason="Resignation", notice_date=dt.date(2023, 12, 31))
    assert case.build().events["EVT-002"].notice_date == dt.date(2023, 12, 31)


@pytest.mark.parametrize("notice, message", [
    (dt.date(2025, 6, 1), "after the event itself"),
    (dt.date(2020, 1, 1), "before the hire"),
])
def test_a_notice_outside_the_story_is_refused(notice, message):
    case, acme, jan, bakker = _hired()
    case.add_event(type="termination", date=dt.date(2024, 1, 31), participant_ids=[jan, bakker],
                   reason="Resignation", notice_date=notice)
    with pytest.raises(ValidationError, match=f"{message}.*field notice_date"):
        case.build()


def test_not_after_event_is_refused_on_a_case_fact():
    with pytest.raises(ValidationError, match="not_after_event belongs on an event"):
        from case_model import DomainConfig
        DomainConfig.model_validate({
            "name": "broken_notice", "roles": ["x"], "event_types": {"hire": {}},
            "document_types": {"letter": {}},
            "case_facts": {"n": {"format": "date", "not_after_event": True}}})


# 8 — a format that does not fit the value is a problem of its placeholder.

@pytest.mark.parametrize("value, fmt, printed", [
    (dt.date(2021, 3, 1), "date", "01-03-2021"),
    (dt.date(2021, 3, 1), "monthYear", "March 2021"),
    (Money(amount=Decimal("4350"), currency=EUR), "eurGrouped", "EUR 4.350"),
    (2, "days", "2 days"),
    (dt.date(2021, 3, 1), "text", "2021-03-01"),
])
def test_a_format_that_fits_prints(value, fmt, printed):
    assert format_fact(value, fmt) == printed


@pytest.mark.parametrize("value, fmt", [
    (dt.date(2021, 3, 1), "eurGrouped"),
    (dt.date(2021, 3, 1), "days"),
    ("Jan de Vries", "date"),
    (Money(amount=Decimal("4350"), currency=EUR), "monthYear"),
    (dt.date(2021, 3, 1), "dateRange"),
])
def test_a_format_that_does_not_fit_is_refused(value, fmt):
    with pytest.raises(ValueError, match=fmt):
        format_fact(value, fmt)


def test_fill_text_names_the_placeholder_with_the_wrong_format(reference):
    path = "employments.P001.start_date"
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(reference, f"{{{{ {path} }}}}", {path: "eurGrouped"})
    assert "needs a number" in error.value.problems[path]


# 9 — a missing reference names its field, never a bare KeyError.

def test_an_event_without_participants_names_the_field():
    case, *_ = _hired()
    with pytest.raises(ValidationError, match="participant_ids"):
        case.add_event(type="training", date=dt.date(2022, 5, 1), course="Forklift safety",
                       duration_days=2, provider_id="ORG-01")
    assert len(case.events) == 1


def test_an_employment_without_a_persona_names_the_field():
    case, acme, jan, _ = _jan()
    with pytest.raises(ValidationError, match="persona_id"):
        case.add_employment(organisation_id=acme, position="Logistics Planner",
                            department="Operations", start_date=dt.date(2021, 3, 1),
                            contract_type="Permanent", hours=40,
                            salary=Money(amount=Decimal("4350.00"), currency=EUR))
    assert case.employments == []


def test_a_document_without_participants_names_the_field():
    case, *_ = _hired()
    with pytest.raises(ValidationError, match="participant_ids"):
        case.add_document(type="payslip", metadata={
            "employee_id": "100101", "document_type": "payslip",
            "document_date": dt.date(2021, 3, 31), "confidential": True})
    assert case.documents == {}
