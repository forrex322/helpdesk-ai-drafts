import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Status(models.TextChoices):
    NEW = "new", "Нове"
    DRAFTING = "drafting", "Генерується чернетка"
    DRAFT_READY = "draft_ready", "Чекає модерації"
    DRAFT_FAILED = "draft_failed", "Помилка генерації"
    APPROVED = "approved", "Підтверджено, в черзі"
    SENDING = "sending", "Надсилається"
    SENT = "sent", "Надіслано"
    SEND_FAILED = "send_failed", "Помилка надсилання"
    REJECTED = "rejected", "Відхилено"


# Queued status -> the in-flight status a claimed Ticket takes (ADR-0001). In-flight
# statuses are claimable too: that is how an expired lease gets picked up again.
CLAIMS = {
    Status.NEW: Status.DRAFTING,
    Status.DRAFTING: Status.DRAFTING,
    Status.APPROVED: Status.SENDING,
    Status.SENDING: Status.SENDING,
}

# Status where drafting or Delivery gave up -> where an Operator's retry sends the Ticket.
RETRIES = {
    Status.DRAFT_FAILED: Status.NEW,
    Status.SEND_FAILED: Status.APPROVED,
}


class Ticket(models.Model):
    """A Customer's support request, created from exactly one Helpdesk Event."""

    Status = Status

    event_id = models.CharField(max_length=255, unique=True)
    helpdesk_ticket_id = models.CharField(max_length=255, db_index=True)
    customer_email = models.CharField(max_length=254, blank=True)
    message = models.TextField()
    reply_url = models.URLField(max_length=2048)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    # Job-queue fields (ADR-0001). For due statuses `available_at` is the next
    # attempt time; for in-flight statuses it is when the worker's lease expires.
    available_at = models.DateTimeField(default=timezone.now)
    lease_id = models.UUIDField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    draft = models.TextField(blank=True)
    cited_articles = models.ManyToManyField("knowledge_base.Article", blank=True, related_name="+")

    # Set by the Operator's Approval (the Reply is the approved, possibly edited, Draft) or Rejection.
    reply = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    # Sent as `Idempotency-Key` on every Delivery attempt of this Ticket's Reply (ADR-0002).
    reply_idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["available_at"],
                name="ticket_due_work_idx",
                condition=models.Q(status__in=[status.value for status in CLAIMS]),
            ),
        ]

    def __str__(self):
        return f"{self.helpdesk_ticket_id} ({self.event_id})"

    @property
    def can_retry(self):
        return self.status in RETRIES


class RateLimitHit(models.Model):
    """One LLM call start recorded by the sliding-window rate limiter (ADR-0003)."""

    at = models.DateTimeField(db_index=True)
