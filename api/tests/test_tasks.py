"""Failing tests for tasks router — must fail before api/routers/tasks.py is implemented."""
import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_create_task_requires_auth() -> None:
    """POST /groups/{id}/tasks without auth returns 401."""
    response = client.post(f"/api/v1/groups/{uuid.uuid4()}/tasks", json={"title": "Test"})
    assert response.status_code == 401


def test_list_tasks_requires_auth() -> None:
    """GET /groups/{id}/tasks without auth returns 401."""
    response = client.get(f"/api/v1/groups/{uuid.uuid4()}/tasks")
    assert response.status_code == 401


def test_mark_done_requires_auth() -> None:
    """POST /tasks/{id}/done without auth returns 401."""
    response = client.post(f"/api/v1/tasks/{uuid.uuid4()}/done")
    assert response.status_code == 401


def test_undo_done_requires_auth() -> None:
    """DELETE /tasks/{id}/done without auth returns 401."""
    response = client.delete(f"/api/v1/tasks/{uuid.uuid4()}/done")
    assert response.status_code == 401


def test_create_task_in_group(make_auth_token) -> None:
    """POST /groups/{id}/tasks creates task for group member."""
    token = make_auth_token(email="task_create@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Task Group"})
    group_id = group_resp.json()["id"]

    response = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "Take out bins", "rrule": None, "due_at": None, "assignee_id": None},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Take out bins"
    assert data["done"] is False
    assert data["rrule"] is None
    assert "id" in data


def test_create_task_with_rrule(make_auth_token) -> None:
    """POST /groups/{id}/tasks accepts rrule string."""
    token = make_auth_token(email="rrule_create@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "RRULE Group"})
    group_id = group_resp.json()["id"]

    response = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={
            "title": "Weekly bins",
            "rrule": "FREQ=WEEKLY;BYDAY=SU",
            "due_at": "2026-06-07T20:00:00Z",
            "assignee_id": None,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rrule"] == "FREQ=WEEKLY;BYDAY=SU"
    assert data["due_at"] is not None


def test_create_task_with_assignee(make_auth_token) -> None:
    """POST /groups/{id}/tasks with valid assignee_id stores it."""
    token_owner = make_auth_token(email="assign_owner@example.com")
    token_member = make_auth_token(email="assign_member@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_member = {"Authorization": f"Bearer {token_member}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    member_resp = client.post("/api/v1/person/sync", headers=headers_member)
    member_id = member_resp.json()["id"]

    group_resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Assign Group"})
    group_id = group_resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": None},
    )
    token_val = invite_resp.json()["token"]
    client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_member)

    response = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers_owner,
        json={"title": "Assigned task", "rrule": None, "due_at": None, "assignee_id": member_id},
    )
    assert response.status_code == 201
    assert response.json()["assignee_id"] == member_id


def test_list_tasks_returns_only_undone_by_default(make_auth_token) -> None:
    """GET /groups/{id}/tasks returns only done=FALSE by default."""
    token = make_auth_token(email="list_undone@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Filter Group"})
    group_id = group_resp.json()["id"]

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "Undone task", "rrule": None, "due_at": None, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]

    client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)

    undone_resp = client.get(f"/api/v1/groups/{group_id}/tasks", headers=headers)
    assert undone_resp.status_code == 200
    ids = [t["id"] for t in undone_resp.json()]
    assert task_id not in ids


def test_list_tasks_done_filter(make_auth_token) -> None:
    """GET /groups/{id}/tasks?done=true returns only done tasks."""
    token = make_auth_token(email="done_filter@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Done Filter Group"})
    group_id = group_resp.json()["id"]

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "To be done", "rrule": None, "due_at": None, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]
    client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)

    done_resp = client.get(f"/api/v1/groups/{group_id}/tasks?done=true", headers=headers)
    assert done_resp.status_code == 200
    ids = [t["id"] for t in done_resp.json()]
    assert task_id in ids


def test_non_member_cannot_create_task(make_auth_token) -> None:
    """POST /groups/{id}/tasks returns 403 for non-member."""
    token_owner = make_auth_token(email="owner_block@example.com")
    token_other = make_auth_token(email="other_block@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_other = {"Authorization": f"Bearer {token_other}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_other)

    group_resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Private"})
    group_id = group_resp.json()["id"]

    response = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers_other,
        json={"title": "Sneaky task", "rrule": None, "due_at": None, "assignee_id": None},
    )
    assert response.status_code == 403


def test_mark_task_done(make_auth_token) -> None:
    """POST /tasks/{id}/done sets done=TRUE."""
    token = make_auth_token(email="mark_done@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Done Group"})
    group_id = group_resp.json()["id"]

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "One-off task", "rrule": None, "due_at": None, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]

    done_resp = client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert done_resp.status_code == 200
    data = done_resp.json()
    assert data["task"]["done"] is True
    assert data["task"]["id"] == task_id
    assert data["next_occurrence"] is None


def test_mark_done_recurring_creates_next_occurrence(make_auth_token) -> None:
    """POST /tasks/{id}/done for RRULE task returns next_occurrence."""
    token = make_auth_token(email="recurring_done@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Recurring Group"})
    group_id = group_resp.json()["id"]

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={
            "title": "Weekly bins",
            "rrule": "FREQ=WEEKLY",
            "due_at": "2026-06-07T20:00:00Z",
            "assignee_id": None,
        },
    )
    task_id = task_resp.json()["id"]

    done_resp = client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert done_resp.status_code == 200
    data = done_resp.json()
    assert data["task"]["done"] is True
    assert data["next_occurrence"] is not None
    assert data["next_occurrence"]["done"] is False
    assert data["next_occurrence"]["due_at"] is not None
    assert data["next_occurrence"]["due_at"] != "2026-06-07T20:00:00Z"


def test_undo_task_done(make_auth_token) -> None:
    """DELETE /tasks/{id}/done restores done=FALSE."""
    token = make_auth_token(email="undo_done@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Undo Group"})
    group_id = group_resp.json()["id"]

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "Undo task", "rrule": None, "due_at": None, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]

    client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)

    undo_resp = client.delete(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert undo_resp.status_code == 200
    assert undo_resp.json()["done"] is False


def test_remove_member_clears_assignee_id(make_auth_token) -> None:
    """Removing a member from a group clears assignee_id on their tasks (FR-022)."""
    token_owner = make_auth_token(email="clear_owner@example.com")
    token_member = make_auth_token(email="clear_member@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_member = {"Authorization": f"Bearer {token_member}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    member_resp = client.post("/api/v1/person/sync", headers=headers_member)
    member_id = member_resp.json()["id"]

    group_resp = client.post(
        "/api/v1/groups", headers=headers_owner, json={"name": "Clear Assign Group"}
    )
    group_id = group_resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": None},
    )
    token_val = invite_resp.json()["token"]
    client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_member)

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers_owner,
        json={"title": "Member's task", "rrule": None, "due_at": None, "assignee_id": member_id},
    )
    task_id = task_resp.json()["id"]

    client.delete(f"/api/v1/groups/{group_id}/membership", headers=headers_member)

    tasks_resp = client.get(f"/api/v1/groups/{group_id}/tasks", headers=headers_owner)
    tasks = [t for t in tasks_resp.json() if t["id"] == task_id]
    assert len(tasks) == 1
    assert tasks[0]["assignee_id"] is None
