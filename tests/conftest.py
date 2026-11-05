import pytest


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_user(username="operator", password="pass")


@pytest.fixture
def operator_client(client, operator):
    client.force_login(operator)
    return client


def make_event(**overrides):
    event = {
        "event_id": "evt_8f2a",
        "ticket_id": "T-1042",
        "customer_email": "user@example.com",
        "message": "Не можу експортувати звіт у PDF",
        "reply_url": "https://helpdesk.example.com/tickets/T-1042/replies",
    }
    event.update(overrides)
    return event


def post_event(client, event):
    return client.post("/webhooks/helpdesk", data=event, content_type="application/json")
