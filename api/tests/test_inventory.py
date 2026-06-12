"""Inventory router: product lookup chain, canonical products, item lifecycle,
staple auto-add, and shopping-list loop-close."""

import uuid
from unittest.mock import MagicMock, patch

from api.models import CanonicalProduct, InventoryItem, ProductCache, ShoppingItem

from .conftest import client


def _off_hit_mock(name: str = "Test Product") -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "status": 1,
        "product": {
            "product_name": name,
            "brands": "TestBrand",
            "categories_tags": ["en:fresh-dairy"],
        },
    }
    return mock


def _off_miss_mock() -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"status": 0, "status_verbose": "product not found"}
    return mock


def _create_canonical_product(
    headers: dict,
    group_id: str,
    *,
    name: str = "Test Yogurt",
    is_staple: bool = False,
    usual_location: str = "fridge",
) -> str:
    resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": name,
            "category": "fresh_dairy",
            "is_staple": is_staple,
            "usual_location": usual_location,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_inventory_item(headers: dict, group_id: str, cp_id: str) -> str:
    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Test Item", "location": "fridge"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ────────────────────────────────────────────────────────────────
# Barcode lookup chain: cache → Open Food Facts → 404
# ────────────────────────────────────────────────────────────────


def test_barcode_lookup_cache_hit_with_canonical_product(db_session, make_user, make_group) -> None:
    """Barcode in product_cache with canonical_product_id → 200 with populated field."""
    headers = make_user("barcode_cache@example.com")
    group_id = make_group(headers, "Cache Group")

    cp = CanonicalProduct(
        group_id=uuid.UUID(group_id),
        name="Milk",
        category="fresh_dairy",
        is_staple=False,
        usual_location="fridge",
    )
    db_session.add(cp)
    db_session.add(
        ProductCache(
            barcode="8718309975563",
            source="off",
            name="Campina Halfvolle Melk",
            brand="Campina",
            category="fresh_dairy",
            canonical_product_id=cp.id,
            raw_data={},
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/inventory/product/8718309975563")
    assert resp.status_code == 200
    data = resp.json()
    assert data["barcode"] == "8718309975563"
    assert data["name"] == "Campina Halfvolle Melk"
    assert data["canonical_product_id"] == str(cp.id)
    assert data["canonical_product_name"] == "Milk"


def test_barcode_lookup_off_hit_writes_cache() -> None:
    """Unknown barcode → OFF hit → cached, so the second call makes no external call."""
    barcode = "4006381333931"

    with patch("httpx.get", return_value=_off_hit_mock("Test Yogurt")):
        resp = client.get(f"/api/v1/inventory/product/{barcode}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["barcode"] == barcode
    assert data["source"] == "off"
    assert data["name"] == "Test Yogurt"
    assert data["canonical_product_id"] is None

    with patch("httpx.get", side_effect=AssertionError("should not call OFF")):
        resp2 = client.get(f"/api/v1/inventory/product/{barcode}")
    assert resp2.status_code == 200


def test_barcode_lookup_all_sources_miss_404() -> None:
    """Barcode unknown to all sources → 404."""
    with patch("httpx.get", return_value=_off_miss_mock()):
        resp = client.get("/api/v1/inventory/product/1234567890123")
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────
# Canonical products
# ────────────────────────────────────────────────────────────────


def test_canonical_product_crud(make_user, make_group) -> None:
    """Create → list → patch; patching an unknown id returns 404."""
    headers = make_user("cp_crud@example.com")
    group_id = make_group(headers, "CP Group")

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": "Milk",
            "category": "fresh_dairy",
            "is_staple": True,
            "usual_location": "fridge",
            "expiry_days_default": 4,
        },
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["name"] == "Milk"
    assert data["is_staple"] is True
    assert data["usual_location"] == "fridge"
    assert data["expiry_days_default"] == 4
    assert data["group_id"] == group_id
    cp_id = data["id"]

    items = client.get(f"/api/v1/groups/{group_id}/canonical-products", headers=headers).json()
    assert [i["id"] for i in items] == [cp_id]

    patch_resp = client.patch(
        f"/api/v1/canonical-products/{cp_id}",
        headers=headers,
        json={"name": "Oat Milk", "is_staple": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Oat Milk"
    assert patch_resp.json()["is_staple"] is False

    missing = client.patch(
        f"/api/v1/canonical-products/{uuid.uuid4()}",
        headers=headers,
        json={"name": "Ghost Product"},
    )
    assert missing.status_code == 404


# ────────────────────────────────────────────────────────────────
# Inventory item lifecycle
# ────────────────────────────────────────────────────────────────


def test_inventory_item_lifecycle(db_session, make_user, make_group) -> None:
    """Create (barcode + manual) → cache association → status cycle ok→low→out→ok
    → expiry patch → removal with reason → removed item excluded from list."""
    headers = make_user("inv_lifecycle@example.com")
    group_id = make_group(headers, "Lifecycle Group")
    cp_id = _create_canonical_product(headers, group_id)

    barcode = "8718309975563"
    pc = ProductCache(barcode=barcode, source="off", name="Campina Yogurt", raw_data={})
    db_session.add(pc)
    db_session.commit()

    # Barcode-originated item; creating it associates the cache row with the product
    barcode_resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={
            "canonical_product_id": cp_id,
            "barcode": barcode,
            "name": "Campina Yogurt",
            "location": "fridge",
            "expiry_date": "10-06-2026",
        },
    )
    assert barcode_resp.status_code == 201
    item = barcode_resp.json()
    assert item["barcode"] == barcode
    assert item["status"] == "ok"
    assert item["expiry_date"] == "10-06-2026"
    item_id = item["id"]

    db_session.refresh(pc)
    assert str(pc.canonical_product_id) == cp_id

    # Manual item (no barcode)
    manual_resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Homemade Yogurt", "location": "fridge"},
    )
    assert manual_resp.status_code == 201
    assert manual_resp.json()["barcode"] is None
    manual_id = manual_resp.json()["id"]

    listing = client.get(f"/api/v1/groups/{group_id}/inventory", headers=headers).json()
    assert {i["id"] for i in listing} == {item_id, manual_id}

    # Status cycle ok → low → out → ok (out items stay listed as "ghosts")
    for status in ("low", "out", "ok"):
        resp = client.patch(
            f"/api/v1/inventory/{item_id}", headers=headers, json={"status": status}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == status

    expiry_resp = client.patch(
        f"/api/v1/inventory/{item_id}", headers=headers, json={"expiry_date": "20-12-2026"}
    )
    assert expiry_resp.status_code == 200
    assert expiry_resp.json()["expiry_date"] == "20-12-2026"

    # Removal is soft-delete with a mandatory reason
    delete_resp = client.request(
        "DELETE",
        f"/api/v1/inventory/{item_id}",
        headers=headers,
        json={"removed_reason": "thrown"},
    )
    assert delete_resp.status_code == 204

    row = db_session.get(InventoryItem, uuid.UUID(item_id))
    assert row is not None
    assert row.removed_at is not None
    assert row.removed_reason == "thrown"

    remaining = client.get(f"/api/v1/groups/{group_id}/inventory", headers=headers).json()
    assert [i["id"] for i in remaining] == [manual_id]


def test_inventory_validation_errors(make_user, make_group) -> None:
    """Invalid payloads and unknown ids: 422s and 404s."""
    headers = make_user("inv_validation@example.com")
    group_id = make_group(headers, "Validation Group")
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    cases = [
        ("PATCH", f"/api/v1/inventory/{item_id}", {"status": "invalid_status"}, 422),
        ("PATCH", f"/api/v1/inventory/{uuid.uuid4()}", {"status": "low"}, 404),
        ("DELETE", f"/api/v1/inventory/{item_id}", {}, 422),
        ("DELETE", f"/api/v1/inventory/{item_id}", {"removed_reason": "vanished"}, 422),
        ("DELETE", f"/api/v1/inventory/{uuid.uuid4()}", {"removed_reason": "used"}, 404),
    ]
    for method, url, body, expected in cases:
        resp = client.request(method, url, headers=headers, json=body)
        assert resp.status_code == expected, f"{method} {url} {body} → {resp.status_code}"


# ────────────────────────────────────────────────────────────────
# Staple auto-add to shopping list
# ────────────────────────────────────────────────────────────────


def test_staple_low_auto_adds_to_shopping_list(make_user, make_group) -> None:
    """Staple→low creates one unchecked shopping item (never duplicated while
    still listed); non-staples never auto-add."""
    headers = make_user("staple@example.com")
    group_id = make_group(headers, "Staple Group")
    staple_id = _create_canonical_product(headers, group_id, name="Milk", is_staple=True)
    staple_item = _create_inventory_item(headers, group_id, staple_id)
    treat_id = _create_canonical_product(headers, group_id, name="Treats", is_staple=False)
    treat_item = _create_inventory_item(headers, group_id, treat_id)

    resp = client.patch(f"/api/v1/inventory/{staple_item}", headers=headers, json={"status": "low"})
    assert resp.status_code == 200
    assert resp.json()["shopping_item_created"] is True
    assert resp.json()["shopping_item_name"] == "Milk"

    shopping = client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers).json()
    milk = [s for s in shopping if s["name"] == "Milk"]
    assert len(milk) == 1
    assert milk[0]["checked"] is False
    assert milk[0]["canonical_product_id"] == staple_id

    # Cycle back to ok and low again — the unchecked item is still listed, no duplicate
    client.patch(f"/api/v1/inventory/{staple_item}", headers=headers, json={"status": "ok"})
    again = client.patch(
        f"/api/v1/inventory/{staple_item}", headers=headers, json={"status": "low"}
    )
    assert again.json()["shopping_item_created"] is False

    # Non-staple going low never auto-adds
    treat_resp = client.patch(
        f"/api/v1/inventory/{treat_item}", headers=headers, json={"status": "low"}
    )
    assert treat_resp.json()["shopping_item_created"] is False

    shopping = client.get(f"/api/v1/groups/{group_id}/shopping", headers=headers).json()
    assert [s["name"] for s in shopping] == ["Milk"]


# ────────────────────────────────────────────────────────────────
# Shopping-list loop-close
# ────────────────────────────────────────────────────────────────


def test_from_shopping_loop_close(db_session, make_user, make_group) -> None:
    """Checked shopping items with a canonical product become inventory rows;
    unlinked items are skipped; an empty id list is a 422."""
    headers = make_user("loop@example.com")
    group_id = make_group(headers, "Loop Group")
    cp_id = _create_canonical_product(headers, group_id, name="Milk", usual_location="fridge")

    def _add_shopping(name: str, canonical_product_id: str | None) -> str:
        item = ShoppingItem(
            group_id=uuid.UUID(group_id),
            name=name,
            checked=True,
            canonical_product_id=(
                uuid.UUID(canonical_product_id) if canonical_product_id else None
            ),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return str(item.id)

    linked_id = _add_shopping("Milk", cp_id)
    unlinked_id = _add_shopping("Mystery", None)

    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory/from-shopping",
        headers=headers,
        json={"shopping_item_ids": [linked_id, unlinked_id]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["skipped"] == [unlinked_id]
    assert len(data["created"]) == 1
    created = data["created"][0]
    assert created["canonical_product_id"] == cp_id
    assert created["location"] == "fridge"
    assert created["status"] == "ok"
    assert created["name"] == "Milk"

    listing = client.get(f"/api/v1/groups/{group_id}/inventory", headers=headers).json()
    assert any(i["id"] == created["id"] for i in listing)

    empty = client.post(
        f"/api/v1/groups/{group_id}/inventory/from-shopping",
        headers=headers,
        json={"shopping_item_ids": []},
    )
    assert empty.status_code == 422
