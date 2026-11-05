import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection

from apps.tickets.adapters.llm import draft_writer_from_settings
from apps.tickets.rate_limit import llm_rate_limiter_from_settings
from apps.tickets.worker import ShuttingDown, Worker

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the background worker that drafts and delivers Replies."

    def add_arguments(self, parser):
        parser.add_argument("--threads", type=int, default=settings.WORKER_THREADS)
        parser.add_argument("--idle-sleep", type=float, default=1.0, help="Seconds to wait when the queue is empty.")

    def handle(self, *args, threads, idle_sleep, **options):
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())

        def sleep_unless_stopping(seconds):
            if stop.wait(seconds):
                raise ShuttingDown

        worker = Worker(
            draft_writer=draft_writer_from_settings(),
            rate_limiter=llm_rate_limiter_from_settings(sleep=sleep_unless_stopping),
        )

        def loop():
            try:
                while not stop.is_set():
                    close_old_connections()
                    try:
                        did_work = worker.run_once()
                    except ShuttingDown:
                        break
                    except Exception:
                        logger.exception("Worker step failed")
                        did_work = False
                    if not did_work:
                        stop.wait(idle_sleep)
            finally:
                connection.close()

        pool = [threading.Thread(target=loop, name=f"worker-{i}") for i in range(threads)]
        for thread in pool:
            thread.start()
        mode = "stub (no ANTHROPIC_API_KEY)" if settings.LLM_STUB_MODE else settings.LLM_MODEL
        logger.info("Worker started: %s threads, LLM: %s", threads, mode)

        stop.wait()
        logger.info("Stopping: in-flight calls finish, Tickets waiting for an LLM slot go back to the queue")
        for thread in pool:
            thread.join()
        logger.info("Worker stopped")
