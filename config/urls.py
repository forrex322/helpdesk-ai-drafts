from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import RedirectView

from apps.tickets.views import helpdesk_webhook


def health(request):
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    path('health', health, name='health'),
    path('webhooks/helpdesk', helpdesk_webhook, name='helpdesk-webhook'),
    path('tickets/', include('apps.tickets.urls')),
    path('kb/', include('apps.knowledge_base.urls')),
    path('mock-helpdesk/', include('apps.mock_helpdesk.urls')),
    path('', include('django.contrib.auth.urls')),
    path('', RedirectView.as_view(pattern_name='tickets:list', permanent=False)),
]
