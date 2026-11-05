from tests.conftest import FakeDraftWriter, make_event, post_event
from apps.tickets.worker import Worker


def test_ticket_list_requires_login(db, client):
    response = client.get("/tickets/")

    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_ticket_list_shows_newest_first(db, client, operator_client):
    post_event(client, make_event(event_id="evt_old", ticket_id="T-1"))
    post_event(client, make_event(event_id="evt_new", ticket_id="T-2"))

    html = operator_client.get("/tickets/").content.decode()

    assert html.index('data-event-id="evt_new"') < html.index('data-event-id="evt_old"')


def test_ticket_list_filters_by_status(db, client, operator_client, clock):
    post_event(client, make_event(event_id="evt_waiting"))
    Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()
    post_event(client, make_event(event_id="evt_fresh"))

    html = operator_client.get("/tickets/?status=draft_ready").content.decode()

    assert 'data-event-id="evt_waiting"' in html
    assert 'data-event-id="evt_fresh"' not in html


def test_ticket_list_shows_draft_previews(db, client, operator_client, clock):
    post_event(client, make_event(message="Не можу експортувати звіт у PDF"))
    Worker(draft_writer=FakeDraftWriter(), now=clock).run_once()

    assert "Чернетка для: Не можу експортувати звіт у PDF" in operator_client.get("/tickets/").content.decode()


def test_operator_logs_in_and_lands_on_ticket_list(db, client, operator):
    response = client.post("/login/", {"username": "operator", "password": "pass"})

    assert response.status_code == 302
    assert response["Location"] == "/tickets/"
