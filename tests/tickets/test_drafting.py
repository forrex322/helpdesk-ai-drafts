import threading
from collections import Counter

import pytest
from django.db import connection

from tests.conftest import FakeDraftWriter, make_event, post_event, ticket_page
from apps.tickets.worker import DRAFT_MAX_ATTEMPTS, Worker


class SimulatedCrash(BaseException):
    """Escapes run_once like a killed process would: nothing gets to clean up."""


def test_worker_drafts_a_new_ticket_citing_relevant_articles(db, client, operator_client, clock):
    post_event(client, make_event(message="Не можу експортувати звіт у PDF"))

    did_work = Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()

    assert did_work
    page = ticket_page(operator_client, "evt_8f2a")
    assert "Чекає модерації" in page
    assert "Чернетка для: Не можу експортувати звіт у PDF" in page
    assert "Як експортувати звіт у PDF" in page
    assert "http://testserver-public/kb/export-pdf/" in page


@pytest.fixture(autouse=True)
def public_base_url(settings):
    settings.PUBLIC_BASE_URL = "http://testserver-public"


def test_llm_receives_the_message_and_found_articles(db, client, clock):
    writer = FakeDraftWriter()
    post_event(client, make_event(message="Не можу експортувати звіт у PDF"))

    Worker(draft_writer=writer, now=clock).run_once()

    [(message, article_slugs)] = writer.calls
    assert message == "Не можу експортувати звіт у PDF"
    assert article_slugs[0] == "export-pdf"


def test_worker_has_nothing_to_do_without_new_tickets(db, clock):
    assert Worker(draft_writer=FakeDraftWriter(), now=clock).run_once() is False


def test_failed_llm_call_is_retried_after_a_backoff(db, client, operator_client, clock):
    writer = FakeDraftWriter(fail_times=1)
    worker = Worker(draft_writer=writer, now=clock)
    post_event(client, make_event())

    worker.run_once()
    page = ticket_page(operator_client, "evt_8f2a")
    assert "Нове" in page
    assert "LLM is down" in page

    assert worker.run_once() is False, "retry must wait for the backoff"
    clock.advance(seconds=10)
    assert worker.run_once() is True
    assert "Чекає модерації" in ticket_page(operator_client, "evt_8f2a")


def test_ticket_is_marked_failed_after_too_many_llm_failures(db, client, operator_client, clock):
    worker = Worker(draft_writer=FakeDraftWriter(fail_times=100), now=clock)
    post_event(client, make_event())

    for _ in range(DRAFT_MAX_ATTEMPTS):
        worker.run_once()
        clock.advance(minutes=10)

    assert worker.run_once() is False
    page = ticket_page(operator_client, "evt_8f2a")
    assert "Помилка генерації" in page
    assert "LLM is down" in page


def test_ticket_of_a_crashed_worker_is_picked_up_after_its_lease_expires(db, client, operator_client, clock):
    post_event(client, make_event())

    def crash():
        raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        Worker(draft_writer=FakeDraftWriter(on_call=crash), now=clock).run_once()
    survivor = Worker(draft_writer=FakeDraftWriter(), now=clock)

    assert survivor.run_once() is False, "the lease is still held"
    clock.advance(minutes=6)
    assert survivor.run_once() is True
    assert "Чекає модерації" in ticket_page(operator_client, "evt_8f2a")


def test_worker_that_lost_its_lease_cannot_overwrite_the_new_owners_draft(db, client, operator_client, clock):
    post_event(client, make_event(message="Не можу експортувати звіт у PDF"))

    class LateWriter(FakeDraftWriter):
        def write_draft(self, message, articles):
            # While this worker is stuck, its lease expires and another worker finishes the job.
            clock.advance(minutes=6)
            Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()
            return "Застаріла чернетка"

    Worker(draft_writer=LateWriter(), now=clock).run_once()

    page = ticket_page(operator_client, "evt_8f2a")
    assert "Чернетка для: Не можу експортувати звіт у PDF" in page
    assert "Застаріла чернетка" not in page


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_draft_each_ticket_exactly_once(client):
    for i in range(20):
        post_event(client, make_event(event_id=f"evt_{i}", message=f"Питання {i}"))
    drafted = Counter()
    lock = threading.Lock()

    class CountingWriter(FakeDraftWriter):
        def write_draft(self, message, articles):
            with lock:
                drafted[message] += 1
            return super().write_draft(message, articles)

    def work():
        try:
            worker = Worker(draft_writer=CountingWriter())
            while worker.run_once():
                pass
        finally:
            connection.close()

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert drafted == Counter({f"Питання {i}": 1 for i in range(20)})
