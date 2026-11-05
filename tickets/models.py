from django.db import models


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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.helpdesk_ticket_id} ({self.event_id})"
