from decimal import Decimal

import pytest
from case_model.format_rules import (
    ID_PATTERNS,
    Money,
    example_id,
    is_valid_employee_number,
    is_valid_id,
    next_id,
    reject_caller_id,
    validate_id,
)


# AX-011 — one ID pattern per type.

def test_the_four_types_have_a_pattern():
    # The insurance-era "vehicle" type is gone: the domain is HR.
    assert set(ID_PATTERNS) == {"persona", "organisation", "event", "document"}

@pytest.mark.parametrize("kind, value", [
    ("persona", "P001"),
    ("organisation", "ORG-01"),
    ("event", "EVT-001"),
    ("document", "DOC-001"),
])
def test_well_formed_id_is_accepted(kind, value):
    assert is_valid_id(kind, value)
    assert validate_id(kind, value) == value

@pytest.mark.parametrize("kind, value", [
    ("persona", "P1"),
    ("persona", "P0001"),
    ("persona", "p001"),
    ("persona", "PERS-001"),
    ("organisation", "ORG-1"),
    ("organisation", "ORG-001"),
    ("organisation", "ORG01"),
    # AX-011a — a trailing newline and non-ASCII digits are not an ID.
    ("persona", "P001\n"),
    ("persona", "P\u0660\u0660\u0661"),
    ("event", "EVT-001\n"),
    ("event", "EVT-01"),
    ("event", "EVT001"),
    ("document", "DOC-1"),
    ("document", ""),
])
def test_wrong_pattern_is_refused(kind, value):
    assert not is_valid_id(kind, value)
    with pytest.raises(ValueError):
        validate_id(kind, value)

def test_a_non_string_is_not_an_id():
    assert not is_valid_id("persona", 1)
    assert not is_valid_id("persona", None)

def test_unknown_type_is_refused():
    with pytest.raises(ValueError):
        is_valid_id("spaceship", "S001")

def test_example_id_is_the_first_of_the_type():
    assert example_id("persona") == "P001"
    assert example_id("organisation") == "ORG-01"
    assert example_id("event") == "EVT-001"

def test_next_id_counts_up_per_type():
    assert next_id("persona", {}) == "P001"
    assert next_id("persona", {"P001": object(), "P002": object()}) == "P003"
    assert next_id("organisation", {}) == "ORG-01"
    assert next_id("event", {"EVT-001": object()}) == "EVT-002"

def test_employee_number_is_six_digits():
    assert is_valid_employee_number("100101")
    assert not is_valid_employee_number("123")
    assert not is_valid_employee_number("1001011")
    assert not is_valid_employee_number("10010a")
    # AX-011a
    assert not is_valid_employee_number("100101\n")
    assert not is_valid_employee_number("\u0661\u0660\u0660\u0661\u0660\u0661")


# AX-012 — reject input that already carries an ID.

def test_reject_caller_id_passes_clean_input():
    reject_caller_id({"name": "Jan de Vries"})

def test_reject_caller_id_refuses_an_id():
    with pytest.raises(ValueError):
        reject_caller_id({"id": "P001", "name": "Jan de Vries"})


# AX-014 — an amount is a number plus a currency.

def test_money_takes_a_number_and_a_currency():
    money = Money(amount=3240.00, currency="EUR")
    assert money.amount == Decimal("3240")
    assert money.currency == "EUR"

def test_money_accepts_a_plain_numeric_string():
    assert Money(amount="3240.00", currency="EUR").currency == "EUR"

def test_formatted_amount_text_is_refused():
    with pytest.raises(ValueError):
        Money(amount="€3,240.00", currency="EUR")

def test_thousands_separator_is_refused():
    with pytest.raises(ValueError):
        Money(amount="3,240.00", currency="EUR")

def test_currency_must_be_an_iso_code():
    with pytest.raises(ValueError):
        Money(amount=3240.00, currency="euro")
    with pytest.raises(ValueError):
        Money(amount=3240.00, currency="€")
