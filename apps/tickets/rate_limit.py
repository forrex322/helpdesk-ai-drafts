"""The LLM rate limit shared by every worker thread and replica (ADR-0003).

Call starts are logged in Postgres; a transaction-scoped advisory lock makes
"count the last window, then record a start" atomic across processes, and the
database clock is the one clock every replica agrees on.
"""

import random
import time
import zlib
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Min

from .models import RateLimitHit

LOCK_KEY = zlib.crc32(b"rate-limit:llm")
# Waits are chopped into short sleeps so `on_wait` (lease renewal) runs often.
MAX_SLEEP_SECONDS = 30


class SlidingWindowRateLimiter:
    def __init__(self, limit, window=timedelta(seconds=60), now=None, sleep=time.sleep):
        self.limit = limit
        self.window = window
        self.now = now  # None: use the database clock
        self.sleep = sleep

    def try_acquire(self) -> float:
        """Record a call start and return 0, or return the seconds until a slot frees up."""
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
                if self.now is None:
                    cursor.execute("SELECT clock_timestamp()")
                    [now] = cursor.fetchone()
                else:
                    now = self.now()
            window_start = now - self.window
            RateLimitHit.objects.filter(at__lte=window_start).delete()
            recent = RateLimitHit.objects.aggregate(count=Count("id"), oldest=Min("at"))
            if recent["count"] < self.limit:
                RateLimitHit.objects.create(at=now)
                return 0.0
            return (recent["oldest"] + self.window - now).total_seconds()

    def acquire(self, on_wait=None):
        """Block until a call may start, calling `on_wait` before each wait."""
        while (wait := self.try_acquire()) > 0:
            if on_wait:
                on_wait()
            # Jitter keeps waiting threads from stampeding the same freed slot.
            self.sleep(min(wait, MAX_SLEEP_SECONDS) + random.uniform(0, 0.5))


def llm_rate_limiter_from_settings(sleep=time.sleep):
    return SlidingWindowRateLimiter(limit=settings.LLM_RATE_LIMIT_PER_MINUTE, sleep=sleep)
