"""Auth & access control: token verification, the 401 sweep over all protected
endpoints, and the non-member 403 sweep over all group-scoped resources.

Per-endpoint auth/permission checks live here once instead of being repeated
in every router test file.
"""

import uuid

import pytest
from fastapi import HTTPException

from .conftest import client


def test_health_endpoint_no_auth() -> None:
    """Health endpoint accessible without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "authorization",
    [
        None,  # missing header
        "Bearer not.a.jwt",  # garbage token
        # structurally valid but expired (exp=iat=2018)
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkwMjJ9."
        "4Adcj3UFYzPUVaVF43FmMab6RlaQD8A9V8wFzzht-KQ",
    ],
)
def test_get_current_person_rejects_bad_tokens(authorization: str | None) -> None:
    """Missing, malformed, and expired tokens all raise HTTP 401."""
    import asyncio

    from api.auth import get_current_person

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_person(authorization=authorization))
    assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", "/api/v1/person/sync"),
        ("GET", "/api/v1/groups"),
        ("POST", "/api/v1/groups"),
        ("DELETE", f"/api/v1/groups/{uuid.uuid4()}/membership"),
        ("POST", f"/api/v1/groups/{uuid.uuid4()}/invites"),
        ("POST", f"/api/v1/invites/{'a' * 64}/accept"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/tasks"),
        ("POST", f"/api/v1/tasks/{uuid.uuid4()}/done"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/shopping"),
        ("PATCH", f"/api/v1/shopping/{uuid.uuid4()}"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/events"),
        ("DELETE", f"/api/v1/events/{uuid.uuid4()}"),
        ("GET", "/api/v1/dashboard"),
        ("GET", "/api/v1/reminders"),
        ("POST", "/api/v1/ical/rotate"),
        ("GET", f"/api/v1/groups/{uuid.uuid4()}/inventory"),
        ("POST", f"/api/v1/groups/{uuid.uuid4()}/canonical-products"),
    ],
)
def test_unauthenticated_returns_401(method: str, url: str) -> None:
    """Every protected endpoint returns 401 without an Authorization header."""
    response = client.request(method, url)
    assert response.status_code == 401


def test_non_member_gets_403_on_group_resources(make_user, make_group) -> None:
    """A person who is not a member of a group cannot touch any of its resources."""
    owner = make_user("sweep_owner@example.com")
    outsider = make_user("sweep_outsider@example.com")
    group_id = make_group(owner, "Private Group")

    attempts = [
        ("GET", f"/api/v1/groups/{group_id}/tasks", None),
        (
            "POST",
            f"/api/v1/groups/{group_id}/tasks",
            {"title": "Sneaky task", "rrule": None, "due_at": None, "assignee_id": None},
        ),
        ("GET", f"/api/v1/groups/{group_id}/shopping", None),
        ("POST", f"/api/v1/groups/{group_id}/shopping", {"name": "Bread"}),
        ("GET", f"/api/v1/groups/{group_id}/events", None),
        (
            "POST",
            f"/api/v1/groups/{group_id}/events",
            {"title": "Sneaky event", "starts_at": "2026-07-01T10:00:00Z"},
        ),
        ("GET", f"/api/v1/groups/{group_id}/inventory", None),
        (
            "POST",
            f"/api/v1/groups/{group_id}/canonical-products",
            {"name": "Milk", "category": "dairy", "is_staple": False, "usual_location": "fridge"},
        ),
        (
            "POST",
            f"/api/v1/groups/{group_id}/inventory/from-shopping",
            {"shopping_item_ids": [str(uuid.uuid4())]},
        ),
        ("POST", f"/api/v1/groups/{group_id}/invites", {"expires_at": None, "max_uses": None}),
        ("DELETE", f"/api/v1/groups/{group_id}/membership", None),
    ]
    for method, url, body in attempts:
        response = client.request(method, url, headers=outsider, json=body)
        assert response.status_code == 403, f"{method} {url} returned {response.status_code}"
