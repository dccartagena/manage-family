"""iCal feed: secret-based access, event/reminder VEVENTs, group rollup, rotation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from .conftest import client

_SCHEDULER_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
def set_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_SECRET", _SCHEDULER_SECRET)


def _ical_secret(headers: dict[str, str]) -> str:
    return client.post("/api/v1/person/sync", headers=headers).json()["ical_secret"]


def test_ical_unknown_secret_returns_404() -> None:
    """GET /ical/{secret} with unknown UUID returns 404."""
    assert client.get(f"/api/v1/ical/{uuid.uuid4()}").status_code == 404


def test_ical_feed_includes_group_events(make_user, make_group) -> None:
    """The feed is text/calendar and contains a VEVENT for the user's group event."""
    headers = make_user("ical_event@example.com")
    ical_secret = _ical_secret(headers)
    group_id = make_group(headers, "iCal Group")

    client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "Birthday party", "starts_at": "2026-07-15T15:00:00Z"},
    )

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "VEVENT" in response.text
    assert "Birthday party" in response.text


def test_ical_parent_group_member_sees_child_group_events(make_user, make_group) -> None:
    """Parent-group member's iCal feed includes sub-group events (rollup).

    A is owner of P. B creates C as child of P and creates an event in C.
    A's feed must include events from C because C is a descendant of P.
    """
    parent = make_user("ical_parent@example.com")
    parent_ical_secret = _ical_secret(parent)
    parent_group_id = make_group(parent, "Parent Group")

    child = make_user("ical_child@example.com")
    child_group_id = make_group(child, "Child Group", parent_group_id)

    client.post(
        f"/api/v1/groups/{child_group_id}/events",
        headers=child,
        json={"title": "Child group event", "starts_at": "2026-08-01T10:00:00Z"},
    )

    response = client.get(f"/api/v1/ical/{parent_ical_secret}")
    assert response.status_code == 200
    assert "Child group event" in response.text


def test_ical_rotate_invalidates_old_secret(make_user) -> None:
    """POST /ical/rotate returns a new feed URL; the old secret stops working."""
    headers = make_user("ical_rotate@example.com")
    old_secret = _ical_secret(headers)
    assert client.get(f"/api/v1/ical/{old_secret}").status_code == 200

    rotate_resp = client.post("/api/v1/ical/rotate", headers=headers)
    assert rotate_resp.status_code == 200
    new_feed_url = rotate_resp.json()["new_feed_url"]
    assert str(old_secret) not in new_feed_url
    assert "ical" in new_feed_url

    assert client.get(f"/api/v1/ical/{old_secret}").status_code == 404


def test_ical_includes_reminders_as_vevents(make_user) -> None:
    """Delivered reminders appear as VEVENT with VALARM; future undelivered
    reminders appear too."""
    headers = make_user("ical_reminders@example.com")
    ical_secret = _ical_secret(headers)

    now = datetime.now(tz=UTC)
    for title, fire_at in (
        ("Past reminder", now - timedelta(hours=1)),
        ("Future reminder", now + timedelta(hours=2)),
    ):
        client.post(
            "/api/v1/reminders",
            headers=headers,
            json={
                "title": title,
                "fire_at_local": fire_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "timezone": "UTC",
            },
        )

    # Deliver the past reminder
    client.get("/api/v1/jobs/tick", headers={"X-Scheduler-Secret": _SCHEDULER_SECRET})

    response = client.get(f"/api/v1/ical/{ical_secret}")
    assert response.status_code == 200
    content = response.text
    assert "VEVENT" in content
    assert "Past reminder" in content
    assert "VALARM" in content
    assert "Future reminder" in content
