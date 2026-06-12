"""Reminders router: timezone conversion, per-person privacy, scheduler delivery.

Scheduler secret enforcement and happy-path delivery are also exercised in
test_critical_paths.
"""

from datetime import UTC, datetime, timedelta

import pytest

from .conftest import client

_SCHEDULER_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
def set_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_SECRET", _SCHEDULER_SECRET)


def test_create_reminder_converts_timezone_to_utc(make_user) -> None:
    """POST /reminders stores fire_at as UTC converted from fire_at_local + timezone."""
    headers = make_user("reminder_create@example.com")

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
    assert body["delivered"] is False
    # Europe/London in summer is UTC+1, so 21:00 local = 20:00 UTC
    fire_at = datetime.fromisoformat(body["fire_at"].replace("Z", "+00:00"))
    assert fire_at.hour == 20 or "20:00" in body["fire_at"]


def test_reminders_are_private_per_person(make_user) -> None:
    """GET returns only the caller's reminders; DELETE of another person's
    reminder returns 403; DELETE of one's own removes it."""
    person_a = make_user("reminder_a@example.com")
    person_b = make_user("reminder_b@example.com")

    create_resp = client.post(
        "/api/v1/reminders",
        headers=person_a,
        json={"title": "A reminder", "fire_at_local": "2026-07-01T09:00:00", "timezone": "UTC"},
    )
    reminder_id = create_resp.json()["id"]
    client.post(
        "/api/v1/reminders",
        headers=person_b,
        json={"title": "B reminder", "fire_at_local": "2026-07-01T10:00:00", "timezone": "UTC"},
    )

    titles_a = [r["title"] for r in client.get("/api/v1/reminders", headers=person_a).json()]
    assert titles_a == ["A reminder"]

    assert client.delete(f"/api/v1/reminders/{reminder_id}", headers=person_b).status_code == 403

    assert client.delete(f"/api/v1/reminders/{reminder_id}", headers=person_a).status_code == 204
    assert client.get("/api/v1/reminders", headers=person_a).json() == []


def test_jobs_tick_delivers_only_due_reminders(make_user) -> None:
    """GET /jobs/tick delivers past-due reminders but not future ones."""
    headers = make_user("reminder_tick@example.com")

    def _create(title: str, fire_at: datetime) -> str:
        resp = client.post(
            "/api/v1/reminders",
            headers=headers,
            json={
                "title": title,
                "fire_at_local": fire_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "timezone": "UTC",
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    now = datetime.now(tz=UTC)
    past_id = _create("Past due", now - timedelta(hours=1))
    future_id = _create("Future reminder", now + timedelta(hours=2))

    tick_resp = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": _SCHEDULER_SECRET},
    )
    assert tick_resp.status_code == 200
    assert tick_resp.json()["reminders_delivered"] >= 1

    by_id = {r["id"]: r for r in client.get("/api/v1/reminders", headers=headers).json()}
    assert by_id[past_id]["delivered"] is True
    assert by_id[future_id]["delivered"] is False
