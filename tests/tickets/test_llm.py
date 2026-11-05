import json
import random as random_module

import anthropic
import httpx2
import pytest

from apps.knowledge_base.models import Article
from apps.tickets.adapters.llm import AnthropicDraftWriter


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


def make_writer(api, api_key="sk-test", time=None, random=random_module.Random(0)):
    time = time or FakeTime()
    return AnthropicDraftWriter(
        api_key=api_key,
        model="claude-sonnet-5-5",
        timeout=60,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api)),
        sleep=time.sleep,
        monotonic=time.monotonic,
        random=random,
    )


@pytest.fixture
def pdf_article(db, settings):
    settings.PUBLIC_BASE_URL = "https://zvitnyk.test"
    return Article.objects.get(slug="export-pdf")


def test_returns_the_models_draft(pdf_article):
    api = Recorder(body=message_response("Добрий день! Відкрийте звіт... https://zvitnyk.test/kb/export-pdf/"))

    draft = make_writer(api).write_draft("Не можу експортувати звіт у PDF", [pdf_article])

    assert draft == "Добрий день! Відкрийте звіт... https://zvitnyk.test/kb/export-pdf/"


def test_draft_always_links_the_cited_articles_even_if_the_model_left_them_out(pdf_article):
    api = Recorder(body=message_response("Добрий день! Відкрийте звіт..."))

    draft = make_writer(api).write_draft("Не можу експортувати звіт у PDF", [pdf_article])

    assert draft.startswith("Добрий день! Відкрийте звіт...")
    assert "https://zvitnyk.test/kb/export-pdf/" in draft


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


@pytest.mark.parametrize("seed", range(20))
def test_without_api_key_the_call_takes_between_5_and_30_seconds_in_total(pdf_article, seed):
    time = FakeTime()
    api = Recorder(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "no"}})

    def slow_api(request):
        time.now += 0.5  # the real round trip
        return api(request)

    started = time.now
    make_writer(slow_api, api_key="", time=time, random=random_module.Random(seed)).write_draft("Питання", [pdf_article])

    assert 5 <= time.now - started <= 30


def test_without_api_key_works_even_if_the_provider_is_unreachable(pdf_article):
    api = Recorder(error=httpx2.ConnectError("no route to host"))

    draft = make_writer(api, api_key="").write_draft("Питання", [pdf_article])

    assert pdf_article.title in draft


def test_without_api_key_and_without_articles_the_static_draft_escalates(db):
    api = Recorder(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "no"}})

    draft = make_writer(api, api_key="").write_draft("Яка погода?", [])

    assert "фахів" in draft
    assert "http" not in draft
