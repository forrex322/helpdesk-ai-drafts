from urllib.parse import urlparse

from django import forms


class EventForm(forms.Form):
    """Validates the Helpdesk webhook payload."""

    event_id = forms.CharField(max_length=255)
    ticket_id = forms.CharField(max_length=255)
    # Lenient on purpose: a Ticket is never lost to a 400 (which the Helpdesk does
    # not retry) over a field we only display.
    customer_email = forms.CharField(max_length=254, required=False)
    message = forms.CharField(strip=False)
    # Plain CharField: Django's URLValidator rejects TLD-less hosts such as
    # the compose service name `web`, which the mock Helpdesk uses.
    reply_url = forms.CharField(max_length=2048)

    def __init__(self, data):
        # Postgres text cannot hold NUL; dropping it beats rejecting (and so losing) the Ticket.
        super().__init__({key: value.replace("\x00", "") if isinstance(value, str) else value for key, value in data.items()})

    def clean_reply_url(self):
        url = self.cleaned_data["reply_url"]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise forms.ValidationError("Must be an absolute http(s) URL.")
        return url
