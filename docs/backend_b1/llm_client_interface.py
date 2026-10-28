"""Draft — LLM client interface for the backend (BE-04). Proposal to show Robin.

Python mirror of Robin's TypeScript client
(generator/demo_dossier_generator/src/ai/types.ts + providers.ts), for the
Python backend stages (CM ID, Plot).

NOT final code. It fixes the SHAPE every stage can rely on; the real client
lives in the team repo's pipeline/ once BE-01 and BE-04 are agreed, and the
concrete providers (Anthropic, ...) are written together with Robin. Run this
file to see the gate accept, retry once, and fail loud:

    python3 docs/backend_b1/llm_client_interface.py
"""

from __future__ import annotations

import json
import re
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

# The four kinds are Robin's ModelError kinds, so the caller knows what to DO.
ErrorKind = Literal["setup", "retry", "refused", "cancelled"]


class LLMError(Exception):
    """A model error the caller can branch on.

    setup     - fix the configuration (missing key, wrong model name)
    retry     - a technical hiccup; try again later
    refused   - the request must change: the model won't comply, or its answer
                never matched the expected shape after the retries
    cancelled - the run was stopped
    """

    def __init__(self, message: str, kind: ErrorKind) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind


class LLMClient(Protocol):
    """The whole interface a stage depends on: send a prompt, get text back.

    The model is a dependency behind this interface; a stage never knows which
    provider answered. Only `complete` is a provider's job — parsing,
    validation and the retry are added once by `complete_as` below, so no
    provider and no stage repeats that logic.
    """

    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None) -> str:
        """Send one prompt, return the model's text (no parsing here)."""
        ...

    def describe(self) -> str:
        """What answered, for the trace and the README: 'claude-... via ...'."""
        ...


TModel = TypeVar("TModel", bound=BaseModel)


def complete_as(
    client: LLMClient,
    model: type[TModel],
    system: str,
    prompt: str,
    *,
    max_retries: int = 1,
) -> TModel:
    """Call the model and return a VALIDATED object — the gate before the case model.

    The LLM proposes; this extracts JSON from the answer and validates it
    against `model`. On a bad answer it retries once (BE-10), adding a short
    reminder, then fails loud with an error that names the field. The caller
    gets a valid object or an exception — never anything half-built.
    """
    attempt = 0
    reminder = ""
    detail = ""
    while attempt <= max_retries:
        answer = client.complete(system, prompt + reminder)
        try:
            return model.model_validate(_extract_json(answer))
        except (ValueError, ValidationError) as exc:
            detail = _detail(exc)
            reminder = (
                f"\n\nYour previous answer was not valid: {detail}. "
                "Reply with one JSON object only, no text around it."
            )
            attempt += 1
    raise LLMError(
        f"The model's answer did not match {model.__name__} after "
        f"{max_retries + 1} tries: {detail}",
        kind="refused",
    )


def _extract_json(text: str) -> object:
    """Robin's extractJson, in Python: accept bare JSON, a ```json fence, or
    JSON embedded in prose. The result is still untrusted; `complete_as`
    validates it against the model."""
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
        start = min(starts)
        end = max(trimmed.rfind("}"), trimmed.rfind("]"))
        if end > start:
            try:
                return json.loads(trimmed[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError("the answer contained no valid JSON")


def _detail(exc: Exception) -> str:
    """One short line that names the field, for the reminder and the error."""
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ())) or "(root)"
        return f"{loc}: {first.get('msg', 'invalid')}"
    return str(exc)


class FakeLLM:
    """A fake model for tests and offline runs: no API key, no network (BE-04).

    It returns canned answers in order and goes through the SAME `complete_as`
    gate as a real model, so a test can prove the chain runs offline and that
    two bad answers raise the BE-10 error with nothing written.
    """

    def __init__(self, answers: list[str], *, name: str = "FakeLLM") -> None:
        self._answers = list(answers)
        self._name = name
        self.calls = 0

    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None) -> str:
        if not self._answers:
            raise LLMError("FakeLLM ran out of canned answers.", kind="setup")
        self.calls += 1
        return self._answers.pop(0)

    def describe(self) -> str:
        return self._name


# A real provider would have the same shape — written with Robin, not here:
#
#   class AnthropicLLM:
#       def __init__(self, api_key: str, model: str) -> None: ...
#       def complete(self, system, prompt, *, max_tokens=None) -> str:
#           # POST to the Anthropic API; map HTTP status to LLMError kinds,
#           # exactly as Robin's providers.ts does; return the text.
#       def describe(self) -> str:
#           return f"{self._model} via Anthropic API"


if __name__ == "__main__":
    # A short demonstration (not the test suite): accept a good answer, accept a
    # fenced one, retry once past a bad one, fail loud on two bad ones.
    class _Employee(BaseModel):
        first_name: str
        last_name: str

    good = '{"first_name": "Jan", "last_name": "de Vries"}'
    fenced = "Here you go:\n```json\n" + good + "\n```"
    bad = "sorry, I cannot do that"

    print("good   ->", complete_as(FakeLLM([good]), _Employee, "sys", "p"))
    print("fenced ->", complete_as(FakeLLM([fenced]), _Employee, "sys", "p"))
    one_retry = FakeLLM([bad, good])
    print("retry  ->", complete_as(one_retry, _Employee, "sys", "p"), f"({one_retry.calls} calls)")
    try:
        complete_as(FakeLLM([bad, bad]), _Employee, "sys", "p")
    except LLMError as e:
        print(f"two bad-> LLMError(kind={e.kind!r}): {e}")
