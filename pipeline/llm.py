"""LLM client interface and an offline fake (BE-04, with Robin).

One call: a prompt plus the pydantic model the answer must fit; back a validated
instance of that model. Robin implements the real client against this interface
(``LLMClient``); the stages depend only on the interface, so their tests run
offline with ``FakeLLM`` — no API key, no network.

The client validates the model's answer. An answer that does not fit the
requested model (including one that carries an ``id``, AX-012) raises
``LLMError``: a stage sees a clear failure, never a half-valid object.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model's answer could not be turned into the requested model."""


@runtime_checkable
class LLMClient(Protocol):
    """What every stage may call. Robin's real client implements it."""

    def generate(self, prompt: str, output_model: type[T]) -> T:
        """Ask the model for `prompt`; return an instance of `output_model`,
        validated. Raise ``LLMError`` if the answer does not fit."""
        ...


class FakeLLM:
    """An offline ``LLMClient`` for tests. Give it the answers it should return,
    in order; each is validated into the model the stage asks for, exactly as
    the real client validates a real answer.

    >>> fake = FakeLLM([{"text": "hello"}])
    >>> fake.generate("say hi", Greeting).text      # doctest: +SKIP
    'hello'
    """

    def __init__(self, answers: list[object]):
        self._answers = list(answers)
        self.prompts: list[str] = []

    def generate(self, prompt: str, output_model: type[T]) -> T:
        self.prompts.append(prompt)
        if not self._answers:
            raise LLMError("FakeLLM has no more answers to give.")
        payload = self._answers.pop(0)
        try:
            return output_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMError(
                f"answer does not fit {output_model.__name__}: {exc}"
            ) from exc
