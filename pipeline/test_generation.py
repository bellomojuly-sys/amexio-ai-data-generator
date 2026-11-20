"""The three generation calls (contract v1.1 §3; Robin's, reference version):
batch sizes and checks, offline with the fake answers."""

import pytest

from pipeline import fake_answers
from pipeline.cm_id import cm_id
from pipeline.contracts import CaseDocumentPlan, PersonasIn
from pipeline.generation import propose_personas, write_document_text, write_event_content
from pipeline.llm import FakeLLM, LLMError
from pipeline.plot import plot


def test_personas_are_proposed_in_batches_of_25(config):
    fake = FakeLLM(fake_answers.answer)
    out = propose_personas(config, fake, count=30)
    assert len(out.employees) == 30
    assert len(fake.calls) == 2


def test_a_short_personas_answer_is_retried_then_refused(config):
    short = {"employees": [{"firstName": "A", "lastName": "B", "department": "IT",
                            "position": "Software Developer"}]}
    with pytest.raises(LLMError, match="asked for 10, got 1"):
        propose_personas(config, FakeLLM([short, short]))


def test_event_content_answers_every_slot_in_batches_of_5(config):
    fake = FakeLLM(fake_answers.answer)
    personas = propose_personas(config, fake)
    cm = cm_id(personas, config)
    outline = plot(cm, config)
    content = write_event_content(cm.cases, outline, fake)
    assert len(content.content) == 10
    assert len(fake.calls) == 1 + 2


def test_a_missing_slot_gets_the_retry_then_fails(config):
    cm = cm_id(propose_personas(config, FakeLLM(fake_answers.answer)), config)
    outline = plot(cm, config)
    first = outline.outlines[0]
    incomplete = {"content": [{"employeeNumber": first.employee_number, "slots": []}]}
    with pytest.raises(LLMError, match="not answered"):
        write_event_content(cm.cases[:1], outline.model_copy(update={"outlines": [first]}),
                            FakeLLM([incomplete, incomplete]))


def test_document_text_refuses_a_plan_for_another_case(config):
    cm = cm_id(propose_personas(config, FakeLLM(fake_answers.answer)), config)
    plan = CaseDocumentPlan.model_validate({"employeeNumber": "100999", "documents": []})
    with pytest.raises(LLMError, match="plan for 100999"):
        write_document_text(cm.cases[0], plan, FakeLLM(fake_answers.answer))


def test_prompts_carry_no_case_ids_for_personas(config):
    fake = FakeLLM(fake_answers.answer)
    propose_personas(config, fake)
    assert "P001" not in fake.prompts[0] and "100101" not in fake.prompts[0]
