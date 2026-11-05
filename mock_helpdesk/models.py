from django.db import models


class MockReply(models.Model):
    """A Reply as the mock Helpdesk stored it, i.e. what the Customer received."""

    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    ticket_id = models.CharField(max_length=255)
    message = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    # Repeated deliveries with the same Idempotency-Key that were acknowledged but not stored again.
    duplicate_deliveries = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-received_at", "-id"]
