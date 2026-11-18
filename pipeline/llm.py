"""LLM client interface, the real provider and an offline fake (pipeline contract v1.1 §8).

Every LLM call goes through one client (rule 6). The interface has two calls:

- ``complete(prompt) -> Completion``: the model's text and token usage;
- ``complete_as(prompt, output_model) -> T``: the answer validated into
  ``output_model``. On a bad answer it retries **once** with the validation
  error in the prompt, then raises ``LLMError`` naming the field (rule 5). The
  retry lives here, so no step implements its own.

``BaseLLMClient`` implements ``complete_as`` on top of ``complete`` (the logic
of Robin's draft, ``docs/backend_b1/llm_client_interface.py``), so a provider
only writes ``complete``. The providers (Robin):

- ``AnthropicLLM``: Claude through the Anthropic Messages API, Claude Sonnet
  5.5 by default (Model Selection document, team decision of 30 Oct);
- ``FakeLLM``: offline, same interface, so every step is tested without an
  API key.

``create_llm()`` picks one by name, like the v1 demo's ``createProvider``. A
provider that gets no usable answer raises ``ProviderError`` with one of v1's
kinds: ``setup`` (fix the settings), ``retry`` (try again later), ``refused``
(change the request) or ``cancelled`` (the run was stopped).

Every ``complete_as`` call appends one record to ``calls`` (model, tokens,
time, retries, and each attempt's prompt, answer and error); the chain turns
them into trace lines (``TraceLine``, BE-19). A call that fails at the
provider is recorded too, so every call has its trace line.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model's answer could not be turned into the requested model."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


ErrorKind = Literal["setup", "retry", "refused", "cancelled"]


class ProviderError(LLMError):
    """The model service gave no usable answer (v1's ``ModelError``). ``kind``
    says what the user can do: ``setup`` fix the settings (key, model,
    address), ``retry`` try again later, ``refused`` change the request,
    ``cancelled`` the run was stopped. It is an ``LLMError``, so the chain
    reports it like any failed LLM step, naming the stage."""

    def __init__(self, message: str, kind: ErrorKind):
        super().__init__(message)
        self.kind = kind


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Attempt:
    """One try inside a ``complete_as`` call: the prompt sent, the answer that
    came back (``None`` when the provider failed first) and why code refused
    it (``None`` when it was accepted). Kept so the demo can show them."""

    prompt: str
    answer: str | None = None
    error: str | None = None


@dataclass
class CallRecord:
    """What one ``complete_as`` call cost, for the trace, plus its attempts."""

    model: str
    ok: bool
    ms: int
    input_tokens: int
    output_tokens: int
    retries: int
    error: str | None = None
    attempts: list[Attempt] = field(default_factory=list)


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
    model = "unknown"          # a provider sets the model it calls

    def __init__(self):
        self.calls: list[CallRecord] = []
        self._stop = threading.Event()

    def complete(self, prompt: str) -> Completion:   # pragma: no cover - abstract
        raise NotImplementedError

    def cancel(self) -> None:
        """Stop the run: the next call, or a wait before a retry, raises
        ``ProviderError`` of kind ``cancelled``. A request already sent still
        finishes. Make a new client for the next run."""
        self._stop.set()

    def complete_as(self, prompt: str, output_model: type[T], check=None) -> T:
        """Validate the answer into ``output_model``; then, if given, run
        ``check(result)``, a rule the shape alone cannot express (every slot
        answered once, …). A ``ValueError`` from either gets the one retry.

        An error from ``complete`` itself (no key, service down, cancelled) is
        not retried here: it is recorded as a failed call and raised as is."""
        start = time.perf_counter()
        tokens_in = tokens_out = 0
        model = self.model
        reminder = ""
        detail, where = "", None
        attempts: list[Attempt] = []
        for attempt in range(self.max_retries + 1):
            sent = prompt + reminder
            try:
                if self._stop.is_set():
                    raise ProviderError("Stopped.", "cancelled")
                answer = self.complete(sent)
            except Exception as exc:
                attempts.append(Attempt(prompt=sent, error=str(exc)))
                self._record(model, False, start, tokens_in, tokens_out, attempt,
                             str(exc), attempts)
                raise
            model = answer.model
            tokens_in += answer.input_tokens
            tokens_out += answer.output_tokens
            try:
                result = output_model.model_validate(extract_json(answer.text))
                if check is not None:
                    check(result)
            except (ValueError, ValidationError) as exc:
                detail, where = _detail(exc)
                attempts.append(Attempt(prompt=sent, answer=answer.text, error=detail))
                reminder = (
                    f"\n\nYour previous answer was not valid: {detail}. "
                    "Reply with one JSON object only, no text around it."
                )
                continue
            attempts.append(Attempt(prompt=sent, answer=answer.text))
            self._record(model, True, start, tokens_in, tokens_out, attempt, None, attempts)
            return result
        message = (
            f"the model's answer did not match {output_model.__name__} after "
            f"{self.max_retries + 1} tries: {detail}"
        )
        self._record(model, False, start, tokens_in, tokens_out, self.max_retries, message,
                     attempts)
        raise LLMError(message, field=where)

    def _record(self, model, ok, start, tokens_in, tokens_out, retries, error=None,
                attempts=()):
        self.calls.append(CallRecord(
            model=model, ok=ok, ms=int((time.perf_counter() - start) * 1000),
            input_tokens=tokens_in, output_tokens=tokens_out, retries=retries, error=error,
            attempts=list(attempts),
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
        self.model = name
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


# --- The real provider (Robin) -----------------------------------------------
#
# Plain HTTP with the standard library, as the v1 demo's providers (fetch) and
# Daniel's ``ai_gateway.py`` (urllib) do: no new dependency in the shared CI,
# and every status -> kind mapping is here and tested in test_llm_providers.py.

MODEL_DEFAULTS = {
    # The default for everyone who runs this copy; AMEXIO_LLM_MODEL overrides
    # it on one machine (v1: src/config/model.ts and VITE_MODEL_NAME).
    "anthropic": "claude-sonnet-5-5",
}
PROVIDER_ENV = "AMEXIO_LLM_PROVIDER"
MODEL_ENV = "AMEXIO_LLM_MODEL"

MAX_TOKENS = 8000        # v1's default; complete(prompt) has no per-call size
TIMEOUT_S = 120.0
WAIT_STATUSES = {429, 529}   # rate limited, overloaded: wait once, then "retry"
DEFAULT_WAIT_S = 10.0        # when the service sends no Retry-After
MAX_WAIT_S = 60.0            # a longer Retry-After is not waited for

_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), None)

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8", errors="replace"))
        except ValueError:
            return None


Transport = Callable[[str, dict, bytes, float], HttpResponse]


def urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> HttpResponse:
    """POST ``body`` to ``url``. An HTTP error status is returned, not raised;
    a network failure raises (``URLError``, ``TimeoutError``, ``OSError``)."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read(), dict(response.headers.items()))
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, exc.read() or b"",
                            dict(exc.headers.items()) if exc.headers else {})


def _count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class _HttpLLM(BaseLLMClient):
    """What every HTTP provider shares: the key from one environment
    variable, one POST with v1's error kinds, and one wait-and-retry when the
    service is rate limited or overloaded (not counted in ``retries``, which
    counts the answer retry of ``complete_as``)."""

    service = "the model service"
    key_env = ""

    def __init__(self, model: str, *, max_tokens: int = MAX_TOKENS, timeout: float = TIMEOUT_S,
                 temperature: float | None = None, transport: Transport = urllib_transport,
                 wait: Callable[[float], bool] | None = None):
        super().__init__()
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.temperature = temperature
        self._transport = transport
        # Waits up to n seconds; True when the run was cancelled meanwhile.
        self._wait = wait or self._stop.wait
        self._key = ""

    def _read_key(self) -> str:
        key = os.environ.get(self.key_env, "").strip()
        if not key:
            raise ProviderError(
                f"No API key: set the {self.key_env} environment variable (for the "
                "demo app, a .env file next to it, which git ignores).", "setup")
        return key

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        name = self.service[0].upper() + self.service[1:]
        for attempt in range(2):
            if self._stop.is_set():
                raise ProviderError("Stopped.", "cancelled")
            try:
                response = self._transport(url, headers, body, self.timeout)
            except TimeoutError:
                raise ProviderError(f"{name} did not answer within {self.timeout:.0f} "
                                    "seconds. Try again.", "retry") from None
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    raise ProviderError(f"{name} did not answer within {self.timeout:.0f} "
                                        "seconds. Try again.", "retry") from None
                raise ProviderError(f"Could not reach {self.service} at {url}. Check the "
                                    "internet connection and the address.", "setup") from None
            except (OSError, http.client.HTTPException):
                raise ProviderError(f"The connection to {self.service} was lost. "
                                    "Try again.", "retry") from None
            if 200 <= response.status < 300:
                data = response.json()
                if not isinstance(data, dict):
                    raise ProviderError(f"{name} sent an answer that is not JSON. "
                                        "Try again.", "retry")
                return data
            seconds = self._wait_for(response) if attempt == 0 else None
            if seconds is None:
                raise self._http_error(response, name)
            if self._wait(seconds):
                raise ProviderError("Stopped.", "cancelled")
        raise AssertionError("unreachable")   # pragma: no cover

    @staticmethod
    def _wait_for(response: HttpResponse) -> float | None:
        """Seconds to wait before the one transport retry, or None: no retry."""
        if response.status not in WAIT_STATUSES:
            return None
        raw = response.header("retry-after")
        try:
            seconds = float(raw) if raw is not None else DEFAULT_WAIT_S
        except ValueError:            # an HTTP date: wait the default
            seconds = DEFAULT_WAIT_S
        return seconds if 0 <= seconds <= MAX_WAIT_S else None

    def _detail(self, response: HttpResponse) -> str:
        """The service's own error message, without the key, on one short line."""
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        message = error.get("message") if isinstance(error, dict) else error
        if not isinstance(message, str):
            return ""
        if self._key:
            message = message.replace(self._key, "[redacted]")
        return " ".join(_SECRET.sub("[redacted]", message).split())[:300]

    def _http_error(self, response: HttpResponse, name: str) -> ProviderError:
        """v1's ``httpError``, with the Anthropic API's documented statuses."""
        status, detail = response.status, self._detail(response)
        note = f" ({detail})" if detail else ""
        if status in (401, 403):
            return ProviderError(f"{name} rejected the API key in {self.key_env}. "
                                 f"Check it.{note}", "setup")
        if status == 402 or (status == 400 and "credit balance" in detail.lower()):
            return ProviderError(f"{name} reports a billing or credit problem for this "
                                 f"key. Check the account.{note}", "setup")
        if status == 404:
            return ProviderError(f"{name} does not know this model or address. Check the "
                                 f"model name ({self.model}) and the address.{note}", "setup")
        if status in (400, 413):
            return ProviderError(f"{name} refused the request.{note} Change the request, "
                                 "for example fewer employees or shorter notes.", "refused")
        if status == 429:
            return ProviderError(f"{name} rate limit or quota reached. Wait and try "
                                 f"again.{note}", "retry")
        if status == 529:
            return ProviderError(f"{name} is overloaded. Try again in a few minutes.{note}",
                                 "retry")
        return ProviderError(f"{name} returned an error ({status}).{note} Try again.", "retry")


ANTHROPIC_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicLLM(_HttpLLM):
    """Claude through the Anthropic Messages API (v1's ``anthropicProvider``).

    The key comes only from ``ANTHROPIC_API_KEY`` (contract §8), read when the
    client is made: to switch keys, change the variable and make a new client.
    ``ANTHROPIC_BASE_URL`` sends the same requests to another address that
    speaks this API (a gateway). Implements only ``complete``."""

    service = "the Anthropic API"
    key_env = "ANTHROPIC_API_KEY"

    def __init__(self, model: str | None = None, *, base_url: str | None = None, **options):
        super().__init__(model or MODEL_DEFAULTS["anthropic"], **options)
        self._key = self._read_key()
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL")
                         or ANTHROPIC_URL).rstrip("/")

    def complete(self, prompt: str) -> Completion:
        payload = {"model": self.model, "max_tokens": self.max_tokens,
                   "messages": [{"role": "user", "content": prompt}]}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        data = self._post(f"{self.base_url}/v1/messages", {
            "content-type": "application/json",
            "x-api-key": self._key,
            "anthropic-version": ANTHROPIC_VERSION,
        }, payload)
        stop = data.get("stop_reason")
        if stop == "refusal":
            raise ProviderError("Claude declined this request. Change the scenario notes "
                                "and try again.", "refused")
        if stop == "max_tokens":
            raise ProviderError(f"The answer was cut off at max_tokens={self.max_tokens}. "
                                "Raise max_tokens, or ask for less per call.", "setup")
        if stop == "model_context_window_exceeded":
            raise ProviderError("The request and answer do not fit in the model's context "
                                "window. Ask for less per call.", "refused")
        text = "".join(block.get("text", "") for block in data.get("content") or []
                       if isinstance(block, dict) and block.get("type") == "text")
        if not text.strip():
            raise ProviderError("Claude returned an empty answer. Try again.", "retry")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return Completion(text=text, model=str(data.get("model") or self.model),
                          input_tokens=_count(usage.get("input_tokens")),
                          output_tokens=_count(usage.get("output_tokens")))


def create_llm(provider: str | None = None, model: str | None = None,
               **options) -> BaseLLMClient:
    """The client for ``provider`` and ``model`` (v1's ``createProvider``).

    Without arguments: the provider in ``AMEXIO_LLM_PROVIDER`` (default
    ``anthropic``) and the model in ``AMEXIO_LLM_MODEL`` (default: the
    provider's entry in ``MODEL_DEFAULTS``). ``fake`` is the offline client
    with the deterministic answers of ``pipeline.fake_answers``."""
    name = (provider or os.environ.get(PROVIDER_ENV) or "anthropic").strip().lower()
    model = model or os.environ.get(MODEL_ENV, "").strip() or None
    if name == "anthropic":
        return AnthropicLLM(model, **options)
    if name == "fake":
        from . import fake_answers   # imported here: fake_answers imports generation, which imports llm
        return FakeLLM(fake_answers.answer)
    raise ProviderError(f"Unknown LLM provider {name!r}: use anthropic or fake.", "setup")
