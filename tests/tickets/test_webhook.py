import threading

import pytest
from django.db import connection
from django.test import Client

from tests.conftest import make_event, post_event


def rows_for(page, event_id):
    return page.content.decode().count(f'data-event-id="{event_id}"')


def test_new_event_is_accepted_and_shown_to_operators(db, client, operator_client):
    response = post_event(client, make_event())

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    page = operator_client.get("/tickets/")
    assert rows_for(page, "evt_8f2a") == 1
    assert "T-1042" in page.content.decode()
    assert "user@example.com" in page.content.decode()


def test_redelivered_event_is_acknowledged_without_a_second_ticket(db, client, operator_client):
    post_event(client, make_event())

    response = post_event(client, make_event())

    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}
    assert rows_for(operator_client.get("/tickets/"), "evt_8f2a") == 1


def test_new_event_for_a_known_helpdesk_ticket_is_a_separate_ticket(db, client, operator_client):
    post_event(client, make_event(event_id="evt_1"))
    post_event(client, make_event(event_id="evt_2"))

    page = operator_client.get("/tickets/")
    assert rows_for(page, "evt_1") == 1
    assert rows_for(page, "evt_2") == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_deliveries_of_one_event_create_one_ticket():
    barrier = threading.Barrier(16)
    statuses = []

    def deliver():
        client = Client()
        barrier.wait()
        try:
            response = post_event(client, make_event())
            statuses.append((response.status_code, response.json()["status"]))
        finally:
            connection.close()

    threads = [threading.Thread(target=deliver) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(code == 200 for code, _ in statuses)
    assert sorted(status for _, status in statuses) == ["accepted"] + ["duplicate"] * 15


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "[1, 2]",
        '{"event_id": "evt_1"}',
    ],
)
def test_malformed_body_is_rejected(db, client, operator_client, body):
    response = client.post("/webhooks/helpdesk", data=body, content_type="application/json")

    assert response.status_code == 400
    assert "errors" in response.json()
    assert "data-event-id" not in operator_client.get("/tickets/").content.decode()


@pytest.mark.parametrize(
    "overrides",
    [
        {"reply_url": "ftp://helpdesk.example.com/replies"},
        {"reply_url": "not a url"},
        {"message": ""},
        {"event_id": ""},
    ],
)
def test_invalid_fields_are_rejected(db, client, operator_client, overrides):
    response = post_event(client, make_event(**overrides))

    assert response.status_code == 400
    assert "data-event-id" not in operator_client.get("/tickets/").content.decode()


@pytest.mark.parametrize(
    "overrides",
    [
        {"customer_email": "not-an-email"},
        {"message": "   "},
        {"message": "Не можу\x00 експортувати"},
    ],
    ids=["odd-email", "blank-message", "nul-character"],
)
def test_events_with_imperfect_fields_are_still_accepted_so_no_ticket_is_lost(db, client, operator_client, overrides):
    response = post_event(client, make_event(**overrides))

    assert response.status_code == 200
    assert 'data-event-id="evt_8f2a"' in operator_client.get("/tickets/").content.decode()


def test_reply_url_on_an_internal_host_is_accepted(db, client):
    response = post_event(client, make_event(reply_url="http://web:8000/mock-helpdesk/tickets/T-1042/replies"))

    assert response.status_code == 200


def test_webhook_only_accepts_post(db, client):
    assert client.get("/webhooks/helpdesk").status_code == 405
