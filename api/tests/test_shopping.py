"""Failing tests for shopping router — must fail before api/routers/shopping.py is implemented."""

import uuid

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_list_shopping_requires_auth() -> None:
    """GET /groups/{id}/shopping without auth returns 401."""
    response = client.get(f"/api/v1/groups/{uuid.uuid4()}/shopping")
    assert response.status_code == 401


def test_add_shopping_requires_auth() -> None:
    """POST /groups/{id}/shopping without auth returns 401."""
    response = client.post(f"/api/v1/groups/{uuid.uuid4()}/shopping", json={"name": "Milk"})
    assert response.status_code == 401


def test_patch_shopping_requires_auth() -> None:
    """PATCH /shopping/{id} without auth returns 401."""
    response = client.patch(f"/api/v1/shopping/{uuid.uuid4()}", json={"checked": True})
    assert response.status_code == 401


def test_delete_shopping_requires_auth() -> None:
    """DELETE /shopping/{id} without auth returns 401."""
    response = client.delete(f"/api/v1/shopping/{uuid.uuid4()}")
    assert response.status_code == 401


def test_add_and_list_shopping_item(make_auth_token) -> None:
    """POST /groups/{id}/shopping creates item; GET lists it."""
    token = make_auth_token(email="shopping_list@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Shopping Group"})
    group_id = group_resp.json()["id"]

    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=headers,
        json={"name": "Milk"},
    )
    assert add_resp.status_code == 201
    item = add_resp.json()
    assert item["name"] == "Milk"
    assert item["checked"] is False
    assert "id" in item
    assert "updated_at" in item

    list_resp = client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Milk"


def test_patch_shopping_item_server_sets_updated_at(make_auth_token) -> None:
    """PATCH /shopping/{id} updates item; server always sets updated_at (last-write-wins arbiter).

    Client must never be able to set updated_at directly.
    """
    token = make_auth_token(email="shopping_patch@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Patch Group"})
    group_id = group_resp.json()["id"]

    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=headers,
        json={"name": "Eggs"},
    )
    item_id = add_resp.json()["id"]
    original_updated_at = add_resp.json()["updated_at"]

    patch_resp = client.patch(
        f"/api/v1/shopping/{item_id}",
        headers=headers,
        json={"checked": True},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["checked"] is True
    assert patched["name"] == "Eggs"
    # Server must set updated_at — it must be present in response
    assert "updated_at" in patched
    # updated_at should be >= original (server always refreshes)
    assert patched["updated_at"] >= original_updated_at


def test_patch_shopping_item_name(make_auth_token) -> None:
    """PATCH /shopping/{id} can rename item."""
    token = make_auth_token(email="shopping_rename@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Rename Group"})
    group_id = group_resp.json()["id"]

    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=headers,
        json={"name": "Butter"},
    )
    item_id = add_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/shopping/{item_id}",
        headers=headers,
        json={"name": "Salted Butter"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Salted Butter"


def test_delete_shopping_item(make_auth_token) -> None:
    """DELETE /shopping/{id} removes item; subsequent GET returns empty list."""
    token = make_auth_token(email="shopping_delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post("/api/v1/groups", headers=headers, json={"name": "Delete Group"})
    group_id = group_resp.json()["id"]

    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=headers,
        json={"name": "Juice"},
    )
    item_id = add_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/shopping/{item_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers)
    assert list_resp.json() == []


def test_non_member_cannot_list_shopping(make_auth_token) -> None:
    """GET /groups/{id}/shopping returns 403 for non-members."""
    owner_token = make_auth_token(email="shop_owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Private Shopping"}
    )
    group_id = group_resp.json()["id"]

    other_token = make_auth_token(email="shop_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.get(f"/api/v1/groups/{group_id}/shopping", headers=other_headers)
    assert response.status_code == 403


def test_non_member_cannot_add_shopping(make_auth_token) -> None:
    """POST /groups/{id}/shopping returns 403 for non-members."""
    owner_token = make_auth_token(email="shop_owner2@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Private Shopping 2"}
    )
    group_id = group_resp.json()["id"]

    other_token = make_auth_token(email="shop_outsider2@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=other_headers,
        json={"name": "Bread"},
    )
    assert response.status_code == 403


def test_non_member_cannot_patch_shopping(make_auth_token) -> None:
    """PATCH /shopping/{id} returns 403 for non-members."""
    owner_token = make_auth_token(email="shop_patch_owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/api/v1/person/sync", headers=owner_headers)
    group_resp = client.post(
        "/api/v1/groups", headers=owner_headers, json={"name": "Patch Private"}
    )
    group_id = group_resp.json()["id"]
    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=owner_headers,
        json={"name": "Cheese"},
    )
    item_id = add_resp.json()["id"]

    other_token = make_auth_token(email="shop_patch_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    response = client.patch(
        f"/api/v1/shopping/{item_id}",
        headers=other_headers,
        json={"checked": True},
    )
    assert response.status_code == 403
