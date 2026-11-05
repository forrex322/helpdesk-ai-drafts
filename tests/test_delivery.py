import json

import httpx
import pytest
from django.test import Client

from tests.conftest import FakeDraftWriter, make_event, post_event, ticket_page
from tickets.helpdesk import HelpdeskClient
from tickets.models import Ticket
from tickets.worker import DELIVERY_MAX_ATTEMPTS, Worker

REPLY_URL = "http://testserver/mock-helpdesk/tickets/T-1042/replies"


class HelpdeskNetwork(httpx.BaseTransport):
    """Routes Deliveries to the mock Helpdesk app in-process, with scripted network trouble.

    Each scripted fault is used once, in order: "503" answers without reaching the
    Helpdesk, "lost" lets the Helpdesk process the request but times out the reply.
    """

    def __init__(self, faults=()):
        # Django's test Client, unlike a raw WSGI call, keeps the test's DB connection open.
        self.helpdesk = Client()
        self.faults = list(faults)
        self.requests = []

    def handle_request(self, request):
        self.requests.append(request)
        fault = self.faults.pop(0) if self.faults else None
        if fault == "503":
            return httpx.Response(503)
        response = self.helpdesk.generic(
            request.method,
            request.url.raw_path.decode(),
            data=request.content,
            content_type=request.headers["Content-Type"],
            headers={"Idempotency-Key": request.headers["Idempotency-Key"]},
        )
        if fault == "lost":
            raise httpx.ReadTimeout("helpdesk did not answer in time", request=request)
        return httpx.Response(response.status_code, content=response.content)


@pytest.fixture(autouse=True)
def reliable_mock_helpdesk(settings):
    settings.MOCK_HELPDESK_FAILURE_RATE = 0
    settings.MOCK_HELPDESK_SLOW_RATE = 0


@pytest.fixture
def approved_ticket(db, client, operator_client, clock):
    post_event(client, make_event(reply_url=REPLY_URL))
    Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()
    pk = Ticket.objects.get(event_id="evt_8f2a").pk
    operator_client.post(f"/tickets/{pk}/approve", {"reply": "Щоб експортувати звіт у PDF, відкрийте..."})
    clock.advance(seconds=1)  # the worker gets to it a moment after the Approval


def delivering_worker(network, clock):
    return Worker(draft_writer=FakeDraftWriter(), now=clock, helpdesk=HelpdeskClient(timeout=10, transport=network))


def received_by_customer(client):
    return client.get("/mock-helpdesk/").content.decode().count("Щоб експортувати звіт у PDF, відкрийте...")


def test_approved_reply_is_delivered_to_the_helpdesk(approved_ticket, client, operator_client, clock):
    network = HelpdeskNetwork()

    assert delivering_worker(network, clock).run_once() is True

    assert "Надіслано" in ticket_page(operator_client, "evt_8f2a")
    assert received_by_customer(client) == 1
    [request] = network.requests
    assert str(request.url) == REPLY_URL
    assert json.loads(request.content) == {"ticket_id": "T-1042", "message": "Щоб експортувати звіт у PDF, відкрийте..."}
    assert request.headers["Idempotency-Key"]


def test_helpdesk_5xx_is_retried_after_a_backoff(approved_ticket, client, operator_client, clock):
    worker = delivering_worker(HelpdeskNetwork(faults=["503"]), clock)

    worker.run_once()
    page = ticket_page(operator_client, "evt_8f2a")
    assert "Підтверджено, в черзі" in page
    assert "503" in page

    assert worker.run_once() is False, "retry must wait for the backoff"
    clock.advance(seconds=10)
    worker.run_once()
    assert "Надіслано" in ticket_page(operator_client, "evt_8f2a")
    assert received_by_customer(client) == 1


def test_reply_stored_before_a_timeout_reaches_the_customer_once(approved_ticket, client, operator_client, clock):
    network = HelpdeskNetwork(faults=["lost", "lost"])
    worker = delivering_worker(network, clock)

    for _ in range(3):
        worker.run_once()
        clock.advance(minutes=1)

    assert "Надіслано" in ticket_page(operator_client, "evt_8f2a")
    assert len(network.requests) == 3
    assert len({request.headers["Idempotency-Key"] for request in network.requests}) == 1
    assert received_by_customer(client) == 1


def test_delivery_gives_up_after_too_many_failures(approved_ticket, client, operator_client, clock):
    worker = delivering_worker(HelpdeskNetwork(faults=["503"] * 100), clock)

    for _ in range(DELIVERY_MAX_ATTEMPTS):
        worker.run_once()
        clock.advance(minutes=10)

    assert worker.run_once() is False
    assert "Помилка надсилання" in ticket_page(operator_client, "evt_8f2a")
    assert received_by_customer(client) == 0


def test_helpdesk_rejecting_the_reply_is_not_retried(approved_ticket, client, operator_client, clock):
    class Rejecting(httpx.BaseTransport):
        def handle_request(self, request):
            return httpx.Response(422, json={"error": "ticket closed"})

    worker = Worker(draft_writer=FakeDraftWriter(), now=clock, helpdesk=HelpdeskClient(timeout=10, transport=Rejecting()))

    worker.run_once()

    page = ticket_page(operator_client, "evt_8f2a")
    assert "Помилка надсилання" in page
    assert "422" in page


def test_unreachable_helpdesk_is_retried(approved_ticket, operator_client, clock):
    class Down(httpx.BaseTransport):
        def handle_request(self, request):
            raise httpx.ConnectError("connection refused", request=request)

    worker = Worker(draft_writer=FakeDraftWriter(), now=clock, helpdesk=HelpdeskClient(timeout=10, transport=Down()))

    worker.run_once()

    page = ticket_page(operator_client, "evt_8f2a")
    assert "Підтверджено, в черзі" in page
    assert "connection refused" in page
