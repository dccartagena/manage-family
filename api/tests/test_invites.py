"""Failing tests for invites router — must fail before api/routers/invites.py is implemented."""

import uuid
from datetime import UTC, datetime, timedelta

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_create_invite_requires_auth() -> None:
    """POST /groups/{id}/invites without auth returns 401."""
    response = client.post(
        f"/api/v1/groups/{uuid.uuid4()}/invites",
        json={"expires_at": None, "max_uses": None},
    )
    assert response.status_code == 401


def test_accept_invite_requires_auth() -> None:
    """POST /invites/{token}/accept without auth returns 401."""
    response = client.post("/api/v1/invites/sometoken/accept")
    assert response.status_code == 401


def test_create_invite_owner_only(make_auth_token) -> None:
    """POST /groups/{id}/invites returns 403 for non-owner."""
    token_owner = make_auth_token(email="inv_owner@example.com")
    token_member = make_auth_token(email="inv_member@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_member = {"Authorization": f"Bearer {token_member}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_member)

    resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Owner Only Group"})
    group_id = resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": None},
    )
    token_val = invite_resp.json()["token"]
    client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_member)

    response = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_member,
        json={"expires_at": None, "max_uses": None},
    )
    assert response.status_code == 403


def test_create_invite_generates_unique_token(make_auth_token) -> None:
    """POST /groups/{id}/invites generates unique 64-char hex token."""
    token = make_auth_token(email="inv_unique@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)

    resp = client.post("/api/v1/groups", headers=headers, json={"name": "Token Group"})
    group_id = resp.json()["id"]

    invite1 = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers,
        json={"expires_at": None, "max_uses": None},
    )
    invite2 = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers,
        json={"expires_at": None, "max_uses": None},
    )

    assert invite1.status_code == 201
    assert invite2.status_code == 201
    tok1 = invite1.json()["token"]
    tok2 = invite2.json()["token"]
    assert len(tok1) == 64
    assert len(tok2) == 64
    assert tok1 != tok2


def test_accept_invite_grants_membership(make_auth_token) -> None:
    """POST /invites/{token}/accept grants membership and returns group info."""
    token_owner = make_auth_token(email="inv_acc_owner@example.com")
    token_joiner = make_auth_token(email="inv_acc_joiner@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_joiner = {"Authorization": f"Bearer {token_joiner}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_joiner)

    resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Join Test Group"})
    group_id = resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": None},
    )
    assert invite_resp.status_code == 201
    token_val = invite_resp.json()["token"]

    accept_resp = client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_joiner)
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["group_id"] == group_id
    assert data["role"] == "member"
    assert "group_name" in data

    groups_resp = client.get("/api/v1/groups", headers=headers_joiner)
    group_ids = [g["id"] for g in groups_resp.json()]
    assert group_id in group_ids


def test_accept_expired_invite_returns_410(make_auth_token) -> None:
    """POST /invites/{token}/accept returns 410 for expired token."""
    token_owner = make_auth_token(email="inv_exp_owner@example.com")
    token_joiner = make_auth_token(email="inv_exp_joiner@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_joiner = {"Authorization": f"Bearer {token_joiner}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_joiner)

    resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Expired Group"})
    group_id = resp.json()["id"]

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": past, "max_uses": None},
    )
    token_val = invite_resp.json()["token"]

    accept_resp = client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_joiner)
    assert accept_resp.status_code == 410


def test_accept_exhausted_invite_returns_410(make_auth_token) -> None:
    """POST /invites/{token}/accept returns 410 when max_uses reached."""
    token_owner = make_auth_token(email="inv_exh_owner@example.com")
    token_j1 = make_auth_token(email="inv_exh_j1@example.com")
    token_j2 = make_auth_token(email="inv_exh_j2@example.com")
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_j1 = {"Authorization": f"Bearer {token_j1}"}
    headers_j2 = {"Authorization": f"Bearer {token_j2}"}

    client.post("/api/v1/person/sync", headers=headers_owner)
    client.post("/api/v1/person/sync", headers=headers_j1)
    client.post("/api/v1/person/sync", headers=headers_j2)

    resp = client.post("/api/v1/groups", headers=headers_owner, json={"name": "Exhausted Group"})
    group_id = resp.json()["id"]

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=headers_owner,
        json={"expires_at": None, "max_uses": 1},
    )
    token_val = invite_resp.json()["token"]

    first = client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_j1)
    assert first.status_code == 200

    second = client.post(f"/api/v1/invites/{token_val}/accept", headers=headers_j2)
    assert second.status_code == 410
