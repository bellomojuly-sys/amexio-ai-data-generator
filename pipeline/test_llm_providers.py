"""The real provider (contract v1.1 §8; Robin): ``AnthropicLLM`` sends a
Messages API request with the key from ``LLM_API_KEY``, reads the text
and the tokens, and maps every failure to v1's kinds (setup, retry, refused,
cancelled). The client records every call, also one that fails at the
provider. All offline: a fake transport stands in for the network."""

import json
import urllib.error

import pytest
from pydantic import BaseModel, ConfigDict

from pipeline.chain import ChainError, run_chain
from pipeline.llm import AnthropicLLM, FakeLLM, HttpResponse, ProviderError, create_llm

KEY = "sk-ant-test-0123456789abcdef"


class Greeting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def message(text, stop="end_turn", model="claude-sonnet-5-5", tokens=(12, 5)):
    return HttpResponse(200, json.dumps({
        "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}], "stop_reason": stop,
        "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]},
    }).encode())


def error(status, kind="invalid_request_error", text="bad request", headers=None):
    body = {"type": "error", "error": {"type": kind, "message": text}}
    return HttpResponse(status, json.dumps(body).encode(), headers or {})


class Transport:
    """Returns (or raises) the queued replies in order and keeps each request."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append({"url": url, "headers": headers, "body": json.loads(body)})
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class Waits:
    """Records each wait instead of sleeping; ``cancelled`` plays a stop meanwhile."""

    def __init__(self, cancelled=False):
        self.seconds = []
        self.cancelled = cancelled

    def __call__(self, seconds):
        self.seconds.append(seconds)
        return self.cancelled


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", KEY)
    for name in ("ANTHROPIC_BASE_URL", "AMEXIO_LLM_MODEL", "AMEXIO_LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)


def client(*replies, wait=None, **options):
    transport = Transport(*replies)
    return AnthropicLLM(transport=transport, wait=wait or Waits(), **options), transport


def kind_of(llm, call=lambda llm: llm.complete("p")):
    with pytest.raises(ProviderError) as exc:
        call(llm)
    return exc.value.kind, str(exc.value)


# --- the request and the answer ---------------------------------------------

def test_a_messages_request_with_the_key_from_the_environment(key):
    llm, sent = client(message("hi"))
    llm.complete("say hi")
    request = sent.requests[0]
    assert request["url"] == "https://api.anthropic.com/v1/messages"
    assert request["headers"]["x-api-key"] == KEY
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["body"] == {"model": "claude-sonnet-5-5", "max_tokens": 8000,
                               "messages": [{"role": "user", "content": "say hi"}]}


def test_the_answer_gives_text_model_and_tokens(key):
    body = {"model": "claude-sonnet-5-5", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
            "usage": {"input_tokens": 120, "output_tokens": 40}}
    llm, _ = client(HttpResponse(200, json.dumps(body).encode()))
    answer = llm.complete("p")
    assert (answer.text, answer.model, answer.input_tokens, answer.output_tokens) == (
        "ab", "claude-sonnet-5-5", 120, 40)


def test_model_size_and_address_are_settings(key, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gateway.example/")
    llm, sent = client(message("x"), model="claude-haiku-5-5", max_tokens=500, temperature=0.7)
    llm.complete("p")
    assert sent.requests[0]["url"] == "https://gateway.example/v1/messages"
    body = sent.requests[0]["body"]
    assert (body["model"], body["max_tokens"], body["temperature"]) == ("claude-haiku-5-5", 500, 0.7)


def test_complete_as_validates_and_records_tokens_and_model(key):
    llm, _ = client(message('{"text": "hello"}', tokens=(30, 4)))
    assert llm.complete_as("p", Greeting) == Greeting(text="hello")
    call = llm.calls[0]
    assert call.ok and call.model == "claude-sonnet-5-5"
    assert (call.input_tokens, call.output_tokens, call.retries) == (30, 4, 0)


# --- setup: fix the settings ------------------------------------------------

def test_no_key_is_a_setup_error(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="LLM_API_KEY") as exc:
        AnthropicLLM(transport=Transport())
    assert exc.value.kind == "setup"


def test_the_key_comes_only_from_llm_api_key(monkeypatch):
    """The team's rule (pipeline/README.md): not from the Anthropic SDK's own variable."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    with pytest.raises(ProviderError, match="LLM_API_KEY"):
        AnthropicLLM(transport=Transport())


@pytest.mark.parametrize("status, kind", [(401, "authentication_error"), (402, "billing_error"),
                                          (403, "permission_error"), (404, "not_found_error")])
def test_key_billing_and_model_errors_are_setup(key, status, kind):
    llm, _ = client(error(status, kind))
    assert kind_of(llm)[0] == "setup"


def test_a_low_credit_balance_is_setup_not_refused(key):
    llm, _ = client(error(400, text="Your credit balance is too low to access the API."))
    assert kind_of(llm)[0] == "setup"


def test_the_key_never_appears_in_an_error(key):
    llm, _ = client(error(401, "authentication_error", f"invalid x-api-key {KEY}"))
    kind, text = kind_of(llm)
    assert KEY not in text and "[redacted]" in text
    assert KEY not in repr(llm)


def test_an_unreachable_service_is_setup(key):
    llm, _ = client(urllib.error.URLError(ConnectionRefusedError("refused")))
    kind, text = kind_of(llm)
    assert kind == "setup" and "Could not reach" in text


def test_a_cut_off_answer_names_max_tokens_instead_of_using_the_retry(key):
    llm, sent = client(message('{"text": "hel', stop="max_tokens"))
    kind, text = kind_of(llm, lambda llm: llm.complete_as("p", Greeting))
    assert kind == "setup" and "max_tokens=8000" in text
    assert len(sent.requests) == 1


# --- refused: change the request --------------------------------------------

@pytest.mark.parametrize("status", [400, 413])
def test_a_request_the_api_refuses_is_refused(key, status):
    llm, _ = client(error(status, text="prompt is too long"))
    kind, text = kind_of(llm)
    assert kind == "refused" and "prompt is too long" in text


def test_a_refusal_by_the_model_is_refused(key):
    llm, _ = client(message("", stop="refusal"))
    assert kind_of(llm)[0] == "refused"


# --- retry: try again later, after one wait for 429 and 529 ----------------

def test_a_rate_limit_waits_once_as_long_as_asked_then_succeeds(key):
    waits = Waits()
    llm, sent = client(error(429, "rate_limit_error", headers={"Retry-After": "3"}),
                       message("ok"), wait=waits)
    assert llm.complete("p").text == "ok"
    assert waits.seconds == [3.0] and len(sent.requests) == 2


def test_overloaded_waits_the_default_without_retry_after(key):
    waits = Waits()
    llm, _ = client(error(529, "overloaded_error"), message("ok"), wait=waits)
    assert llm.complete("p").text == "ok"
    assert waits.seconds == [10.0]


def test_a_second_rate_limit_is_a_retry_error_after_one_wait(key):
    waits = Waits()
    llm, sent = client(error(429, "rate_limit_error"), error(429, "rate_limit_error"), wait=waits)
    kind, text = kind_of(llm)
    assert kind == "retry" and "rate limit" in text
    assert len(waits.seconds) == 1 and len(sent.requests) == 2


def test_a_long_retry_after_is_not_waited_for(key):
    waits = Waits()
    llm, _ = client(error(429, "rate_limit_error", headers={"retry-after": "120"}), wait=waits)
    assert kind_of(llm)[0] == "retry" and waits.seconds == []


@pytest.mark.parametrize("status", [500, 504])
def test_server_errors_are_retry_without_waiting(key, status):
    waits = Waits()
    llm, _ = client(error(status, "api_error"), wait=waits)
    assert kind_of(llm)[0] == "retry" and waits.seconds == []


@pytest.mark.parametrize("failure", [TimeoutError("timed out"),
                                     urllib.error.URLError(TimeoutError("timed out"))])
def test_a_timeout_is_retry(key, failure):
    llm, _ = client(failure)
    kind, text = kind_of(llm)
    assert kind == "retry" and "did not answer" in text


def test_a_dropped_connection_is_retry(key):
    llm, _ = client(ConnectionResetError("reset"))
    assert kind_of(llm)[0] == "retry"


def test_an_empty_answer_is_retry(key):
    llm, _ = client(message("   "))
    assert kind_of(llm)[0] == "retry"


# --- cancelled --------------------------------------------------------------

def test_cancel_stops_the_next_call_before_it_is_sent(key):
    llm, sent = client(message('{"text": "x"}'))
    llm.cancel()
    assert kind_of(llm, lambda llm: llm.complete_as("p", Greeting))[0] == "cancelled"
    assert sent.requests == []


def test_cancel_during_the_wait_stops_the_retry(key):
    llm, sent = client(error(529, "overloaded_error"), message("x"), wait=Waits(cancelled=True))
    assert kind_of(llm)[0] == "cancelled"
    assert len(sent.requests) == 1


# --- every call is recorded -------------------------------------------------

def test_a_provider_error_is_recorded_as_a_failed_call(key):
    llm, _ = client(error(401, "authentication_error"))
    with pytest.raises(ProviderError):
        llm.complete_as("p", Greeting)
    call = llm.calls[0]
    assert not call.ok and "rejected the API key" in call.error
    assert call.attempts[0].prompt == "p" and call.attempts[0].answer is None


def test_each_attempt_keeps_its_prompt_answer_and_error():
    fake = FakeLLM([{"wrong": 1}, {"text": "hi"}])
    fake.complete_as("p", Greeting)
    first, second = fake.calls[0].attempts
    assert first.prompt == "p" and '"wrong"' in first.answer
    assert "text: Field required" in first.error
    assert second.prompt.startswith("p\n\nYour previous answer was not valid")
    assert second.error is None


def test_the_chain_reports_a_provider_error_with_its_stage(key, run_request):
    llm, _ = client(error(529, "overloaded_error"), error(529, "overloaded_error"))
    with pytest.raises(ChainError) as exc:
        run_chain(run_request, llm=llm)
    assert exc.value.stage == "personas" and exc.value.kind == "llm"
    assert "overloaded" in str(exc.value)
    line = exc.value.trace[-1]
    assert (line.stage, line.kind, line.ok) == ("personas", "llm", False)


# --- choosing a provider and model ------------------------------------------

def test_create_llm_defaults_to_anthropic_and_sonnet(key):
    llm = create_llm(transport=Transport())
    assert isinstance(llm, AnthropicLLM) and llm.model == "claude-sonnet-5-5"


def test_create_llm_reads_provider_and_model_from_the_environment(key, monkeypatch):
    monkeypatch.setenv("AMEXIO_LLM_MODEL", "claude-opus-5-5")
    assert create_llm(transport=Transport()).model == "claude-opus-5-5"
    monkeypatch.setenv("AMEXIO_LLM_PROVIDER", "fake")
    assert isinstance(create_llm(), FakeLLM)


def test_an_unknown_provider_is_a_setup_error(key):
    with pytest.raises(ProviderError, match="Unknown LLM provider") as exc:
        create_llm("gemini")
    assert exc.value.kind == "setup"
