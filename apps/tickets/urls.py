from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
    path("<int:pk>/approve", views.approve, name="approve"),
    path("<int:pk>/reject", views.reject, name="reject"),
    path("<int:pk>/retry", views.retry, name="retry"),
]
