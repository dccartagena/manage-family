"""End-to-end flows through the API.

- Group create → invite generate → invite accept → invite exhaustion
- Recurring task done → next occurrence
- /jobs/tick secret enforcement and reminder delivery
"""

import pytest

from .conftest import client


def test_group_invite_accept_flow(make_user, make_group) -> None:
    """Full flow: owner creates group → generates invite → second user accepts."""
    owner = make_user("owner@example.com")
    member = make_user("member@example.com")
    group_id = make_group(owner, "Critical Path Family")

    # Owner generates a single-use invite
    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner,
        json={"max_uses": 1, "expires_at": "2099-01-01T00:00:00"},
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]
    assert len(token) == 64

    # Second user accepts the invite
    accept_resp = client.post(f"/api/v1/invites/{token}/accept", headers=member)
    assert accept_resp.status_code == 200
    accept_data = accept_resp.json()
    assert accept_data["group_id"] == group_id
    assert accept_data["role"] == "member"

    # Both users see the group
    owner_ids = [g["id"] for g in client.get("/api/v1/groups", headers=owner).json()]
    member_ids = [g["id"] for g in client.get("/api/v1/groups", headers=member).json()]
    assert group_id in owner_ids
    assert group_id in member_ids

    # Exhausted invite returns 410
    exhausted_resp = client.post(f"/api/v1/invites/{token}/accept", headers=member)
    assert exhausted_resp.status_code == 410


def test_task_done_and_next_occurrence(make_user, make_group) -> None:
    """Marking a recurring task done creates next_occurrence 7 days later."""
    headers = make_user("tasks@example.com")
    group_id = make_group(headers, "Task Test Group")

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


def test_jobs_tick_requires_correct_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /jobs/tick returns 403 with a wrong or missing X-Scheduler-Secret."""
    monkeypatch.setenv("SCHEDULER_SECRET", "correct-secret")
    wrong = client.get("/api/v1/jobs/tick", headers={"X-Scheduler-Secret": "wrong-secret"})
    assert wrong.status_code == 403
    missing = client.get("/api/v1/jobs/tick")
    assert missing.status_code == 403


def test_jobs_tick_correct_secret_delivers_reminders(
    make_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs/tick with correct secret marks due reminders delivered."""
    monkeypatch.setenv("SCHEDULER_SECRET", "correct-secret")
    headers = make_user("reminder@example.com")

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

    tick_resp = client.get(
        "/api/v1/jobs/tick",
        headers={"X-Scheduler-Secret": "correct-secret"},
    )
    assert tick_resp.status_code == 200
    tick_data = tick_resp.json()
    assert tick_data["reminders_delivered"] >= 1
    assert "tick_at" in tick_data

    reminders = client.get("/api/v1/reminders", headers=headers).json()
    delivered = [r for r in reminders if r["title"] == "Past due reminder"]
    assert len(delivered) == 1
    assert delivered[0]["delivered"] is True
