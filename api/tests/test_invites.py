"""Invites router: owner-only creation and expiry.

The happy path (generate → accept → exhaustion) is covered by
test_critical_paths.test_group_invite_accept_flow.
"""

from datetime import UTC, datetime, timedelta

from .conftest import client


def test_create_invite_owner_only(make_user, make_group) -> None:
    """POST /groups/{id}/invites returns 403 for a member who is not the owner."""
    owner = make_user("inv_owner@example.com")
    member = make_user("inv_member@example.com")
    group_id = make_group(owner, "Owner Only Group")

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner,
        json={"expires_at": None, "max_uses": None},
    )
    client.post(f"/api/v1/invites/{invite_resp.json()['token']}/accept", headers=member)

    response = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=member,
        json={"expires_at": None, "max_uses": None},
    )
    assert response.status_code == 403


def test_accept_expired_invite_returns_410(make_user, make_group) -> None:
    """POST /invites/{token}/accept returns 410 for an expired token."""
    owner = make_user("inv_exp_owner@example.com")
    joiner = make_user("inv_exp_joiner@example.com")
    group_id = make_group(owner, "Expired Group")

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner,
        json={"expires_at": past, "max_uses": None},
    )

    accept_resp = client.post(
        f"/api/v1/invites/{invite_resp.json()['token']}/accept", headers=joiner
    )
    assert accept_resp.status_code == 410
