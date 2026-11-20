"""LLM client (contract v1.1 §8): ``complete_as`` validates, retries once with
the error named, then raises ``LLMError`` naming the field; every call is
recorded for the trace. All offline with ``FakeLLM``."""

import pytest
from pydantic import BaseModel, ConfigDict

from pipeline.llm import FakeLLM, LLMClient, LLMError, extract_json


class Greeting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def test_fake_is_an_llm_client():
    assert isinstance(FakeLLM([]), LLMClient)


def test_complete_returns_text_and_model():
    fake = FakeLLM(['{"text": "hi"}'], name="fake-1")
    answer = fake.complete("p")
    assert answer.text == '{"text": "hi"}' and answer.model == "fake-1"


def test_complete_as_returns_a_validated_object():
    fake = FakeLLM([{"text": "hello"}])
    out = fake.complete_as("say hi", Greeting)
    assert out == Greeting(text="hello")
    assert fake.prompts == ["say hi"]
    assert fake.calls[0].ok and fake.calls[0].retries == 0


def test_complete_as_accepts_a_fenced_answer():
    fake = FakeLLM(['Here:\n```json\n{"text": "hi"}\n```'])
    assert fake.complete_as("p", Greeting).text == "hi"


def test_one_bad_answer_is_retried_with_the_error_named():
    fake = FakeLLM([{"wrong": 1}, {"text": "hi"}])
    assert fake.complete_as("p", Greeting).text == "hi"
    assert "not valid: text: Field required" in fake.prompts[1]   # the retry names it
    assert fake.calls[0].retries == 1


def test_two_bad_answers_raise_an_error_naming_the_field():
    fake = FakeLLM([{"wrong": 1}, {"wrong": 2}])
    with pytest.raises(LLMError, match="did not match Greeting after 2 tries") as exc:
        fake.complete_as("p", Greeting)
    assert exc.value.field == "text"
    assert fake.calls[0].ok is False


def test_an_id_from_the_model_is_refused():
    fake = FakeLLM([{"text": "hi", "id": "P001"}] * 2)       # AX-012, extra=forbid
    with pytest.raises(LLMError) as exc:
        fake.complete_as("p", Greeting)
    assert exc.value.field == "id"


def test_a_failing_check_gets_the_retry():
    def check(g):
        if g.text != "ok":
            raise ValueError("text must be ok")
    fake = FakeLLM([{"text": "no"}, {"text": "ok"}])
    assert fake.complete_as("p", Greeting, check=check).text == "ok"
    assert "text must be ok" in fake.prompts[1]


def test_no_json_at_all_is_refused():
    with pytest.raises(ValueError, match="no valid JSON"):
        extract_json("sorry, I cannot do that")


def test_fake_raises_when_it_runs_out_of_answers():
    with pytest.raises(LLMError, match="no more answers"):
        FakeLLM([]).complete("p")
