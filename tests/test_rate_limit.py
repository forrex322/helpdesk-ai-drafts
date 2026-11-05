import threading
from datetime import timedelta

import pytest
from django.db import connection

from tests.conftest import FakeDraftWriter, make_event, post_event, ticket_page
from tickets.rate_limit import SlidingWindowRateLimiter
from tickets.worker import ShuttingDown, Worker


def test_worker_starts_at_most_the_allowed_number_of_llm_calls_per_minute(db, client, clock):
    started_at = []

    class TimedWriter(FakeDraftWriter):
        def write_draft(self, message, articles):
            started_at.append(clock())
            return super().write_draft(message, articles)

    for i in range(7):
        post_event(client, make_event(event_id=f"evt_{i}"))
    limiter = SlidingWindowRateLimiter(limit=3, now=clock, sleep=clock.sleep)
    worker = Worker(draft_writer=TimedWriter(), now=clock, rate_limiter=limiter)

    while worker.run_once():
        clock.advance(seconds=1)

    assert len(started_at) == 7
    for first in started_at:
        in_window = [t for t in started_at if first <= t < first + timedelta(seconds=60)]
        assert len(in_window) <= 3
    assert started_at[3] - started_at[0] >= timedelta(seconds=60)


def test_waiting_caller_learns_when_the_next_slot_frees_up(db, clock):
    limiter = SlidingWindowRateLimiter(limit=2, now=clock)
    limiter.try_acquire()
    clock.advance(seconds=20)
    limiter.try_acquire()
    clock.advance(seconds=5)

    assert limiter.try_acquire() == pytest.approx(35)
    clock.advance(seconds=35)
    assert limiter.try_acquire() == 0


def test_separate_limiters_share_one_budget_like_worker_replicas_do(db, clock):
    replica_a = SlidingWindowRateLimiter(limit=2, now=clock)
    replica_b = SlidingWindowRateLimiter(limit=2, now=clock)

    assert replica_a.try_acquire() == 0
    assert replica_b.try_acquire() == 0
    assert replica_a.try_acquire() > 0
    assert replica_b.try_acquire() > 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_callers_never_exceed_the_limit():
    limiter = SlidingWindowRateLimiter(limit=5)
    barrier = threading.Barrier(12)
    granted = []

    def call():
        barrier.wait()
        try:
            granted.append(limiter.try_acquire() == 0)
        finally:
            connection.close()

    threads = [threading.Thread(target=call) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert granted.count(True) == 5


def test_ticket_waiting_long_for_an_llm_slot_is_not_taken_over_by_another_worker(db, client, clock):
    post_event(client, make_event(event_id="evt_first"))
    post_event(client, make_event(event_id="evt_second"))
    llm = FakeDraftWriter()
    rival = Worker(draft_writer=llm, now=clock, rate_limiter=SlidingWindowRateLimiter(limit=100, now=clock))

    def sleep_while_a_rival_looks_for_work(seconds):
        clock.sleep(seconds)
        rival.run_once()

    # One call per 10 minutes: the second Ticket waits twice as long as the lease.
    limiter = SlidingWindowRateLimiter(
        limit=1, window=timedelta(minutes=10), now=clock, sleep=sleep_while_a_rival_looks_for_work
    )
    worker = Worker(draft_writer=llm, now=clock, rate_limiter=limiter)

    worker.run_once()
    worker.run_once()

    assert len(llm.calls) == 2, "a taken-over Ticket costs a second LLM call"


def test_stopping_worker_puts_a_ticket_waiting_for_an_llm_slot_back_in_the_queue(db, client, operator_client, clock):
    post_event(client, make_event(event_id="evt_first"))
    post_event(client, make_event(event_id="evt_second"))

    def stop_requested(seconds):
        raise ShuttingDown

    limiter = SlidingWindowRateLimiter(limit=1, now=clock, sleep=stop_requested)
    worker = Worker(draft_writer=FakeDraftWriter(), now=clock, rate_limiter=limiter)
    worker.run_once()

    with pytest.raises(ShuttingDown):
        worker.run_once()

    page = ticket_page(operator_client, "evt_second")
    assert "Нове" in page
    assert "<th>Спроб</th><td>0</td>" in page
