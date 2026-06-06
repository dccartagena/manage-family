"""Failing tests for groups router — must fail before api/routers/groups.py is implemented."""
import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_create_group_requires_auth() -> None:
    """POST /groups without auth returns 401."""
    response = client.post("/api/v1/groups", json={"name": "Test"})
    assert response.status_code == 401


def test_list_groups_requires_auth() -> None:
    """GET /groups without auth returns 401."""
    response = client.get("/api/v1/groups")
    assert response.status_code == 401


def test_leave_group_requires_auth() -> None:
    """DELETE /groups/{id}/membership without auth returns 401."""
    response = client.delete(f"/api/v1/groups/{uuid.uuid4()}/membership")
    assert response.status_code == 401


def test_create_group_sets_caller_as_owner(make_auth_token) -> None:
    """POST /groups creates group and caller becomes owner."""
    token = make_auth_token(email="owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)

    response = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Smith Family", "parent_group_id": None},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Smith Family"
    assert data["depth"] == 0
    assert data["role"] == "owner"
    assert "id" in data


def test_list_groups_returns_only_caller_memberships(make_auth_token) -> None:
    """GET /groups lists only the caller's memberships."""
    token_a = make_auth_token(email="list_a@example.com")
    token_b = make_auth_token(email="list_b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.post("/api/v1/person/sync", headers=headers_a)
    client.post("/api/v1/person/sync", headers=headers_b)

    client.post("/api/v1/groups", headers=headers_a, json={"name": "Group A"})
    client.post("/api/v1/groups", headers=headers_b, json={"name": "Group B"})

    resp_a = client.get("/api/v1/groups", headers=headers_a)
    assert resp_a.status_code == 200
    names_a = [g["name"] for g in resp_a.json()]
    assert "Group A" in names_a
    assert "Group B" not in names_a


def test_create_nested_group_depth(make_auth_token) -> None:
    """POST /groups with parent_group_id sets depth = parent.depth + 1."""
    token = make_auth_token(email="nested@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)

    parent = client.post(
        "/api/v1/groups", headers=headers, json={"name": "Root", "parent_group_id": None}
    )
    assert parent.status_code == 201
    parent_id = parent.json()["id"]

    child = client.post(
        "/api/v1/groups",
        headers=headers,
        json={"name": "Child", "parent_group_id": parent_id},
    )
    assert child.status_code == 201
    assert child.json()["depth"] == 1


def test_create_group_rejects_depth_exceeding_max(make_auth_token) -> None:
    """POST /groups returns 400 if parent has depth = 4 (would exceed max nesting)."""
    token = make_auth_token(email="deep@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)

    current_id = None
    for i in range(6):
        body = {"name": f"Level{i}", "parent_group_id": current_id}
        resp = client.post("/api/v1/groups", headers=headers, json=body)
        if i < 5:
            assert resp.status_code == 201, f"Level {i} should succeed"
            current_id = resp.json()["id"]
        else:
            assert resp.status_code == 400


def test_leave_group_non_member_returns_403(make_auth_token) -> None:
    """DELETE /groups/{id}/membership returns 403 if caller is not a member."""
    token_owner = make_auth_token(email="owner_leave@example.com")
    token_other = make_auth_token(email="other_leave@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_other = {"Authorization": f"Bearer {token_other}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_other)

    resp = client.post(
        "/api/v1/groups", headers=headers_owner, json={"name": "Private Group"}
    )
    group_id = resp.json()["id"]

    response = client.delete(
        f"/api/v1/groups/{group_id}/membership", headers=headers_other
    )
    assert response.status_code == 403


def test_sole_member_departure_deletes_group(make_auth_token) -> None:
    """DELETE /groups/{id}/membership by sole member deletes group (FR-021)."""
    token = make_auth_token(email="sole@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)

    resp = client.post(
        "/api/v1/groups", headers=headers, json={"name": "Solo Group"}
    )
    group_id = resp.json()["id"]

    leave = client.delete(f"/api/v1/groups/{group_id}/membership", headers=headers)
    assert leave.status_code == 204

    groups = client.get("/api/v1/groups", headers=headers)
    group_ids = [g["id"] for g in groups.json()]
    assert group_id not in group_ids


def test_owner_departure_promotes_oldest_member(make_auth_token) -> None:
    """Owner departure promotes member with smallest joined_at (FR-020)."""
    token_owner = make_auth_token(email="owner_promo@example.com")
    token_member = make_auth_token(email="member_promo@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_member = {"Authorization": f"Bearer {token_member}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_member)

    resp = client.post(
        "/api/v1/groups", headers=headers_owner, json={"name": "Promo Group"}
    )
    group_id = resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": None},
    )
    token_val = invite_resp.json()["token"]

    client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_member)

    leave = client.delete(f"/api/v1/groups/{group_id}/membership", headers=headers_owner)
    assert leave.status_code == 204

    groups_resp = client.get("/api/v1/groups", headers=headers_member)
    groups = groups_resp.json()
    member_groups = [g for g in groups if g["id"] == group_id]
    assert len(member_groups) == 1
    assert member_groups[0]["role"] == "owner"
