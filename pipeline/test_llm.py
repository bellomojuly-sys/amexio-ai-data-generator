"""BE-04 — the fake LLM returns validated objects and refuses bad answers.

A stage test can run entirely offline with ``FakeLLM``: no API key, no network.
Each refusal checks the right reason (F1).
"""

import pytest
from pydantic import BaseModel, ConfigDict

from pipeline.llm import FakeLLM, LLMClient, LLMError


class Greeting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def test_fake_is_an_llm_client():
    # The fake satisfies the interface the stages depend on.
    assert isinstance(FakeLLM([]), LLMClient)


def test_fake_returns_a_validated_object():
    fake = FakeLLM([{"text": "hello"}])
    out = fake.generate("say hi", Greeting)
    assert isinstance(out, Greeting)
    assert out.text == "hello"
    assert fake.prompts == ["say hi"]      # it recorded the prompt, offline


def test_fake_refuses_an_answer_that_does_not_fit():
    fake = FakeLLM([{"wrong": 1}])         # missing 'text', extra field
    with pytest.raises(LLMError, match="does not fit Greeting"):
        fake.generate("p", Greeting)


def test_fake_refuses_an_id_from_the_model():
    fake = FakeLLM([{"text": "hi", "id": "P001"}])   # AX-012
    with pytest.raises(LLMError, match="does not fit Greeting"):
        fake.generate("p", Greeting)


def test_fake_raises_when_it_runs_out_of_answers():
    fake = FakeLLM([])
    with pytest.raises(LLMError, match="no more answers"):
        fake.generate("p", Greeting)
