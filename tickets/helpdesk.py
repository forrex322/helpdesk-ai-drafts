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

    def deliver_reply(self, reply_url, helpdesk_ticket_id, reply, idempotency_key):
        try:
            response = self.http.post(
                reply_url,
                json={"ticket_id": helpdesk_ticket_id, "message": reply},
                headers={"Idempotency-Key": str(idempotency_key)},
            )
        except httpx.TransportError as error:
            # Includes timeouts: the Helpdesk may have stored the Reply anyway.
            raise RetryableDeliveryError(repr(error)) from error
        # The contract promises 201; any 2xx still means the Helpdesk has the Reply,
        # and resending after a success is exactly what must never happen.
        if response.is_success:
            return
        detail = f"HTTP {response.status_code}: {response.text[:200]}"
        if response.status_code >= 500 or response.status_code in RETRYABLE_STATUSES:
            raise RetryableDeliveryError(detail)
        raise PermanentDeliveryError(detail)


def helpdesk_client_from_settings():
    return HelpdeskClient(timeout=settings.HELPDESK_TIMEOUT_SECONDS)
