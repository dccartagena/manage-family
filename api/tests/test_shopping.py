"""Shopping router: full CRUD flow with server-managed updated_at."""

from .conftest import client


def test_shopping_item_crud_flow(make_user, make_group) -> None:
    """Add → list → check off → rename → delete; the server always sets
    updated_at (last-write-wins arbiter for offline sync)."""
    headers = make_user("shopping_flow@example.com")
    group_id = make_group(headers, "Shopping Group")

    add_resp = client.post(
        f"/api/v1/groups/{group_id}/shopping",
        headers=headers,
        json={"name": "Milk"},
    )
    assert add_resp.status_code == 201
    item = add_resp.json()
    assert item["name"] == "Milk"
    assert item["checked"] is False
    item_id = item["id"]
    original_updated_at = item["updated_at"]

    items = client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers).json()
    assert [i["name"] for i in items] == ["Milk"]

    check_resp = client.patch(
        f"/api/v1/shopping/{item_id}",
        headers=headers,
        json={"checked": True},
    )
    assert check_resp.status_code == 200
    checked = check_resp.json()
    assert checked["checked"] is True
    assert checked["name"] == "Milk"
    # Server must refresh updated_at — clients can never set it directly
    assert checked["updated_at"] >= original_updated_at

    rename_resp = client.patch(
        f"/api/v1/shopping/{item_id}",
        headers=headers,
        json={"name": "Oat Milk"},
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["name"] == "Oat Milk"

    delete_resp = client.delete(f"/api/v1/shopping/{item_id}", headers=headers)
    assert delete_resp.status_code == 204
    assert client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers).json() == []
