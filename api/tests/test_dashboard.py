"""Dashboard router: empty state and all five sections populated at once."""

from datetime import UTC, datetime, timedelta

from .conftest import client


def _today_start() -> datetime:
    now = datetime.now(UTC).replace(tzinfo=None)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def test_dashboard_empty_for_new_user(make_user) -> None:
    """Empty dashboard returns all 5 sections as empty arrays (not 404)."""
    headers = make_user("dashboard_empty@example.com")

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overdue_tasks"] == []
    assert body["today_tasks"] == []
    assert body["today_events"] == []
    assert body["shopping_counts"] == []
    assert body["upcoming_events"] == []


def test_dashboard_populates_all_sections(make_user, make_group) -> None:
    """One group seeded with an overdue task, a today task, a today event,
    unchecked shopping items, and a tomorrow event fills all five sections
    with group_name attached."""
    headers = make_user("dashboard_full@example.com")
    group_id = make_group(headers, "Dash Group")

    def _post_task(title: str, due_at: datetime) -> str:
        resp = client.post(
            f"/api/v1/groups/{group_id}/tasks",
            headers=headers,
            json={
                "title": title,
                "rrule": None,
                "due_at": due_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "assignee_id": None,
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def _post_event(title: str, starts_at: datetime) -> str:
        resp = client.post(
            f"/api/v1/groups/{group_id}/events",
            headers=headers,
            json={
                "title": title,
                "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "rrule": None,
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    today = _today_start()
    overdue_id = _post_task("Overdue chore", today - timedelta(hours=12))
    today_task_id = _post_task("Today chore", today + timedelta(hours=23))
    today_event_id = _post_event("Today event", today + timedelta(hours=20))
    upcoming_id = _post_event("Upcoming event", today + timedelta(days=1, hours=12))
    client.post(f"/api/v1/groups/{group_id}/shopping", headers=headers, json={"name": "Milk"})
    client.post(f"/api/v1/groups/{group_id}/shopping", headers=headers, json={"name": "Bread"})

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert [t["id"] for t in body["overdue_tasks"]] == [overdue_id]
    assert body["overdue_tasks"][0]["group_name"] == "Dash Group"
    assert body["overdue_tasks"][0]["due_at"] is not None

    assert [t["id"] for t in body["today_tasks"]] == [today_task_id]
    assert [e["id"] for e in body["today_events"]] == [today_event_id]
    assert [e["id"] for e in body["upcoming_events"]] == [upcoming_id]
    assert body["upcoming_events"][0]["group_name"] == "Dash Group"

    counts = {sc["group_id"]: sc for sc in body["shopping_counts"]}
    assert counts[group_id]["unchecked_count"] == 2
    assert counts[group_id]["group_name"] == "Dash Group"
