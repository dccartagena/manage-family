"""Failing tests for iCal feed — must fail before api/routers/ical.py is implemented."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_SCHEDULER_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
def set_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_SECRET", _SCHEDULER_SECRET)


def test_ical_unknown_secret_returns_404() -> None:
    """GET /ical/{secret} with unknown UUID returns 404."""
    response = client.get(f"/api/v1/ical/{uuid.uuid4()}")
    assert response.status_code == 404


def test_ical_returns_text_calendar(make_auth_token) -> None:
    """GET /ical/{secret} returns Content-Type: text/calendar."""
    token = make_auth_token(email="ical_basic@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    ical_secret = sync_resp.json()["ical_secret"]

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]


def test_ical_includes_vevent_for_event(make_auth_token) -> None:
    """GET /ical/{secret} includes VEVENT for event in user's group."""
    token = make_auth_token(email="ical_event@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    ical_secret = sync_resp.json()["ical_secret"]

    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "iCal Group"})
    group_id = group_resp.json()["id"]

    client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "Birthday party", "starts_at": "2026-07-15T15:00:00Z"},
    )

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    content = response.text
    assert "VEVENT" in content
    assert "Birthday party" in content


def test_ical_parent_group_member_sees_child_group_events(make_auth_token) -> None:
    """Parent-group member's iCal feed includes sub-group events (rollup).

    A is owner of P. B creates C as child of P and creates an event in C.
    A's feed must include events from C because C is a descendant of P.
    """
    parent_token = make_auth_token(email="ical_parent@example.com")
    parent_headers = {"Authorization": f"Bearer {parent_token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=parent_headers)
    parent_ical_secret = sync_resp.json()["ical_secret"]

    parent_group_resp = client.post(
        "/api/v1/groups", headers=parent_headers, json={"name": "Parent Group"}
    )
    parent_group_id = parent_group_resp.json()["id"]

    child_token = make_auth_token(email="ical_child@example.com")
    child_headers = {"Authorization": f"Bearer {child_token}"}
    client.post("/api/v1/person/sync", headers=child_headers)

    # B creates child group as a descendant of P (B becomes owner of C)
    child_group_resp = client.post(
        "/api/v1/groups",
        headers=child_headers,
        json={"name": "Child Group", "parent_group_id": parent_group_id},
    )
    child_group_id = child_group_resp.json()["id"]

    # B creates event in C
    client.post(
        f"/api/v1/groups/{child_group_id}/events",
        headers=child_headers,
        json={"title": "Child group event", "starts_at": "2026-08-01T10:00:00Z"},
    )

    # A's iCal feed should include events from C (P's descendant)
    response = client.get(f"/api/v1/ical/{parent_ical_secret}")
    assert response.status_code == 200
    assert "Child group event" in response.text


def test_ical_rotate_requires_auth() -> None:
    """POST /ical/rotate without auth returns 401."""
    response = client.post("/api/v1/ical/rotate")
    assert response.status_code == 401


def test_ical_rotate_generates_new_secret(make_auth_token) -> None:
    """POST /ical/rotate returns new feed URL with different secret."""
    token = make_auth_token(email="ical_rotate@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    old_secret = sync_resp.json()["ical_secret"]

    rotate_resp = client.post("/api/v1/ical/rotate", headers=headers)
    assert rotate_resp.status_code == 200
    new_feed_url = rotate_resp.json()["new_feed_url"]
    assert str(old_secret) not in new_feed_url
    assert "ical" in new_feed_url


def test_ical_old_secret_returns_404_after_rotate(make_auth_token) -> None:
    """GET /ical/{old_secret} returns 404 after rotation."""
    token = make_auth_token(email="ical_rotate_404@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    old_secret = sync_resp.json()["ical_secret"]

    assert client.get(f"/api/v1/ical/{old_secret}").status_code == 200

    client.post("/api/v1/ical/rotate", headers=headers)

    assert client.get(f"/api/v1/ical/{old_secret}").status_code == 404


def test_ical_includes_delivered_reminder_as_vevent(make_auth_token) -> None:
    """GET /ical/{secret} includes delivered reminder as VEVENT with VALARM."""
    token = make_auth_token(email="ical_reminder_delivered@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    ical_secret = sync_resp.json()["ical_secret"]

    past_time = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Past reminder", "fire_at_local": past_time, "timezone": "UTC"},
    )

    client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": _SCHEDULER_SECRET},
    )

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    content = response.text
    assert "Past reminder" in content
    assert "VEVENT" in content
    assert "VALARM" in content


def test_ical_includes_future_undelivered_reminder_as_vevent(make_auth_token) -> None:
    """GET /ical/{secret} includes undelivered future reminder as VEVENT."""
    token = make_auth_token(email="ical_reminder_future@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    sync_resp = client.post("/api/v1/person/sync", headers=headers)
    ical_secret = sync_resp.json()["ical_secret"]

    future_time = (datetime.now(tz=timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Future reminder", "fire_at_local": future_time, "timezone": "UTC"},
    )

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    content = response.text
    assert "Future reminder" in content
    assert "VEVENT" in content
