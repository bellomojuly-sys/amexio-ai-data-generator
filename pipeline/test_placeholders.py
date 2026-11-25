"""The placeholder check (contract v1.1 §7, rule 3; Robin with Valentin): every
``{{ path }}`` resolves with ``get_fact`` to one fact of the case, and no name,
date, amount or number is typed out. One test per failure, then the check in
``complete_as`` for Part 2 and Part 3: one retry with the problem named, then
an ``LLMError`` (and a ``ChainError``) naming the field.

The case is AMEXIO's 100101: P001 Jan de Vries, P002 "M. Bakker (fictional)",
P003 "Occupational physician (fictional)", ORG-01 "Acme Logistics B.V.
(fictional)", ORG-02 "Training Academy (fictional)", ORG-03 "Occupational
health service (fictional)"."""

import copy
import json
from pathlib import Path

import pytest

from case_model.ingest import EmployeeIn, ingest_employees
from pipeline import fake_answers
from pipeline.chain import ChainError, run_chain
from pipeline.cm_id import cm_id
from pipeline.contracts import EventContentIn, RunRequest
from pipeline.document_plan import plan_case
from pipeline.generation import request_of, write_document_text, write_event_content
from pipeline.llm import FakeLLM, LLMError
from pipeline.placeholders import (
    PlaceholderError,
    check_event_placeholders,
    text_problems,
)
from pipeline.plot import plot

EXAMPLE = (Path(__file__).resolve().parent.parent / "case_model" / "fixtures" / "generator"
           / "amexio_example" / "employees.json")


@pytest.fixture
def jan():
    cases, _ = ingest_employees(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    return cases[0]


def only(problems, *words):
    """The one problem, and that it says every word given."""
    assert len(problems) == 1, problems
    assert all(w in problems[0] for w in words), problems[0]
    return problems[0]


# --- passes -----------------------------------------------------------------

def test_placeholders_that_resolve_and_no_typed_facts_pass(jan):
    text = ("On {{events.EVT-001.date}}, {{ personas.P002.name }} welcomed "
            "{{personas.P001.name}} at {{organisations.ORG-01.name}} for "
            "{{employments.P001.salary}} a month.")
    assert text_problems(text, jan) == []


def test_descriptions_and_words_that_contain_a_name_pass(jan):
    text = "The occupational physician of the Occupational health service met Janssen."
    assert text_problems(text, jan) == []     # P003 and ORG-03 are labels; "Jan" is not a word here


# --- 1 · every placeholder resolves to one fact ------------------------------

def test_an_unknown_collection_fails(jan):
    only(text_problems("{{projects.X1.name}} started.", jan),
         "{{projects.X1.name}} does not resolve", "unknown collection")


def test_an_unknown_key_fails(jan):
    only(text_problems("{{personas.P999.name}} started.", jan), "no persona 'P999'")


def test_an_unknown_field_fails(jan):
    only(text_problems("{{personas.P001.nickname}} started.", jan), "cannot read 'nickname'")


def test_a_whole_object_is_not_one_fact(jan):
    only(text_problems("{{personas.P001}} started.", jan), "whole Persona", "not one fact")


def test_an_internal_id_fails_as_fill_refuses_it(jan):
    only(text_problems("{{personas.P001.id}} started.", jan), "an internal ID")


def test_part_of_an_amount_fails_and_names_the_whole_amount(jan):
    """Fill would print "4350"; the whole amount prints "EUR 4.350" (case model AX-025)."""
    only(text_problems("{{employments.P001.salary.amount}} a month.", jan),
         "part of one fact", "{{employments.P001.salary}}")


def test_the_check_accepts_exactly_what_fill_prints(jan):
    """Every fact the case model lists (AX-023) passes, and Fill fills it."""
    from case_model.fill import fact_paths, fill_text
    for path in fact_paths(jan):
        text = f"{{{{{path}}}}}"
        problems = [p for p in text_problems(text, jan) if "typed out" not in p]
        assert problems == [] or problems == [f"{text} is empty in this case"], (path, problems)
        fill_text(jan, text)


def test_an_empty_fact_fails(jan):
    only(text_problems("Born on {{personas.P001.date_of_birth}}.", jan), "holds no value")


@pytest.mark.parametrize("text", ["{{personas.P001.name} wrote.", "{personas.P001.name} wrote.",
                                  "{{{personas.P001.name}} wrote."])
def test_a_placeholder_with_a_brace_missing_or_extra_fails(jan, text):
    only(text_problems(text, jan), "not written as {{collection.key.field}}")


# --- 2 · no fact typed out -----------------------------------------------------

def test_a_full_name_typed_out_fails_and_names_its_placeholder(jan):
    only(text_problems("Jan de Vries met the goals.", jan),
         "'Jan de Vries' is a name typed out", "{{personas.P001.name}}")


def test_one_word_of_a_name_typed_out_fails(jan):
    only(text_problems("Jan met the goals.", jan), "'Jan'", "{{personas.P001.name}}")
    only(text_problems("Mr de Vries met the goals.", jan), "'Vries'")
    only(text_problems("Bakker agreed.", jan), "'Bakker'", "{{personas.P002.name}}")


def test_an_organisation_typed_out_fails(jan):
    only(text_problems("A course at the Training Academy.", jan), "{{organisations.ORG-02.name}}")
    only(text_problems("Joined Acme Logistics.", jan), "{{organisations.ORG-01.name}}")


@pytest.mark.parametrize("text, shown", [("Started on 2024-03-12.", "'2024-03-12'"),
                                         ("Started on 12/03/2024.", "'12/03/2024'"),
                                         ("Started on 12 March 2024.", "'12 March 2024'"),
                                         ("Started in March.", "'March'"),
                                         ("Begonnen in maart.", "'maart'")])
def test_a_date_typed_out_fails(jan, text, shown):
    only(text_problems(text, jan), shown, "a date typed out")


@pytest.mark.parametrize("text, shown", [("A raise to EUR 4.500.", "'EUR 4.500'"),
                                         ("A raise to €4350.", "'€4350'"),
                                         ("A 3% raise.", "'3%'"),
                                         ("A raise of three percent.", "'percent'")])
def test_an_amount_typed_out_fails(jan, text, shown):
    only(text_problems(text, jan), shown, "an amount or percentage typed out")


def test_any_other_number_fails(jan):
    only(text_problems("Completed 3 courses.", jan), "'3' is a number typed out")


def test_every_problem_of_a_text_is_named(jan):
    problems = text_problems("Jan joined Acme Logistics on 2021-03-01 for EUR 4350.", jan)
    assert len(problems) == 4                      # two names, a date, an amount
    assert {p.split(" is ")[1].split(" typed")[0] for p in problems} == {
        "a name", "a date", "an amount or percentage"}


# --- the check in complete_as: Part 2 --------------------------------------

def _part2(config, amexio_employees):
    """Jan's case after CM ID, its outline, and the fake's good answer."""
    one = config.model_copy(update={"employee_count": 1})
    cm = cm_id(None, one, [EmployeeIn.model_validate(amexio_employees["employees"][0])])
    outline = plot(cm, one)
    fake = FakeLLM(fake_answers.answer)
    write_event_content(cm.cases, outline, fake)
    return cm, outline, fake_answers.answer(fake.prompts[0])


def test_part_2_text_is_checked_and_the_course_is_not(jan):
    content = EventContentIn.model_validate({"content": [{"employeeNumber": "100101", "slots": [
        {"slot": "S01", "summary": "Took a course.", "course": "ISO 27001 Awareness"},
        {"slot": "S02", "summary": "Annual review.", "comment": "Jan delivered well."},
    ]}]})
    with pytest.raises(PlaceholderError, match="slot S02, comment: 'Jan'") as exc:
        check_event_placeholders({"100101": jan}, content)
    assert exc.value.field == "content.0.slots.1.comment"


def test_a_name_in_part_2_gets_the_retry_with_the_problem_named(config, amexio_employees):
    cm, outline, good = _part2(config, amexio_employees)
    bad = copy.deepcopy(good)
    bad["content"][0]["slots"][0]["summary"] = "Jan de Vries had a good year."
    fake = FakeLLM([bad, good])
    write_event_content(cm.cases, outline, fake)
    assert "'Jan de Vries' is a name typed out" in fake.prompts[1]
    assert fake.calls[0].ok and fake.calls[0].retries == 1


def test_two_bad_part_2_answers_fail_naming_the_field(config, amexio_employees):
    cm, outline, good = _part2(config, amexio_employees)
    bad = copy.deepcopy(good)
    bad["content"][0]["slots"][0]["summary"] = "Started on 2021-03-01."
    with pytest.raises(LLMError, match="a date typed out") as exc:
        write_event_content(cm.cases, outline, FakeLLM([bad, bad]))
    assert exc.value.field == "content.0.slots.0.summary"


# --- the check in complete_as: Part 3 --------------------------------------

def _seed_request(request_data, amexio_employees):
    request_data["config"]["employeeCount"] = 1
    request_data["seedEmployees"] = amexio_employees["employees"][:1]
    return RunRequest.model_validate(request_data)


def _part3(request_data, amexio_employees):
    """Jan's dated case, its plan, and the fake's good answer."""
    case = run_chain(_seed_request(request_data, amexio_employees)).cases[0]
    plan = plan_case(case)
    assert plan.documents
    fake = FakeLLM(fake_answers.answer)
    write_document_text(case, plan, fake)
    return case, plan, fake_answers.answer(fake.prompts[0])


def _first_section(answer):
    return next(iter(answer["documents"][0]["sections"]))


def test_an_unknown_placeholder_in_part_3_gets_the_retry_with_it_named(request_data,
                                                                      amexio_employees):
    case, plan, good = _part3(request_data, amexio_employees)
    bad = copy.deepcopy(good)
    bad["documents"][0]["sections"][_first_section(bad)] = "{{personas.P999.name}} reviewed it."
    fake = FakeLLM([bad, good])
    write_document_text(case, plan, fake)
    assert "{{personas.P999.name}} does not resolve" in fake.prompts[1]
    assert fake.calls[0].ok and fake.calls[0].retries == 1


def test_two_bad_part_3_answers_fail_naming_the_field(request_data, amexio_employees):
    case, plan, good = _part3(request_data, amexio_employees)
    bad = copy.deepcopy(good)
    section = _first_section(bad)
    bad["documents"][0]["sections"][section] = "Your salary is now EUR 4500."
    with pytest.raises(LLMError, match="amount or percentage typed out") as exc:
        write_document_text(case, plan, FakeLLM([bad, bad]))
    assert exc.value.field == f"documents.0.sections.{section}"


def test_the_chain_stops_at_document_text_naming_the_field(request_data, amexio_employees,
                                                           tmp_path):
    def answer(prompt):
        reply = fake_answers.answer(prompt)
        if request_of(prompt)["task"] == "document_text":
            for document in reply["documents"]:
                for section in document["sections"]:
                    document["sections"][section] = "Jan de Vries did well."
        return reply

    with pytest.raises(ChainError) as exc:
        run_chain(_seed_request(request_data, amexio_employees), llm=FakeLLM(answer),
                  out_dir=tmp_path)
    assert exc.value.stage == "document_text" and exc.value.kind == "llm"
    assert exc.value.field.startswith("documents.0.sections.")
    assert "'Jan de Vries' is a name typed out" in str(exc.value)
    assert list(tmp_path.iterdir()) == []                 # nothing half-written
