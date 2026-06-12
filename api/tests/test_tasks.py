"""Tasks router: creation fields, done/undo, list filters, assignee clearing.

Recurring done → next_occurrence is covered by test_critical_paths.
"""

from .conftest import client


def _add_member(owner: dict[str, str], member: dict[str, str], group_id: str) -> None:
    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner,
        json={"expires_at": None, "max_uses": None},
    )
    client.post(f"/api/v1/invites/{invite_resp.json()['token']}/accept", headers=member)


def test_create_task_with_rrule_and_assignee(make_user, make_group) -> None:
    """POST /groups/{id}/tasks stores title, rrule, due_at, and assignee_id."""
    owner = make_user("assign_owner@example.com")
    member = make_user("assign_member@example.com")
    member_id = client.post("/api/v1/person/sync", headers=member).json()["id"]
    group_id = make_group(owner, "Assign Group")
    _add_member(owner, member, group_id)

    response = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=owner,
        json={
            "title": "Weekly bins",
            "rrule": "FREQ=WEEKLY;BYDAY=SU",
            "due_at": "2026-06-07T20:00:00Z",
            "assignee_id": member_id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Weekly bins"
    assert data["rrule"] == "FREQ=WEEKLY;BYDAY=SU"
    assert data["due_at"] is not None
    assert data["assignee_id"] == member_id
    assert data["done"] is False


def test_mark_done_undo_and_list_filters(make_user, make_group) -> None:
    """Done sets done=TRUE (no next occurrence for one-off tasks), the default
    list hides done tasks, ?done=true shows them, and undo restores done=FALSE."""
    headers = make_user("done_flow@example.com")
    group_id = make_group(headers, "Done Group")

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "One-off task", "rrule": None, "due_at": None, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]

    done_resp = client.post(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert done_resp.status_code == 200
    assert done_resp.json()["task"]["done"] is True
    assert done_resp.json()["next_occurrence"] is None

    undone_ids = [
        t["id"] for t in client.get(f"/api/v1/groups/{group_id}/tasks", headers=headers).json()
    ]
    assert task_id not in undone_ids

    done_ids = [
        t["id"]
        for t in client.get(f"/api/v1/groups/{group_id}/tasks?done=true", headers=headers).json()
    ]
    assert task_id in done_ids

    undo_resp = client.delete(f"/api/v1/tasks/{task_id}/done", headers=headers)
    assert undo_resp.status_code == 200
    assert undo_resp.json()["done"] is False


def test_remove_member_clears_assignee_id(make_user, make_group) -> None:
    """Removing a member from a group clears assignee_id on their tasks (FR-022)."""
    owner = make_user("clear_owner@example.com")
    member = make_user("clear_member@example.com")
    member_id = client.post("/api/v1/person/sync", headers=member).json()["id"]
    group_id = make_group(owner, "Clear Assign Group")
    _add_member(owner, member, group_id)

    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=owner,
        json={"title": "Member's task", "rrule": None, "due_at": None, "assignee_id": member_id},
    )
    task_id = task_resp.json()["id"]

    client.delete(f"/api/v1/groups/{group_id}/membership", headers=member)

    tasks = [
        t
        for t in client.get(f"/api/v1/groups/{group_id}/tasks", headers=owner).json()
        if t["id"] == task_id
    ]
    assert len(tasks) == 1
    assert tasks[0]["assignee_id"] is None
