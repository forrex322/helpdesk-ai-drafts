from django.contrib.auth import authenticate
from django.core.management import call_command


def test_creates_demo_operator_who_can_log_in(db, settings):
    settings.OPERATOR_USERNAME = "olena"
    settings.OPERATOR_PASSWORD = "s3cret-pass"

    call_command("ensure_operator")

    assert authenticate(username="olena", password="s3cret-pass") is not None


def test_running_twice_keeps_one_operator_with_current_password(db, settings):
    settings.OPERATOR_USERNAME = "olena"
    settings.OPERATOR_PASSWORD = "old-pass"
    call_command("ensure_operator")

    settings.OPERATOR_PASSWORD = "new-pass"
    call_command("ensure_operator")

    assert authenticate(username="olena", password="old-pass") is None
    assert authenticate(username="olena", password="new-pass") is not None
