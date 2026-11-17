"""LLM client interface and an offline fake (pipeline contract v1.1 §8).

Every LLM call goes through one client (rule 6). The interface has two calls:

- ``complete(prompt) -> Completion``: the model's text and token usage;
- ``complete_as(prompt, output_model) -> T``: the answer validated into
  ``output_model``. On a bad answer it retries **once** with the validation
  error in the prompt, then raises ``LLMError`` naming the field (rule 5). The
  retry lives here, so no step implements its own.

``BaseLLMClient`` implements ``complete_as`` on top of ``complete`` (the logic
of Robin's draft, ``docs/backend_b1/llm_client_interface.py``), so a provider
only writes ``complete``. Robin implements the real providers; ``FakeLLM`` has
the same interface, so every step is tested offline without an API key.

Every call appends one record to ``calls`` (model, tokens, time, retries); the
chain turns them into trace lines (``TraceLine``, BE-19).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model's answer could not be turned into the requested model."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class CallRecord:
    """What one ``complete_as`` call cost, for the trace."""

    model: str
    ok: bool
    ms: int
    input_tokens: int
    output_tokens: int
    retries: int
    error: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    """What every step may call (contract §8). Robin's real client implements it."""

    calls: list[CallRecord]

    def complete(self, prompt: str) -> Completion: ...

    def complete_as(self, prompt: str, output_model: type[T], check=None) -> T: ...


class BaseLLMClient:
    """``complete_as`` once, for every provider: extract JSON, validate, retry
    once with the error named, then fail loud. Subclasses write ``complete``."""

    max_retries = 1

    def __init__(self):
        self.calls: list[CallRecord] = []

    def complete(self, prompt: str) -> Completion:   # pragma: no cover - abstract
        raise NotImplementedError

    def complete_as(self, prompt: str, output_model: type[T], check=None) -> T:
        """Validate the answer into ``output_model``; then, if given, run
        ``check(result)``, a rule the shape alone cannot express (every slot
        answered once, …). A ``ValueError`` from either gets the one retry."""
        start = time.perf_counter()
        tokens_in = tokens_out = 0
        model = "unknown"
        reminder = ""
        detail, where = "", None
        for attempt in range(self.max_retries + 1):
            answer = self.complete(prompt + reminder)
            model = answer.model
            tokens_in += answer.input_tokens
            tokens_out += answer.output_tokens
            try:
                result = output_model.model_validate(extract_json(answer.text))
                if check is not None:
                    check(result)
            except (ValueError, ValidationError) as exc:
                detail, where = _detail(exc)
                reminder = (
                    f"\n\nYour previous answer was not valid: {detail}. "
                    "Reply with one JSON object only, no text around it."
                )
                continue
            self._record(model, True, start, tokens_in, tokens_out, attempt)
            return result
        message = (
            f"the model's answer did not match {output_model.__name__} after "
            f"{self.max_retries + 1} tries: {detail}"
        )
        self._record(model, False, start, tokens_in, tokens_out, self.max_retries, message)
        raise LLMError(message, field=where)

    def _record(self, model, ok, start, tokens_in, tokens_out, retries, error=None):
        self.calls.append(CallRecord(
            model=model, ok=ok, ms=int((time.perf_counter() - start) * 1000),
            input_tokens=tokens_in, output_tokens=tokens_out, retries=retries, error=error,
        ))


def extract_json(text: str) -> object:
    """Accept bare JSON, a ```json fence, or JSON inside prose (Robin's
    ``extractJson``). The result is still untrusted: ``complete_as`` validates it."""
    trimmed = text.strip()
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", trimmed, re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    starts = [i for i in (trimmed.find("{"), trimmed.find("[")) if i >= 0]
    if starts:
        start, end = min(starts), max(trimmed.rfind("}"), trimmed.rfind("]"))
        if end > start:
            try:
                return json.loads(trimmed[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError("the answer contained no valid JSON")


def _detail(exc: Exception) -> tuple[str, str | None]:
    """One short line naming the field, and the field's dotted path."""
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ())) or None
        return f"{where or '(root)'}: {first.get('msg', 'invalid')}", where
    return str(exc), None


class FakeLLM(BaseLLMClient):
    """An offline client for tests and ``options.fake_llm`` runs. Give it the
    answers to return, in order: a string is returned as the model's text, any
    other value is sent as JSON. It goes through the same ``complete_as`` gate
    as a real model, so two bad answers raise the same ``LLMError``.

    ``answers`` may also be a function ``prompt -> answer``, for a fake that
    answers whatever the chain asks (see ``pipeline.fake_answers``).
    """

    def __init__(self, answers, name: str = "fake-llm"):
        super().__init__()
        self._answers = answers if callable(answers) else list(answers)
        self.name = name
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> Completion:
        self.prompts.append(prompt)
        if callable(self._answers):
            answer = self._answers(prompt)
        elif not self._answers:
            raise LLMError("FakeLLM has no more answers to give.")
        else:
            answer = self._answers.pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return Completion(text=text, model=self.name)
