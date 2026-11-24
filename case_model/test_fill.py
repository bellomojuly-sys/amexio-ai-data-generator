"""M04 — every placeholder resolves from the case, or the run stops (AX-023 … AX-025)."""

import datetime as dt
from decimal import Decimal

import pytest
from case_model import Money
from case_model.fill import UnresolvedPlaceholders, fact_paths, fill_text, format_fact
from case_model.lookup import get_fact
from case_model.reference_dossier import build_reference_case


@pytest.fixture
def jan():
    return build_reference_case()


# AX-023 — every placeholder the case offers resolves.

def test_every_fact_path_of_the_reference_case_resolves(jan):
    paths = fact_paths(jan)
    assert "personas.P001.name" in paths and "employments.P001.salary" in paths
    text = " | ".join(f"{{{{ {p} }}}}" for p in paths)
    filled = fill_text(jan, text)
    assert "{{" not in filled
    assert len(filled.split(" | ")) == len(paths)


def test_fact_paths_never_offer_an_internal_id(jan):
    for path in fact_paths(jan):
        assert path.rsplit(".", 1)[-1] not in {"id", "persona_id", "organisation_id",
                                               "provider_id", "event_id", "signed_by"}


def test_a_letter_fills_with_the_reference_facts(jan):
    text = ("Dear {{ personas.P001.name }}, from {{employments.P001.start_date}} your "
            "salary is {{ employments.P001.salary }} for {{ employments.P001.hours }} hours.")
    assert fill_text(jan, text) == (
        "Dear Jan de Vries, from 01-03-2021 your salary is EUR 4.350 for 40 hours.")


# AX-024 — a placeholder that does not resolve stops the run; never a silent blank.

def test_an_unknown_path_is_refused_and_named(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "Dear {{ personas.P009.name }}")
    assert list(error.value.problems) == ["personas.P009.name"]
    assert "no persona 'P009'" in error.value.problems["personas.P009.name"]


def test_a_path_without_a_value_is_refused(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "Born on {{ personas.P001.date_of_birth }}")
    assert error.value.problems == {"personas.P001.date_of_birth": "the case holds no value for it"}


def test_a_path_to_several_values_is_refused(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "{{ events.EVT-001.participant_ids }}")
    assert "several values" in error.value.problems["events.EVT-001.participant_ids"]


def test_an_internal_id_is_refused(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "Signed by {{ personas.P002.id }}")
    assert "internal ID" in error.value.problems["personas.P002.id"]


def test_a_malformed_placeholder_is_refused(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "Dear {{ personas.P001.name }, welcome")
    assert list(error.value.problems) == ["(malformed)"]


def test_all_problems_are_named_at_once(jan):
    with pytest.raises(UnresolvedPlaceholders) as error:
        fill_text(jan, "{{ personas.P009.name }} {{ personas.P001.name }} {{ dossier.nope }}")
    assert set(error.value.problems) == {"personas.P009.name", "dossier.nope"}


# AX-025 — format when the text is filled; the stored values stay ISO and numeric.

@pytest.mark.parametrize("value, fmt, printed", [
    (dt.date(2026, 4, 14), None, "14-04-2026"),
    (dt.date(2026, 9, 25), "monthYear", "September 2026"),
    (Money(amount="4350.00", currency="EUR"), None, "EUR 4.350"),
    (Money(amount="4350.00", currency="EUR"), "eurPlain", "EUR 4350"),
    (Decimal("1250.50"), "eurGrouped", "EUR 1.251"),
    (2, "days", "2 days"),
    (40.0, None, "40"),
    (32.5, "number", "32.5"),
    (1, "days", "1 day"),
    ("Exceeds expectations", None, "Exceeds expectations"),
])
def test_facts_print_in_amexios_formats(value, fmt, printed):
    assert format_fact(value, fmt) == printed


def test_an_unknown_format_is_refused():
    with pytest.raises(ValueError, match="unknown format 'currency'"):
        format_fact(Decimal("4350"), "currency")


def test_a_template_format_applies_to_its_path(jan):
    text = "Gross {{ employments.P001.salary }}"
    assert fill_text(jan, text, {"employments.P001.salary": "eurPlain"}) == "Gross EUR 4350"


def test_filling_never_changes_the_stored_facts(jan):
    before = jan.model_dump()
    fill_text(jan, "{{ employments.P001.start_date }} {{ employments.P001.salary }}")
    assert jan.model_dump() == before
    assert get_fact(jan, "employments.P001.start_date") == dt.date(2021, 3, 1)
    assert get_fact(jan, "employments.P001.salary.amount") == Decimal("4350.00")
