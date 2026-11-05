import threading

import httpx
import pytest
from django.db import connection
from django.test import Client

from mock_helpdesk.simulator import simulate


class WebhookTransport(httpx.BaseTransport):
    """Sends the simulator's requests into the app via Django's test Client."""

    def handle_request(self, request):
        try:
            response = Client().generic(
                request.method,
                request.url.raw_path.decode(),
                data=request.content,
                content_type=request.headers["Content-Type"],
            )
        finally:
            connection.close()
        return httpx.Response(response.status_code, content=response.content)


@pytest.mark.django_db(transaction=True)
def test_simulator_delivers_unique_events_once_and_redelivers_duplicates(django_user_model):
    report = simulate(
        base_url="http://testserver",
        reply_base_url="http://web:8000",
        count=12,
        duplicate_rate=0.5,
        concurrency=6,
        transport=WebhookTransport(),
    )

    assert report.accepted == 12
    assert report.duplicates_acknowledged == report.requests - 12
    assert report.requests > 12
    assert report.errors == 0
    operator = django_user_model.objects.create_user(username="op", password="x")
    client = Client()
    client.force_login(operator)
    assert client.get("/tickets/").content.decode().count('data-event-id="sim_') == 12
