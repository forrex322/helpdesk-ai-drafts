"""A stand-in for the real Helpdesk's reply API, with fault injection.

Randomly answers 503 without storing the Reply, or stores it and then
answers too late for the caller's timeout. Deduplicates by Idempotency-Key.
"""

import json
import logging
import random
import time

from django.conf import settings
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import MockReply

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def post_reply(request, ticket_id):
    try:
        payload = json.loads(request.body)
        message = payload["message"]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
        return JsonResponse({"error": "Expected JSON with ticket_id and message."}, status=400)
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({"error": "message must be a non-empty string."}, status=400)

    roll = random.random()
    if roll < settings.MOCK_HELPDESK_FAILURE_RATE:
        logger.info("Mock Helpdesk: injected 503 for %s", ticket_id)
        return JsonResponse({"error": "Service temporarily unavailable (injected)."}, status=503)

    key = request.headers.get("Idempotency-Key") or None
    if key:
        reply, created = MockReply.objects.get_or_create(
            idempotency_key=key, defaults={"ticket_id": ticket_id, "message": message}
        )
        if not created:
            MockReply.objects.filter(pk=reply.pk).update(duplicate_deliveries=F("duplicate_deliveries") + 1)
            logger.info("Mock Helpdesk: duplicate delivery for %s absorbed", ticket_id)
    else:
        reply = MockReply.objects.create(ticket_id=ticket_id, message=message)

    if roll < settings.MOCK_HELPDESK_FAILURE_RATE + settings.MOCK_HELPDESK_SLOW_RATE:
        logger.info("Mock Helpdesk: stored %s, answering late (injected)", ticket_id)
        time.sleep(settings.MOCK_HELPDESK_SLOW_SECONDS)
    return JsonResponse({"id": reply.pk, "ticket_id": ticket_id}, status=201)


def received_replies(request):
    replies = MockReply.objects.all()[:200]
    totals = MockReply.objects.aggregate(duplicates=Sum("duplicate_deliveries"))
    return render(
        request,
        "mock_helpdesk/replies.html",
        {
            "replies": replies,
            "total": MockReply.objects.count(),
            "duplicates": totals["duplicates"] or 0,
            "failure_rate": settings.MOCK_HELPDESK_FAILURE_RATE,
            "slow_rate": settings.MOCK_HELPDESK_SLOW_RATE,
            "slow_seconds": settings.MOCK_HELPDESK_SLOW_SECONDS,
        },
    )
