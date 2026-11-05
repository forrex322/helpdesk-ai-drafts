import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import EventForm
from .models import Ticket


@csrf_exempt
@require_POST
def helpdesk_webhook(request):
    """Store the Event's Ticket once and answer immediately; drafting happens in the worker."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"errors": {"body": ["Invalid JSON."]}}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"errors": {"body": ["Expected a JSON object."]}}, status=400)

    form = EventForm(payload)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    event = form.cleaned_data
    # get_or_create is race-safe on the unique event_id: a concurrent loser
    # hits the IntegrityError path and re-reads the winner's row.
    _, created = Ticket.objects.get_or_create(
        event_id=event["event_id"],
        defaults={
            "helpdesk_ticket_id": event["ticket_id"],
            "customer_email": event["customer_email"],
            "message": event["message"],
            "reply_url": event["reply_url"],
        },
    )
    return JsonResponse({"status": "accepted" if created else "duplicate"})


@login_required
def ticket_list(request):
    tickets = Ticket.objects.all()
    status = request.GET.get("status", "")
    if status in Ticket.Status.values:
        tickets = tickets.filter(status=status)
    page = Paginator(tickets, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "tickets/list.html",
        {"page": page, "status": status, "statuses": Ticket.Status.choices},
    )
