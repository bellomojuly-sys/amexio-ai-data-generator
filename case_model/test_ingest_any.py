"""GD-05 (first part) — ingest for any domain: JSON without IDs in, validated cases out."""

import copy

import pytest
from case_model import DomainConfig, register_domain
from case_model.ingest_any import ingest_cases
from case_model.storage import load_case

PERMIT = register_domain(DomainConfig.model_validate({
    "name": "building_permit",
    "description": "A building-permit file at a municipality.",
    "case_number_pattern": "BP-[0-9]{5}",
    "roles": ["applicant", "case_officer", "inspector"],
    "organisation_kinds": ["municipality", "architect_firm"],
    "event_types": {
        "application": {"fields": {
            "work": {"format": "text", "required": True,
                     "values": ["Extension", "Dormer", "Garage", "Demolition"]}}},
        "site_visit": {"fields": {
            "inspector_id": {"format": "persona", "required": True, "label": "inspector"},
            "finding": {"format": "text", "required": True}}},
        "decision": {"fields": {
            "outcome": {"format": "text", "required": True, "values": ["Granted", "Refused"]},
            "decided_by": {"format": "organisation", "required": True, "label": "municipality"}}},
    },
    "document_types": {"application_form": {}, "visit_report": {}, "decision_letter": {}},
    "case_facts": {
        "permit_number": {"format": "text", "required": True},
        "fee": {"format": "money", "required": True, "currency": "EUR", "min": 150, "max": 2500},
    },
    "rules": {"first_event": "application", "last_event": "decision"},
}))

CASE = {
    "dossier": {"folder_title": "Permit Bakker, Dorpsstraat 12"},
    "facts": {"permit_number": "OLO-2025-1187"},
    "organisations": {"town": {"name": "Gemeente Eindhoven (fictional)", "kind": "municipality"},
                      "studio": {"name": "Studio Noord (fictional)", "kind": "architect_firm"}},
    "personas": {"owner": {"name": "Kees Bakker", "role": "applicant"},
                 "officer": {"name": "L. Smit", "role": "case_officer", "organisation": "town"},
                 "visitor": {"name": "T. Vos", "role": "inspector", "organisation": "town"}},
    "events": [
        {"key": "decision", "type": "decision", "date": "2025-06-20", "participants": ["owner", "officer"],
         "outcome": "Granted", "decided_by": "town", "signed_by": "officer"},
        {"key": "apply", "type": "application", "date": "2025-04-02", "participants": ["owner"],
         "work": "Dormer"},
        {"key": "visit", "type": "site_visit", "date": "2025-05-14", "participants": ["owner", "visitor"],
         "inspector_id": "visitor", "finding": "Roof structure fits the drawings."},
    ],
    "documents": [
        {"type": "application_form", "event": "apply", "participants": ["owner"],
         "metadata": {"confidential": False, "tags": ["permit"]}},
        {"type": "decision_letter", "event": "decision", "participants": ["owner", "officer"],
         "metadata": {"confidential": False}},
    ],
}


def _data(*changes):
    case = copy.deepcopy(CASE)
    for change in changes:
        change(case)
    return {"cases": [case]}


def _ingest(data, **options):
    return ingest_cases("building_permit", data, first_number=1, number_format="BP-{:05d}", **options)


def test_a_permit_case_gets_ids_numbers_and_a_dated_timeline():
    (case,), corrections = _ingest(_data())
    assert case.case_number == "BP-00001" and case.domain == "building_permit"
    assert [(k, e.type) for k, e in case.events.items()] == [
        ("EVT-001", "application"), ("EVT-002", "site_visit"), ("EVT-003", "decision")]
    assert case.personas["P003"].name == "T. Vos"
    assert case.events["EVT-002"].inspector_id == "P003"
    assert case.events["EVT-003"].decided_by == "ORG-01" and case.events["EVT-003"].signed_by == "P002"
    assert corrections == []


def test_code_fills_the_document_metadata_the_case_decides():
    (case,), _ = _ingest(_data())
    letter = case.documents["DOC-002"]
    assert letter.event_id == "EVT-003"
    assert letter.metadata.employee_id == "BP-00001"
    assert letter.metadata.document_type == "decision_letter"
    assert str(letter.metadata.document_date) == "2025-06-20"


def test_missing_facts_are_generated_by_their_rule_and_given_ones_kept():
    (case,), _ = _ingest(_data())
    assert case.facts.permit_number == "OLO-2025-1187"
    assert 150 <= case.facts.fee.amount <= 2500 and case.facts.fee.currency == "EUR"
    (again,), _ = _ingest(_data())
    assert again.facts == case.facts                       # same seed, same facts
    (other,), _ = _ingest(_data(), seed=1)
    assert other.facts.permit_number == case.facts.permit_number


def test_values_written_differently_are_corrected_and_recorded():
    def lower(case):
        case["events"][1]["work"] = "  dormer "
        case["personas"]["owner"]["role"] = "Applicant"
    (case,), corrections = _ingest(_data(lower))
    assert case.events["EVT-001"].work == "Dormer"
    assert [c.path for c in corrections] == ["personas.owner.role", "events[1].work"]


def test_several_cases_are_numbered_in_order(tmp_path):
    data = _data()
    data["cases"].append(copy.deepcopy(CASE))
    cases, _ = ingest_cases("building_permit", data, first_number=41, number_format="BP-{:05d}",
                            out_dir=tmp_path)
    assert [c.case_number for c in cases] == ["BP-00041", "BP-00042"]
    assert load_case(tmp_path / "BP-00042") == cases[1]


@pytest.mark.parametrize("change, message", [
    (lambda c: c["personas"]["owner"].update(id="P009"), "IDs are assigned by the case model"),
    (lambda c: c["events"][0].update(id="EVT-009"), "IDs are assigned by the case model"),
    (lambda c: c["events"][2].update(participants=["owner", "ghost"]),
     r"events\[2\].participants: no persona with key 'ghost'"),
    (lambda c: c["personas"]["officer"].update(organisation="city_hall"),
     r"personas.officer.organisation: no organisation with key 'city_hall'"),
    (lambda c: c["events"][2].update(inspector_id="owner_x"),
     r"events\[2\].inspector_id: no persona with key 'owner_x'"),
    (lambda c: c["documents"][0].update(event="visit_2"), r"documents\[0\].event: no event with key 'visit_2'"),
    (lambda c: c["events"][2].update(key="apply"), r"key 'apply' is used twice"),
    (lambda c: c["personas"].update(p001={"name": "X", "role": "applicant"}), "must not look like an ID"),
    (lambda c: c["events"].append({"type": "appraisal", "date": "2025-06-01"}),
     r"'appraisal' is not an event type of building_permit"),
    (lambda c: c["events"][1].update(work="Swimming pool"), r"'Swimming pool' is not one of Extension"),
    (lambda c: c["events"][1].update(budget=50000), "budget"),
    (lambda c: c["facts"].pop("permit_number"), "permit_number: free text is written by the LLM"),
    (lambda c: c.update(notes="x"), "notes"),
])
def test_a_bad_input_is_refused_naming_the_place(change, message):
    with pytest.raises(ValueError, match=message):
        _ingest(_data(change))


def test_a_refusal_names_the_case():
    with pytest.raises(ValueError, match=r"cases\[0\] \(BP-00001\)"):
        _ingest(_data(lambda c: c["events"][1].update(work="Swimming pool")))


def test_a_number_format_outside_the_pattern_is_refused():
    with pytest.raises(ValueError, match=r"'000001' .* does not match the building_permit pattern"):
        ingest_cases("building_permit", _data(), number_format="{:06d}")


def test_nothing_is_saved_when_one_case_is_refused(tmp_path):
    data = _data()
    data["cases"].append(_data(lambda c: c["events"][1].update(work="Pool"))["cases"][0])
    with pytest.raises(ValueError):
        _ingest(data, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_story_rules_of_the_domain_still_hold():
    with pytest.raises(ValueError, match="happens before the application"):
        _ingest(_data(lambda c: c["events"][2].update(date="2025-03-01")))


def test_an_hr_case_goes_through_the_same_ingest():
    (case,), _ = ingest_cases("hr", {"cases": [{
        "organisations": {"acme": {"name": "Acme Logistics B.V. (fictional)", "kind": "employer"}},
        "personas": {"jan": {"name": "Jan de Vries", "role": "employee", "organisation": "acme"},
                     "boss": {"name": "M. Bakker", "role": "manager", "organisation": "acme"}},
        "events": [{"type": "hire", "date": "2021-03-01", "participants": ["jan"]},
                   {"type": "appraisal", "date": "2025-06-30", "participants": ["jan", "boss"],
                    "year": 2025, "rating": "meets expectations", "signed_by": "boss"}],
    }]}, first_number=100101)
    assert case.case_number == "100101"
    assert case.events["EVT-002"].rating == "Meets expectations"
