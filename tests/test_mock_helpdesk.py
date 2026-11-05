import json

import pytest


def post_reply(client, ticket_id="T-1042", message="Відповідь", key="key-1", body=None):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client.post(
        f"/mock-helpdesk/tickets/{ticket_id}/replies",
        data=json.dumps(body if body is not None else {"ticket_id": ticket_id, "message": message}),
        content_type="application/json",
        **headers,
    )


def test_accepts_a_reply_and_shows_what_the_customer_received(db, client, reliable_mock_helpdesk):
    response = post_reply(client, message="Щоб експортувати звіт у PDF, відкрийте...")

    assert response.status_code == 201
    page = client.get("/mock-helpdesk/").content.decode()
    assert "T-1042" in page
    assert "Щоб експортувати звіт у PDF, відкрийте..." in page


def test_repeated_idempotency_key_is_acknowledged_but_not_received_twice(db, client, reliable_mock_helpdesk):
    post_reply(client, message="Одна відповідь", key="same-key")

    response = post_reply(client, message="Одна відповідь", key="same-key")

    assert response.status_code == 201
    page = client.get("/mock-helpdesk/").content.decode()
    assert page.count("Одна відповідь") == 1
    assert 'data-duplicates="1"' in page


def test_failing_helpdesk_answers_5xx_and_stores_nothing(db, client, settings):
    settings.MOCK_HELPDESK_FAILURE_RATE = 1

    response = post_reply(client, message="Загублена відповідь")

    assert response.status_code == 503
    assert "Загублена відповідь" not in client.get("/mock-helpdesk/").content.decode()


def test_slow_helpdesk_stores_the_reply_before_answering_late(db, client, settings):
    settings.MOCK_HELPDESK_FAILURE_RATE = 0
    settings.MOCK_HELPDESK_SLOW_RATE = 1
    settings.MOCK_HELPDESK_SLOW_SECONDS = 0

    response = post_reply(client, message="Повільна відповідь")

    assert response.status_code == 201
    assert "Повільна відповідь" in client.get("/mock-helpdesk/").content.decode()


def test_malformed_reply_is_rejected(db, client, reliable_mock_helpdesk):
    assert post_reply(client, body={"message": ""}).status_code == 400
