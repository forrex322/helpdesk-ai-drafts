import json

import anthropic
import httpx2
import pytest

from knowledge_base.models import Article
from tickets.llm import AnthropicDraftWriter


class Recorder:
    """A fake Anthropic API: records requests and answers with a canned response."""

    def __init__(self, status=200, body=None, error=None):
        self.status = status
        self.body = body
        self.error = error
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return httpx2.Response(self.status, json=self.body or {})


def message_response(text, stop_reason="end_turn"):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def uniform(self, low, high):
        assert (low, high) == (5, 30)
        return self.value


def make_writer(api, api_key="sk-test", time=None, random=None):
    time = time or FakeTime()
    return AnthropicDraftWriter(
        api_key=api_key,
        model="claude-sonnet-5-5",
        timeout=60,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api)),
        sleep=time.sleep,
        monotonic=time.monotonic,
        random=random or FixedRandom(12.0),
    )


@pytest.fixture
def pdf_article(db, settings):
    settings.PUBLIC_BASE_URL = "https://zvitnyk.test"
    return Article.objects.get(slug="export-pdf")


def test_returns_the_models_draft(pdf_article):
    api = Recorder(body=message_response("Добрий день! Відкрийте звіт..."))

    draft = make_writer(api).write_draft("Не можу експортувати звіт у PDF", [pdf_article])

    assert draft == "Добрий день! Відкрийте звіт..."


def test_sends_the_message_and_articles_with_links_to_the_configured_model(pdf_article):
    api = Recorder(body=message_response("ok"))

    make_writer(api).write_draft("Не можу експортувати звіт у PDF", [pdf_article])

    [request] = api.requests
    body = json.loads(request.content)
    assert request.url.path == "/v1/messages"
    assert request.headers["authorization"] == "Bearer sk-test"
    assert body["model"] == "claude-sonnet-5-5"
    prompt = json.dumps(body, ensure_ascii=False)
    assert "Не можу експортувати звіт у PDF" in prompt
    assert "https://zvitnyk.test/kb/export-pdf/" in prompt
    assert pdf_article.title in prompt


def test_provider_errors_surface_without_sdk_retries(pdf_article):
    api = Recorder(status=500, body={"type": "error", "error": {"type": "api_error", "message": "boom"}})

    with pytest.raises(anthropic.InternalServerError):
        make_writer(api).write_draft("Питання", [pdf_article])
    assert len(api.requests) == 1, "retries belong to the job queue, not the SDK"


def test_refusal_is_an_error_not_a_draft(pdf_article):
    api = Recorder(body=message_response("", stop_reason="refusal"))

    with pytest.raises(RuntimeError, match="refus"):
        make_writer(api).write_draft("Питання", [pdf_article])


def test_without_api_key_still_calls_the_provider_then_returns_a_static_draft_with_links(pdf_article):
    api = Recorder(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})

    draft = make_writer(api, api_key="").write_draft("Не можу експортувати звіт у PDF", [pdf_article])

    assert len(api.requests) == 1
    assert api.requests[0].url.path == "/v1/messages"
    assert pdf_article.title in draft
    assert "https://zvitnyk.test/kb/export-pdf/" in draft


def test_without_api_key_the_call_takes_between_5_and_30_seconds_in_total(pdf_article):
    time = FakeTime()
    api = Recorder(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "no"}})

    def slow_api(request):
        time.now += 0.5  # the real round trip
        return api(request)

    make_writer(slow_api, api_key="", time=time, random=FixedRandom(12.0)).write_draft("Питання", [pdf_article])

    assert time.slept == [pytest.approx(11.5)]


def test_without_api_key_works_even_if_the_provider_is_unreachable(pdf_article):
    api = Recorder(error=httpx2.ConnectError("no route to host"))

    draft = make_writer(api, api_key="").write_draft("Питання", [pdf_article])

    assert pdf_article.title in draft


def test_without_api_key_and_without_articles_the_static_draft_escalates(db):
    api = Recorder(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "no"}})

    draft = make_writer(api, api_key="").write_draft("Яка погода?", [])

    assert "фахів" in draft
    assert "http" not in draft
