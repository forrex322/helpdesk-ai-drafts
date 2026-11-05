import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.mock_helpdesk.simulator import simulate


class Command(BaseCommand):
    help = "Fire Helpdesk Events at the webhook, with redelivered duplicates and concurrency, and report latency."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://localhost:8000", help="Where the webhook lives.")
        parser.add_argument(
            "--reply-base-url",
            default=None,
            help="Base URL the worker will deliver Replies to (the mock Helpdesk). Defaults to SIMULATOR_REPLY_BASE_URL.",
        )
        parser.add_argument("--count", type=int, default=50)
        parser.add_argument("--duplicate-rate", type=float, default=0.3)
        parser.add_argument("--concurrency", type=int, default=20)
        parser.add_argument("--over-seconds", type=float, default=0, help="Spread the Events over this many seconds.")

    def handle(self, *args, base_url, reply_base_url, count, duplicate_rate, concurrency, over_seconds, **options):
        logging.getLogger("httpx").setLevel(logging.WARNING)
        report = simulate(
            base_url=base_url,
            reply_base_url=reply_base_url or settings.SIMULATOR_REPLY_BASE_URL,
            count=count,
            duplicate_rate=duplicate_rate,
            concurrency=concurrency,
            over_seconds=over_seconds,
        )
        self.stdout.write(report.summary())
