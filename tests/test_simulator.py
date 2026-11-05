import pytest
from django.core.management import call_command
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_simulator_delivers_unique_events_once_and_redelivers_duplicates(live_server, django_user_model, capsys):
    call_command(
        "simulate_webhooks",
        base_url=live_server.url,
        reply_base_url="http://web:8000",
        count=12,
        duplicate_rate=0.5,
        concurrency=6,
    )

    out = capsys.readouterr().out
    assert "accepted (new Tickets):   12" in out
    assert "errors:                   0" in out
    operator = django_user_model.objects.create_user(username="op", password="x")
    client = Client()
    client.force_login(operator)
    assert client.get("/tickets/").content.decode().count('data-event-id="sim_') == 12
