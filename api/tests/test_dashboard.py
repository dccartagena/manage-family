"""Failing tests for dashboard — must fail before api/routers/dashboard.py is implemented."""
from datetime import UTC, datetime, timedelta

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _today_start() -> datetime:
    now = datetime.now(UTC).replace(tzinfo=None)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def test_dashboard_requires_auth() -> None:
    """GET /dashboard without auth returns 401."""
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401


def test_dashboard_empty_for_new_user(make_auth_token) -> None:
    """Empty dashboard returns all 5 sections as empty arrays (not 404)."""
    token = make_auth_token(email="dashboard_empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overdue_tasks"] == []
    assert body["today_tasks"] == []
    assert body["today_events"] == []
    assert body["shopping_counts"] == []
    assert body["upcoming_events"] == []


def test_dashboard_overdue_tasks_include_group_name(make_auth_token) -> None:
    """GET /dashboard overdue_tasks includes tasks due before today with group_name."""
    token = make_auth_token(email="dashboard_overdue@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Overdue Group", "parent_group_id": None},
    )
    assert group_resp.status_code == 201
    group_id = group_resp.json()["id"]

    yesterday_noon = (_today_start() - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "Overdue chore", "rrule": None, "due_at": yesterday_noon, "assignee_id": None},  # noqa: E501
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    overdue_ids = [t["id"] for t in body["overdue_tasks"]]
    assert task_id in overdue_ids

    overdue_task = next(t for t in body["overdue_tasks"] if t["id"] == task_id)
    assert overdue_task["group_name"] == "Overdue Group"
    assert overdue_task["title"] == "Overdue chore"
    assert "due_at" in overdue_task


def test_dashboard_today_tasks_include_group_name(make_auth_token) -> None:
    """GET /dashboard today_tasks includes undone tasks due today with group_name."""
    token = make_auth_token(email="dashboard_today_tasks@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Today Group", "parent_group_id": None},
    )
    group_id = group_resp.json()["id"]

    today_11pm = (_today_start() + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%S")
    task_resp = client.post(
        f"/api/v1/groups/{group_id}/tasks",
        headers=headers,
        json={"title": "Today chore", "rrule": None, "due_at": today_11pm, "assignee_id": None},
    )
    task_id = task_resp.json()["id"]

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    today_ids = [t["id"] for t in body["today_tasks"]]
    assert task_id in today_ids

    today_task = next(t for t in body["today_tasks"] if t["id"] == task_id)
    assert today_task["group_name"] == "Today Group"
    assert today_task["title"] == "Today chore"


def test_dashboard_today_events_include_group_name(make_auth_token) -> None:
    """GET /dashboard today_events includes events starting today with group_name."""
    token = make_auth_token(email="dashboard_today_events@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Events Group", "parent_group_id": None},
    )
    group_id = group_resp.json()["id"]

    today_evening = (_today_start() + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S")
    event_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "Today event", "starts_at": today_evening, "rrule": None},
    )
    assert event_resp.status_code == 201
    event_id = event_resp.json()["id"]

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    today_event_ids = [e["id"] for e in body["today_events"]]
    assert event_id in today_event_ids

    event = next(e for e in body["today_events"] if e["id"] == event_id)
    assert event["group_name"] == "Events Group"
    assert event["title"] == "Today event"


def test_dashboard_shopping_counts_per_group(make_auth_token) -> None:
    """GET /dashboard shopping_counts shows unchecked item count per group with group_name."""
    token = make_auth_token(email="dashboard_shopping@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Shopping Group", "parent_group_id": None},
    )
    group_id = group_resp.json()["id"]

    client.post(f"/api/v1/groups/{group_id}/shopping", headers=headers, json={"name": "Milk"})
    client.post(f"/api/v1/groups/{group_id}/shopping", headers=headers, json={"name": "Bread"})

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    group_counts = {sc["group_id"]: sc["unchecked_count"] for sc in body["shopping_counts"]}
    assert group_id in group_counts
    assert group_counts[group_id] == 2

    group_entry = next(sc for sc in body["shopping_counts"] if sc["group_id"] == group_id)
    assert group_entry["group_name"] == "Shopping Group"


def test_dashboard_upcoming_events(make_auth_token) -> None:
    """GET /dashboard upcoming_events shows events in next 7 days (starting tomorrow)."""
    token = make_auth_token(email="dashboard_upcoming@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    group_resp = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Upcoming Group", "parent_group_id": None},
    )
    group_id = group_resp.json()["id"]

    tomorrow_noon = (_today_start() + timedelta(days=1, hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
    event_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "Upcoming event", "starts_at": tomorrow_noon, "rrule": None},
    )
    event_id = event_resp.json()["id"]

    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    upcoming_ids = [e["id"] for e in body["upcoming_events"]]
    assert event_id in upcoming_ids

    upcoming = next(e for e in body["upcoming_events"] if e["id"] == event_id)
    assert upcoming["group_name"] == "Upcoming Group"
