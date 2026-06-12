"""Groups router: creation/listing, nesting depth, and departure rules."""

from .conftest import client


def test_create_and_list_groups(make_user, make_group) -> None:
    """POST /groups makes the caller owner; GET /groups lists only own memberships."""
    user_a = make_user("list_a@example.com")
    user_b = make_user("list_b@example.com")

    resp = client.post(
        "/api/v1/groups",
        headers=user_a,
        json={"name": "Smith Family", "parent_group_id": None},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Smith Family"
    assert data["depth"] == 0
    assert data["role"] == "owner"

    make_group(user_b, "Group B")

    names_a = [g["name"] for g in client.get("/api/v1/groups", headers=user_a).json()]
    assert "Smith Family" in names_a
    assert "Group B" not in names_a


def test_nested_group_depth_and_max(make_user) -> None:
    """Child depth = parent.depth + 1; nesting beyond depth 4 returns 400."""
    headers = make_user("nested@example.com")

    current_id = None
    for level in range(6):
        resp = client.post(
            "/api/v1/groups",
            headers=headers,
            json={"name": f"Level{level}", "parent_group_id": current_id},
        )
        if level < 5:
            assert resp.status_code == 201, f"Level {level} should succeed"
            assert resp.json()["depth"] == level
            current_id = resp.json()["id"]
        else:
            assert resp.status_code == 400


def test_sole_member_departure_deletes_group(make_user, make_group) -> None:
    """DELETE /groups/{id}/membership by sole member deletes group (FR-021)."""
    headers = make_user("sole@example.com")
    group_id = make_group(headers, "Solo Group")

    leave = client.delete(f"/api/v1/groups/{group_id}/membership", headers=headers)
    assert leave.status_code == 204

    group_ids = [g["id"] for g in client.get("/api/v1/groups", headers=headers).json()]
    assert group_id not in group_ids


def test_owner_departure_promotes_oldest_member(make_user, make_group) -> None:
    """Owner departure promotes member with smallest joined_at (FR-020)."""
    owner = make_user("owner_promo@example.com")
    member = make_user("member_promo@example.com")
    group_id = make_group(owner, "Promo Group")

    invite_resp = client.post(
        f"/api/v1/groups/{group_id}/invites",
        headers=owner,
        json={"expires_at": None, "max_uses": None},
    )
    client.post(f"/api/v1/invites/{invite_resp.json()['token']}/accept", headers=member)

    leave = client.delete(f"/api/v1/groups/{group_id}/membership", headers=owner)
    assert leave.status_code == 204

    member_groups = [
        g for g in client.get("/api/v1/groups", headers=member).json() if g["id"] == group_id
    ]
    assert len(member_groups) == 1
    assert member_groups[0]["role"] == "owner"
