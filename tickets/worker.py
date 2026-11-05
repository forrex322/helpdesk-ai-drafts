"""Background processing of Tickets.

Postgres is the job queue (ADR-0001): a worker claims one due Ticket in a short
`SKIP LOCKED` transaction, takes a time-limited lease on it, does the slow work
outside any transaction, and completes with an update fenced on its `lease_id`
so that a worker whose lease expired cannot overwrite the new owner's result.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.db import transaction
from django.utils import timezone

from knowledge_base.search import search_articles

from .llm import DraftWriter
from .models import Ticket

logger = logging.getLogger(__name__)

S = Ticket.Status

LEASE = timedelta(minutes=5)
DRAFT_MAX_ATTEMPTS = 5
BACKOFF_BASE = timedelta(seconds=10)
BACKOFF_MAX = timedelta(minutes=10)

# Due status -> the in-flight status a claimed Ticket takes. In-flight statuses
# are claimable too: that is how an expired lease gets picked up again.
CLAIMABLE = {
    S.NEW: S.DRAFTING,
    S.DRAFTING: S.DRAFTING,
}


def backoff(attempt):
    return min(BACKOFF_BASE * 2 ** (attempt - 1), BACKOFF_MAX)


@dataclass
class Worker:
    draft_writer: DraftWriter
    now: Callable[[], datetime] = timezone.now

    def run_once(self) -> bool:
        """Process one due Ticket. Returns False when there was nothing to do."""
        ticket = self._claim()
        if ticket is None:
            return False
        self._draft(ticket)
        return True

    def _claim(self):
        now = self.now()
        with transaction.atomic():
            ticket = (
                Ticket.objects.select_for_update(skip_locked=True)
                .filter(status__in=list(CLAIMABLE), available_at__lte=now)
                .order_by("available_at")
                .first()
            )
            if ticket is None:
                return None
            ticket.status = CLAIMABLE[ticket.status]
            ticket.lease_id = uuid.uuid4()
            ticket.available_at = now + LEASE
            ticket.attempts += 1
            ticket.save(update_fields=["status", "lease_id", "available_at", "attempts", "updated_at"])
        return ticket

    def _draft(self, ticket):
        try:
            articles = search_articles(ticket.message)
            draft = self.draft_writer.write_draft(ticket.message, articles)
        except Exception as error:
            logger.warning("Drafting %s failed (attempt %s): %r", ticket, ticket.attempts, error)
            self._retry_or_fail(ticket, error, DRAFT_MAX_ATTEMPTS, retry_as=S.NEW, fail_as=S.DRAFT_FAILED)
            return
        with transaction.atomic():
            if self._complete(ticket, status=S.DRAFT_READY, draft=draft, last_error=""):
                ticket.cited_articles.set(articles)
        logger.info("Drafted %s citing %s", ticket, [article.slug for article in articles])

    def _retry_or_fail(self, ticket, error, max_attempts, retry_as, fail_as):
        last_error = f"{type(error).__name__}: {error}"
        if ticket.attempts >= max_attempts:
            self._complete(ticket, status=fail_as, last_error=last_error)
        else:
            self._complete(
                ticket,
                status=retry_as,
                available_at=self.now() + backoff(ticket.attempts),
                last_error=last_error,
            )

    def _complete(self, ticket, **fields) -> bool:
        """Apply the outcome only if this worker still holds the lease."""
        updated = Ticket.objects.filter(pk=ticket.pk, lease_id=ticket.lease_id).update(
            lease_id=None, updated_at=timezone.now(), **fields
        )
        if not updated:
            logger.warning("Lost the lease on %s; discarding this worker's result", ticket)
        return bool(updated)
