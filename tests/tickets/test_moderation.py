import threading

import httpx
import pytest
from django.db import connection
from django.test import Client

from tests.conftest import FakeDraftWriter, make_event, post_event, ticket_page, ticket_path
from apps.tickets.adapters.helpdesk import HelpdeskClient
from apps.tickets.worker import DRAFT_MAX_ATTEMPTS, Worker


class RejectingHelpdesk(httpx.BaseTransport):
    def handle_request(self, request):
        return httpx.Response(422)


@pytest.fixture
def drafted_ticket(db, client, clock):
    post_event(client, make_event())
    Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()
    return ticket_path()


def test_operator_approves_an_edited_draft(operator_client, drafted_ticket):
    response = operator_client.post(f"{drafted_ticket}/approve", {"reply": "Виправлений текст відповіді"}, follow=True)

    page = response.content.decode()
    assert "Відповідь підтверджено" in page
    assert "Підтверджено, в черзі" in page
    assert "Виправлений текст відповіді" in page
    assert "operator" in page


def test_operator_rejects_a_draft(operator_client, drafted_ticket):
    page = operator_client.post(f"{drafted_ticket}/reject", follow=True).content.decode()

    assert "Відхилено" in page
    assert "Підтвердити" not in page


def test_second_approval_changes_nothing_and_says_so(operator_client, drafted_ticket):
    operator_client.post(f"{drafted_ticket}/approve", {"reply": "Перша версія"})

    page = operator_client.post(f"{drafted_ticket}/approve", {"reply": "Друга версія"}, follow=True).content.decode()

    assert "вже оброблено" in page
    assert "Перша версія" in page
    assert "Друга версія" not in page


def test_rejected_ticket_cannot_be_approved(operator_client, drafted_ticket):
    operator_client.post(f"{drafted_ticket}/reject")

    page = operator_client.post(f"{drafted_ticket}/approve", {"reply": "Текст"}, follow=True).content.decode()

    assert "вже оброблено" in page
    assert "Відхилено" in page


def test_ticket_without_a_draft_cannot_be_approved(db, client, operator_client):
    post_event(client, make_event())

    page = operator_client.post(f"{ticket_path()}/approve", {"reply": "Текст"}, follow=True).content.decode()

    assert "вже оброблено" in page
    assert "Нове" in page


def test_empty_reply_is_not_approved(operator_client, drafted_ticket):
    page = operator_client.post(f"{drafted_ticket}/approve", {"reply": "   "}, follow=True).content.decode()

    assert "не може бути порожньою" in page
    assert "Чекає модерації" in page


def test_moderation_requires_login_and_post(drafted_ticket, operator_client):
    assert Client().post(f"{drafted_ticket}/approve", {"reply": "x"}).status_code == 302
    assert operator_client.get(f"{drafted_ticket}/approve").status_code == 405
    assert "Чекає модерації" in operator_client.get(f"{drafted_ticket}/").content.decode()


def test_operator_retries_a_ticket_whose_drafting_failed(db, client, operator_client, clock):
    post_event(client, make_event())
    failing = Worker(draft_writer=FakeDraftWriter(fail_times=100), now=clock)
    for _ in range(DRAFT_MAX_ATTEMPTS):
        failing.run_once()
        clock.advance(minutes=10)
    assert "Помилка генерації" in ticket_page(operator_client)

    page = operator_client.post(f"{ticket_path()}/retry", follow=True).content.decode()

    assert "Нове" in page
    clock.advance(seconds=1)
    assert Worker(draft_writer=FakeDraftWriter(), now=clock).run_once() is True
    assert "Чекає модерації" in ticket_page(operator_client)


def test_operator_retries_a_ticket_whose_delivery_failed(operator_client, drafted_ticket, clock):
    operator_client.post(f"{drafted_ticket}/approve", {"reply": "Текст"})
    clock.advance(seconds=1)
    Worker(draft_writer=FakeDraftWriter(), now=clock, helpdesk=HelpdeskClient(timeout=10, transport=RejectingHelpdesk())).run_once()
    assert "Помилка надсилання" in ticket_page(operator_client)

    page = operator_client.post(f"{drafted_ticket}/retry", follow=True).content.decode()

    assert "Підтверджено, в черзі" in page


@pytest.mark.django_db(transaction=True)
def test_two_operators_approving_at_once_produce_one_reply(django_user_model):
    seed = Client()
    post_event(seed, make_event())
    Worker(draft_writer=FakeDraftWriter()).run_once()
    url = ticket_path()
    operators = [django_user_model.objects.create_user(username=f"op{i}", password="x") for i in range(8)]
    barrier = threading.Barrier(len(operators))
    outcomes = []

    def approve(operator):
        client = Client()
        client.force_login(operator)
        barrier.wait()
        try:
            page = client.post(f"{url}/approve", {"reply": f"Відповідь від {operator.username}"}, follow=True)
            outcomes.append("Відповідь підтверджено" in page.content.decode())
        finally:
            connection.close()

    threads = [threading.Thread(target=approve, args=(operator,)) for operator in operators]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count(True) == 1
