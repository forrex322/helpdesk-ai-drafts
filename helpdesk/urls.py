from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


def health(request):
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    path('health', health, name='health'),
    path('admin/', admin.site.urls),
]
