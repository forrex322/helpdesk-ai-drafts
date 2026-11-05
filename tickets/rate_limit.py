"""A rate limit shared by every worker thread and replica (ADR-0003).

Call starts are logged in Postgres; a transaction-scoped advisory lock makes
"count the last window, then record a start" atomic across processes.
"""

import random
import time
import zlib
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Min
from django.utils import timezone

from .models import RateLimitHit


class SlidingWindowRateLimiter:
    def __init__(self, limit, window=timedelta(seconds=60), bucket="llm", now=timezone.now, sleep=time.sleep):
        self.limit = limit
        self.window = window
        self.bucket = bucket
        self.lock_key = zlib.crc32(f"rate-limit:{bucket}".encode())
        self.now = now
        self.sleep = sleep

    def try_acquire(self) -> float:
        """Record a call start and return 0, or return the seconds until a slot frees up."""
        now = self.now()
        window_start = now - self.window
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [self.lock_key])
            hits = RateLimitHit.objects.filter(bucket=self.bucket)
            hits.filter(at__lte=window_start).delete()
            recent = hits.filter(at__gt=window_start).aggregate(count=Count("id"), oldest=Min("at"))
            if recent["count"] < self.limit:
                RateLimitHit.objects.create(bucket=self.bucket, at=now)
                return 0.0
            return (recent["oldest"] + self.window - now).total_seconds()

    def acquire(self):
        """Block until a call may start."""
        while (wait := self.try_acquire()) > 0:
            # Jitter keeps waiting threads from stampeding the same freed slot.
            self.sleep(wait + random.uniform(0, 0.5))


def llm_rate_limiter_from_settings():
    return SlidingWindowRateLimiter(limit=settings.LLM_RATE_LIMIT_PER_MINUTE)
