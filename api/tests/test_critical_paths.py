"""Integration tests for critical paths through the API.

Covers:
- 401 without auth token
- Group create → invite generate → invite accept full flow
- Task done + next_occurrence recurrence
- /jobs/tick correct-secret delivers reminders; wrong-secret returns 403
"""

import uuid
from collections.abc import Callable

import pytest
from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _auth_headers(make_auth_token: Callable[[str], str], email: str) -> dict[str, str]:
    token = make_auth_token(email=email)
    return {"Authorization": f"Bearer {token}"}


def _sync_person(headers: dict[str, str]) -> None:
    client.post("/api/v1/person/sync", headers=headers)


# ---------------------------------------------------------------------------
# 401 without auth token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,url",
    [
        ("GET", "/api/v1/groups"),
        ("POST", "/api/v1/groups"),
        ("GET", "/api/v1/dashboard"),
        ("GET", "/api/v1/reminders"),
        ("POST", "/api/v1/reminders"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/tasks"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/shopping"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/events"),
        ("POST", "/api/v1/ical/rotate"),
    ],
)
def test_unauthenticated_returns_401(method: str, url: str) -> None:
    """Every protected endpoint returns 401 without Authorization header."""
    response = client.request(method, url)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Group create → invite generate → invite accept full flow
# ---------------------------------------------------------------------------


def test_group_invite_accept_flow(make_auth_token: Callable[[str], str]) -> None:
    """Full flow: owner creates group → generates invite → second user accepts."""
    owner_headers = _auth_headers(make_auth_token, "owner@example.com")
    member_headers = _auth_headers(make_auth_token, "member@example.com")

    _sync_person(owner_headers)
    _sync_person(member_headers)

    # Owner creates group
    group_resp = client.post(
        "/api/v1/groups",
        headers=owner_headers,
        json={"name": "Critical Path Family", "parent_group_id": None},
    )
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    # Owner generates invite
    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner_headers,
        json={"max_uses": 1, "expires_at": "2099-01-01T00:00:00"},
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]
    assert len(token) == 64

    # Second user accepts invite
    accept_resp = client.post(
        f"/api/v1/invites/{token}/accept",
        headers=member_headers,
    )
    assert accept_resp.status_code == 200
    accept_data = accept_resp.json()
    assert accept_data["group_id"] == group_id
    assert accept_data["role"] == "member"

    # Both users see the group
    owner_groups = client.get("/api/v1/groups", headers=owner_headers).json()
    member_groups = client.get("/api/v1/groups", headers=member_headers).json()

    owner_ids = [g["id"] for g in owner_groups]
    member_ids = [g["id"] for g in member_groups]

    assert group_id in owner_ids
    assert group_id in member_ids

    # Exhausted invite returns 410
    exhausted_resp = client.post(
        f"/api/v1/invites/{token}/accept",
        headers=member_headers,
    )
    assert exhausted_resp.status_code == 410


# ---------------------------------------------------------------------------
# Task done + next_occurrence recurrence
# ---------------------------------------------------------------------------


def test_task_done_and_next_occurrence(make_auth_token: Callable[[str], str]) -> None:
    """Marking a recurring task done creates next_occurrence 7 days later."""
    headers = _auth_headers(make_auth_token, "tasks@example.com")
    _sync_person(headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Task Test Group", "parent_group_id": None},
    )
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    # Create recurring weekly task with due_at
    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={
            "title": "Weekly chore",
            "rrule": "FREQ=WEEKLY",
            "due_at": "2026-06-10T09:00:00",
            "assignee_id": None,
        },
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    # Mark task done
    done_resp = client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert done_resp.status_code == 200
    done_data = done_resp.json()

    assert done_data["task"]["done"] is True
    assert done_data["next_occurrence"] is not None
    assert done_data["next_occurrence"]["done"] is False

    next_due = done_data["next_occurrence"]["due_at"]
    assert next_due is not None
    # next occurrence should be roughly 7 days after original
    assert "2026-06-17" in next_due

    # Original task no longer in default list (done=FALSE filter)
    tasks = client.get(f"/api/v1/groups/{group_id}/tasks", headers=headers).json()
    task_ids = [t["id"] for t in tasks]
    assert task_id not in task_ids
    assert done_data["next_occurrence"]["id"] in task_ids


# ---------------------------------------------------------------------------
# /jobs/tick — secret header enforcement
# ---------------------------------------------------------------------------


def test_jobs_tick_wrong_secret_returns_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /jobs/tick with wrong X-Scheduler-Secret returns 403."""
    monkeypatch.setenv("SCHEDULER_SECRET", "correct-secret")
    response = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


def test_jobs_tick_correct_secret_delivers_reminders(
    make_auth_token: Callable[[str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs/tick with correct secret marks due reminders delivered."""
    monkeypatch.setenv("SCHEDULER_SECRET", "correct-secret")

    headers = _auth_headers(make_auth_token, "reminder@example.com")
    _sync_person(headers)

    # Create reminder due in the past (1970 = always due)
    reminder_resp = client.post(
        "/api/v1/reminders",
        headers=headers,
        json={
            "title": "Past due reminder",
            "fire_at_local": "1970-01-01T00:01:00",
            "timezone": "UTC",
        },
    )
    assert reminder_resp.status_code == 201

    # Tick the scheduler
    tick_resp = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": "correct-secret"},
    )
    assert tick_resp.status_code == 200
    tick_data = tick_resp.json()
    assert tick_data["reminders_delivered"] >= 1
    assert "tick_at" in tick_data

    # Reminder should now be delivered
    reminders = client.get("/api/v1/reminders", headers=headers).json()
    delivered = [r for r in reminders if r["title"] == "Past due reminder"]
    assert len(delivered) == 1
    assert delivered[0]["delivered"] is True
