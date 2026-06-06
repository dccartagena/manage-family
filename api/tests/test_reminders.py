"""Failing tests for reminders — must fail before api/routers/reminders.py and jobs.py are implemented."""  # noqa: E501
from datetime import UTC, datetime, timedelta

import pytest
from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

_SCHEDULER_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
def set_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_SECRET", _SCHEDULER_SECRET)


def test_list_reminders_requires_auth() -> None:
    """GET /reminders without auth returns 401."""
    response = client.get("/api/v1/reminders")
    assert response.status_code == 401


def test_create_reminder_requires_auth() -> None:
    """POST /reminders without auth returns 401."""
    response = client.post(
        "/api/v1/reminders",
        json={"title": "Test", "fire_at_local": "2026-06-08T20:00:00", "timezone": "Europe/London"},
    )
    assert response.status_code == 401


def test_create_reminder_converts_timezone_to_utc(make_auth_token) -> None:
    """POST /reminders stores fire_at as UTC converted from fire_at_local + timezone."""
    token = make_auth_token(email="reminder_create@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    response = client.post(
        "/api/v1/reminders",
        headers=headers,
        json={
            "title": "Bins out",
            "fire_at_local": "2026-06-08T21:00:00",
            "timezone": "Europe/London",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Bins out"
    assert "fire_at" in body
    assert body["delivered"] is False
    # Europe/London in summer is UTC+1, so 21:00 local = 20:00 UTC
    fire_at = datetime.fromisoformat(body["fire_at"].replace("Z", "+00:00"))
    assert fire_at.hour == 20 or "20:00" in body["fire_at"]


def test_list_reminders_returns_own_only(make_auth_token) -> None:
    """GET /reminders returns only caller's reminders."""
    token_a = make_auth_token(email="reminder_a@example.com")
    token_b = make_auth_token(email="reminder_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.post("/api/v1/person/sync", headers=headers_a)
    client.post("/api/v1/person/sync", headers=headers_b)

    client.post(
        "/api/v1/reminders",
        headers=headers_a,
        json={"title": "A reminder", "fire_at_local": "2026-07-01T09:00:00", "timezone": "UTC"},
    )
    client.post(
        "/api/v1/reminders",
        headers=headers_b,
        json={"title": "B reminder", "fire_at_local": "2026-07-01T10:00:00", "timezone": "UTC"},
    )

    resp_a = client.get("/api/v1/reminders", headers=headers_a)
    assert resp_a.status_code == 200
    titles_a = [r["title"] for r in resp_a.json()]
    assert "A reminder" in titles_a
    assert "B reminder" not in titles_a


def test_delete_reminder(make_auth_token) -> None:
    """DELETE /reminders/{id} removes the reminder."""
    token = make_auth_token(email="reminder_delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    create_resp = client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "To delete", "fire_at_local": "2026-07-15T08:00:00", "timezone": "UTC"},
    )
    reminder_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/reminders/{reminder_id}", headers=headers)
    assert del_resp.status_code == 204

    list_resp = client.get("/api/v1/reminders", headers=headers)
    ids = [r["id"] for r in list_resp.json()]
    assert reminder_id not in ids


def test_delete_reminder_other_persons_returns_403(make_auth_token) -> None:
    """DELETE /reminders/{id} returns 403 when not the owner."""
    token_owner = make_auth_token(email="reminder_owner@example.com")
    token_other = make_auth_token(email="reminder_other@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_other = {"Authorization": f"Bearer {token_other}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_other)

    create_resp = client.post(
        "/api/v1/reminders",
        headers=headers_owner,
        json={"title": "Private", "fire_at_local": "2026-07-01T12:00:00", "timezone": "UTC"},
    )
    reminder_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/reminders/{reminder_id}", headers=headers_other)
    assert del_resp.status_code == 403


def test_jobs_tick_wrong_secret_returns_403() -> None:
    """GET /jobs/tick with wrong X-Scheduler-Secret returns 403."""
    response = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


def test_jobs_tick_no_secret_returns_403() -> None:
    """GET /jobs/tick without X-Scheduler-Secret returns 403."""
    response = client.get("/api/v1/jobs/tick")
    assert response.status_code == 403


def test_jobs_tick_delivers_due_reminders(make_auth_token) -> None:
    """GET /jobs/tick sets delivered=TRUE on reminders with fire_at <= now."""
    token = make_auth_token(email="reminder_tick@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    # Create a past-due reminder (fire_at in the past)
    past_time = (datetime.now(tz=UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    create_resp = client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Past due", "fire_at_local": past_time, "timezone": "UTC"},
    )
    assert create_resp.status_code == 201
    reminder_id = create_resp.json()["id"]

    tick_resp = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": _SCHEDULER_SECRET},
    )
    assert tick_resp.status_code == 200
    body = tick_resp.json()
    assert body["reminders_delivered"] >= 1
    assert "tick_at" in body

    list_resp = client.get("/api/v1/reminders", headers=headers)
    reminder = next(r for r in list_resp.json() if r["id"] == reminder_id)
    assert reminder["delivered"] is True


def test_jobs_tick_does_not_deliver_future_reminders(make_auth_token) -> None:
    """GET /jobs/tick does not deliver reminders with fire_at in the future."""
    token = make_auth_token(email="reminder_future@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    future_time = (datetime.now(tz=UTC) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    create_resp = client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Future reminder", "fire_at_local": future_time, "timezone": "UTC"},
    )
    reminder_id = create_resp.json()["id"]

    client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": _SCHEDULER_SECRET},
    )

    list_resp = client.get("/api/v1/reminders", headers=headers)
    reminder = next((r for r in list_resp.json() if r["id"] == reminder_id), None)
    assert reminder is not None
    assert reminder["delivered"] is False
