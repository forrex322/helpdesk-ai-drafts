"""The Helpdesk adapter: delivers a Reply to the Ticket's `reply_url`."""

import httpx
from django.conf import settings


class RetryableDeliveryError(Exception):
    """The Helpdesk may or may not have the Reply: try again with the same Idempotency-Key."""


class PermanentDeliveryError(Exception):
    """The Helpdesk refused the Reply; retrying will not help."""


RETRYABLE_STATUSES = {408, 425, 429}


class HelpdeskClient:
    def __init__(self, timeout, transport=None):
        self.http = httpx.Client(timeout=timeout, transport=transport)

    def deliver_reply(self, reply_url, ticket_id, message, idempotency_key):
        try:
            response = self.http.post(
                reply_url,
                json={"ticket_id": ticket_id, "message": message},
                headers={"Idempotency-Key": str(idempotency_key)},
            )
        except httpx.TransportError as error:
            # Includes timeouts: the Helpdesk may have stored the Reply anyway.
            raise RetryableDeliveryError(f"{type(error).__name__}: {error}") from error
        if response.is_success:
            return
        detail = f"HTTP {response.status_code}: {response.text[:200]}"
        if response.status_code >= 500 or response.status_code in RETRYABLE_STATUSES:
            raise RetryableDeliveryError(detail)
        raise PermanentDeliveryError(detail)


def helpdesk_client_from_settings():
    return HelpdeskClient(timeout=settings.HELPDESK_TIMEOUT_SECONDS)
