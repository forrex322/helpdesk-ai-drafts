"""Operator decisions on a Ticket.

Each decision is a conditional update from the one status it is valid in, so
a double click or two Operators acting at once change the Ticket only once.
Every function returns False when the Ticket was not in that status anymore.
"""

from django.utils import timezone

from .models import Ticket

S = Ticket.Status


def approve(ticket_id, reply, operator) -> bool:
    now = timezone.now()
    return _transition(
        ticket_id,
        S.DRAFT_READY,
        status=S.APPROVED,
        reply=reply,
        moderated_by=operator,
        moderated_at=now,
        available_at=now,
        attempts=0,
        last_error="",
    )


def reject(ticket_id, operator) -> bool:
    return _transition(ticket_id, S.DRAFT_READY, status=S.REJECTED, moderated_by=operator, moderated_at=timezone.now())


def retry(ticket_id) -> bool:
    """Send a Ticket whose drafting or Delivery gave up back into the queue."""
    restart = {"available_at": timezone.now(), "attempts": 0}
    return _transition(ticket_id, S.DRAFT_FAILED, status=S.NEW, **restart) or _transition(
        ticket_id, S.SEND_FAILED, status=S.APPROVED, **restart
    )


def _transition(ticket_id, from_status, **fields) -> bool:
    return bool(
        Ticket.objects.filter(pk=ticket_id, status=from_status).update(updated_at=timezone.now(), **fields)
    )
