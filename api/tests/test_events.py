"""Failing tests for events router — must fail before api/routers/events.py is implemented."""

import uuid

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_list_events_requires_auth() -> None:
    """GET /groups/{id}/events without auth returns 401."""
    response = client.get(f"/api/v1/groups/{uuid.uuid4()}/events")
    assert response.status_code == 401


def test_create_event_requires_auth() -> None:
    """POST /groups/{id}/events without auth returns 401."""
    response = client.post(
        f"/api/v1/groups/{uuid.uuid4()}/events",
        json={"title": "Test", "starts_at": "2026-07-01T10:00:00Z"},
    )
    assert response.status_code == 401


def test_delete_event_requires_auth() -> None:
    """DELETE /events/{id} without auth returns 401."""
    response = client.delete(f"/api/v1/events/{uuid.uuid4()}")
    assert response.status_code == 401


def test_create_and_list_event(make_auth_token) -> None:
    """POST /groups/{id}/events creates event; GET lists it."""
    token = make_auth_token(email="events_create@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Events Group"})
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "School play", "starts_at": "2026-07-13T18:00:00Z", "rrule": None},
    )
    assert create_resp.status_code == 201
    event = create_resp.json()
    assert event["title"] == "School play"
    assert event["group_id"] == group_id
    assert event["rrule"] is None
    assert "id" in event

    list_resp = client.get(f"/api/v1/groups/{group_id}/events", headers=headers)
    assert list_resp.status_code == 200
    events = list_resp.json()
    assert len(events) == 1
    assert events[0]["title"] == "School play"


def test_create_recurring_event(make_auth_token) -> None:
    """POST /groups/{id}/events creates event with rrule."""
    token = make_auth_token(email="events_recurring@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post(
        "/api/v1/groups", headers=headers, json={"name": "Recurring Events Group"}
    )
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={
            "title": "Weekly cleanup",
            "starts_at": "2026-07-06T09:00:00Z",
            "rrule": "FREQ=WEEKLY;BYDAY=SU",
        },
    )
    assert create_resp.status_code == 201
    event = create_resp.json()
    assert event["rrule"] == "FREQ=WEEKLY;BYDAY=SU"


def test_non_member_cannot_list_events(make_auth_token) -> None:
    """GET /groups/{id}/events returns 403 for non-members."""
    owner_token = make_auth_token(email="events_owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Private Events"}
    )
    group_id = group_resp.json()["id"]

    other_token = make_auth_token(email="events_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.get(f"/api/v1/groups/{group_id}/events", headers=other_headers)
    assert response.status_code == 403


def test_non_member_cannot_create_event(make_auth_token) -> None:
    """POST /groups/{id}/events returns 403 for non-members."""
    owner_token = make_auth_token(email="events_owner2@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Private Events 2"}
    )
    group_id = group_resp.json()["id"]

    other_token = make_auth_token(email="events_outsider2@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=other_headers,
        json={"title": "Sneaky event", "starts_at": "2026-07-01T10:00:00Z"},
    )
    assert response.status_code == 403


def test_delete_event(make_auth_token) -> None:
    """DELETE /events/{id} removes event; subsequent GET returns empty list."""
    token = make_auth_token(email="events_delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post(
        "/api/v1/groups", headers=headers, json={"name": "Delete Events Group"}
    )
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "Temp event", "starts_at": "2026-07-01T10:00:00Z"},
    )
    event_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/events/{event_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/v1/groups/{group_id}/events", headers=headers)
    assert list_resp.json() == []


def test_non_member_cannot_delete_event(make_auth_token) -> None:
    """DELETE /events/{id} returns 403 for non-members of the owning group."""
    owner_token = make_auth_token(email="events_del_owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Events Del Group"}
    )
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=owner_headers,
        json={"title": "Protected event", "starts_at": "2026-07-01T10:00:00Z"},
    )
    event_id = create_resp.json()["id"]

    other_token = make_auth_token(email="events_del_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.delete(f"/api/v1/events/{event_id}", headers=other_headers)
    assert response.status_code == 403
