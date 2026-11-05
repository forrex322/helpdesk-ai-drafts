from django.urls import path

from . import views

app_name = "mock_helpdesk"

urlpatterns = [
    path("", views.received_replies, name="replies"),
    path("tickets/<str:ticket_id>/replies", views.post_reply, name="post-reply"),
]
