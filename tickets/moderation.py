"""Operator decisions on a Ticket.

Each decision is a conditional update from the one status it is valid in, so
a double click or two Operators acting at once change the Ticket only once.
Every function returns False when the Ticket was not in that status anymore.
"""

from django.utils import timezone

from .models import RETRIES, Status, Ticket


def approve(pk, reply, operator) -> bool:
    now = timezone.now()
    return _transition(
        pk,
        Status.DRAFT_READY,
        status=Status.APPROVED,
        reply=reply,
        moderated_by=operator,
        moderated_at=now,
        available_at=now,
        attempts=0,
        last_error="",
    )


def reject(pk, operator) -> bool:
    return _transition(
        pk, Status.DRAFT_READY, status=Status.REJECTED, moderated_by=operator, moderated_at=timezone.now()
    )


def retry(pk) -> bool:
    """Send a Ticket whose drafting or Delivery gave up back into the queue."""
    return any(
        _transition(pk, failed, status=queued, available_at=timezone.now(), attempts=0)
        for failed, queued in RETRIES.items()
    )


def _transition(pk, from_status, **fields) -> bool:
    return bool(Ticket.objects.filter(pk=pk, status=from_status).update(updated_at=timezone.now(), **fields))
