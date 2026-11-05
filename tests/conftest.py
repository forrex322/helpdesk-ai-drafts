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


class FakeClock:
    """A controllable `now()` for the worker; starts at the real time of its first use."""

    def __init__(self):
        self.current = None

    def __call__(self):
        if self.current is None:
            from django.utils import timezone

            self.current = timezone.now()
        return self.current

    def advance(self, **delta):
        from datetime import timedelta

        self.current = self() + timedelta(**delta)


class FakeDraftWriter:
    """Stands in for the LLM adapter: returns a predictable Draft or fails on demand."""

    def __init__(self, fail_times=0, on_call=None):
        self.fail_times = fail_times
        self.on_call = on_call
        self.calls = []

    def write_draft(self, message, articles):
        self.calls.append((message, [article.slug for article in articles]))
        if self.on_call:
            self.on_call()
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("LLM is down")
        return f"Чернетка для: {message}"


@pytest.fixture
def clock():
    return FakeClock()


def ticket_page(operator_client, event_id):
    from tickets.models import Ticket

    return operator_client.get(f"/tickets/{Ticket.objects.get(event_id=event_id).pk}/").content.decode()
