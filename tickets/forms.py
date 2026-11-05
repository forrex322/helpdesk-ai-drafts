from urllib.parse import urlparse

from django import forms


class EventForm(forms.Form):
    """Validates the Helpdesk webhook payload."""

    event_id = forms.CharField(max_length=255)
    ticket_id = forms.CharField(max_length=255)
    customer_email = forms.EmailField(max_length=254)
    message = forms.CharField()
    # Plain CharField: Django's URLValidator rejects TLD-less hosts such as
    # the compose service name `web`, which the mock Helpdesk uses.
    reply_url = forms.CharField(max_length=2048)

    def clean_reply_url(self):
        url = self.cleaned_data["reply_url"]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise forms.ValidationError("Must be an absolute http(s) URL.")
        return url
