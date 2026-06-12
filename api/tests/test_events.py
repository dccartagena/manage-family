"""Events router: full CRUD flow including recurrence."""

from .conftest import client


def test_event_crud_flow(make_user, make_group) -> None:
    """Create (one-off and recurring) → list → delete."""
    headers = make_user("events_flow@example.com")
    group_id = make_group(headers, "Events Group")

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={"title": "School play", "starts_at": "2026-07-13T18:00:00Z", "rrule": None},
    )
    assert create_resp.status_code == 201
    event = create_resp.json()
    assert event["title"] == "School play"
    assert event["group_id"] == group_id
    assert event["rrule"] is None
    event_id = event["id"]

    recurring_resp = client.post(
        f"/api/v1/groups/{group_id}/events",
        headers=headers,
        json={
            "title": "Weekly cleanup",
            "starts_at": "2026-07-06T09:00:00Z",
            "rrule": "FREQ=WEEKLY;BYDAY=SU",
        },
    )
    assert recurring_resp.status_code == 201
    assert recurring_resp.json()["rrule"] == "FREQ=WEEKLY;BYDAY=SU"

    events = client.get(f"/api/v1/groups/{group_id}/events", headers=headers).json()
    assert {e["title"] for e in events} == {"School play", "Weekly cleanup"}

    delete_resp = client.delete(f"/api/v1/events/{event_id}", headers=headers)
    assert delete_resp.status_code == 204

    remaining = client.get(f"/api/v1/groups/{group_id}/events", headers=headers).json()
    assert [e["title"] for e in remaining] == ["Weekly cleanup"]
