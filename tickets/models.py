from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    """A Customer's support request, created from exactly one Helpdesk Event."""

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

    event_id = models.CharField(max_length=255, unique=True)
    helpdesk_ticket_id = models.CharField(max_length=255, db_index=True)
    customer_email = models.EmailField(max_length=254)
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

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["available_at"],
                name="ticket_due_work_idx",
                condition=models.Q(status__in=["new", "drafting", "approved", "sending"]),
            ),
        ]

    def __str__(self):
        return f"{self.helpdesk_ticket_id} ({self.event_id})"


class RateLimitHit(models.Model):
    """One call start recorded by the sliding-window rate limiter (ADR-0003)."""

    bucket = models.CharField(max_length=50)
    at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["bucket", "at"], name="ratelimit_bucket_at_idx")]
