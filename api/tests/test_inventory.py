"""Integration tests for inventory router — Phases 3 & 4: US1 + US2."""
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from api.main import app
from api.models import CanonicalProduct, InventoryItem, ProductCache
from fastapi.testclient import TestClient

client = TestClient(app)


def _make_user_and_group(
    email: str,
    group_name: str,
    make_auth_token,
) -> tuple[str, str, dict[str, str]]:
    """Create a person + group; return (token, group_id, auth headers)."""
    token = make_auth_token(email=email)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)
    group_resp = client.post(
        "/api/v1/groups", headers=headers, json={"name": group_name}
    )
    assert group_resp.status_code == 201
    return token, group_resp.json()["id"], headers


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


def _create_canonical_product(headers: dict, group_id: str) -> str:
    """Create a canonical product; return its id."""
    resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": "Test Yogurt",
            "category": "fresh_dairy",
            "is_staple": False,
            "usual_location": "fridge",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ────────────────────────────────────────────────────────────────
# T012: GET /inventory/product/{barcode}
# ────────────────────────────────────────────────────────────────


def test_barcode_lookup_cache_hit_with_canonical_product(
    db_session, make_auth_token
) -> None:
    """(a) barcode in product_cache with canonical_product_id → 200 with populated field."""
    _, group_id, headers = _make_user_and_group(
        "barcode_cache@example.com", "Cache Group", make_auth_token
    )

    cp = CanonicalProduct(
        group_id=uuid.UUID(group_id),
        name="Milk",
        category="fresh_dairy",
        is_staple=False,
        usual_location="fridge",
    )
    db_session.add(cp)

    pc = ProductCache(
        barcode="8718309975563",
        source="off",
        name="Campina Halfvolle Melk",
        brand="Campina",
        category="fresh_dairy",
        canonical_product_id=cp.id,
        raw_data={},
    )
    db_session.add(pc)
    db_session.commit()

    resp = client.get("/api/v1/inventory/product/8718309975563")
    assert resp.status_code == 200
    data = resp.json()
    assert data["barcode"] == "8718309975563"
    assert data["name"] == "Campina Halfvolle Melk"
    assert data["canonical_product_id"] == str(cp.id)
    assert data["canonical_product_name"] == "Milk"


def test_barcode_lookup_off_hit_writes_cache(make_auth_token) -> None:
    """(b) unknown barcode → OFF mock hit → writes to cache → 200."""
    barcode = "4006381333931"

    with patch("httpx.get", return_value=_off_hit_mock("Test Yogurt")):
        resp = client.get(f"/api/v1/inventory/product/{barcode}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["barcode"] == barcode
    assert data["source"] == "off"
    assert data["name"] == "Test Yogurt"
    assert data["canonical_product_id"] is None

    # Second call must be a cache hit (no external call raised)
    with patch("httpx.get", side_effect=AssertionError("should not call OFF")):
        resp2 = client.get(f"/api/v1/inventory/product/{barcode}")
    assert resp2.status_code == 200


def test_barcode_lookup_all_sources_miss_404(make_auth_token) -> None:
    """(c) barcode unknown to all sources → 404."""
    barcode = "1234567890123"

    with patch("httpx.get", return_value=_off_miss_mock()):
        resp = client.get(f"/api/v1/inventory/product/{barcode}")

    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────
# T013: POST /groups/{group_id}/canonical-products
# ────────────────────────────────────────────────────────────────


def test_create_canonical_product_member(make_auth_token) -> None:
    """(a) member creates product → 201 with correct fields."""
    _, group_id, headers = _make_user_and_group(
        "cp_create@example.com", "CP Group", make_auth_token
    )

    resp = client.post(
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
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Milk"
    assert data["category"] == "fresh_dairy"
    assert data["is_staple"] is True
    assert data["usual_location"] == "fridge"
    assert data["expiry_days_default"] == 4
    assert "id" in data
    assert data["group_id"] == group_id


def test_create_canonical_product_non_member(make_auth_token) -> None:
    """(b) non-member → 403."""
    _, group_id, _ = _make_user_and_group(
        "cp_owner2@example.com", "CP Group 2", make_auth_token
    )

    other_token = make_auth_token(email="cp_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=other_headers,
        json={
            "name": "Milk",
            "category": "fresh_dairy",
            "is_staple": False,
            "usual_location": "fridge",
        },
    )
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────
# T014: GET /groups/{group_id}/canonical-products
# ────────────────────────────────────────────────────────────────


def test_list_canonical_products_member(make_auth_token) -> None:
    """Member gets list of canonical products for their group."""
    _, group_id, headers = _make_user_and_group(
        "cp_list@example.com", "List Group", make_auth_token
    )

    client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": "Coffee",
            "category": "dry_goods",
            "is_staple": True,
            "usual_location": "pantry",
        },
    )

    resp = client.get(
        f"/api/v1/groups/{group_id}/canonical-products", headers=headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Coffee"


def test_list_canonical_products_non_member(make_auth_token) -> None:
    """Non-member → 403."""
    _, group_id, _ = _make_user_and_group(
        "cp_list_owner@example.com", "List Group 2", make_auth_token
    )

    other_token = make_auth_token(email="cp_list_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    resp = client.get(
        f"/api/v1/groups/{group_id}/canonical-products", headers=other_headers
    )
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────
# T015: PATCH /canonical-products/{id}
# ────────────────────────────────────────────────────────────────


def test_patch_canonical_product_member(make_auth_token) -> None:
    """Member updates name and is_staple → 200 with updated values."""
    _, group_id, headers = _make_user_and_group(
        "cp_patch@example.com", "Patch CP Group", make_auth_token
    )

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": "Butter",
            "category": "fresh_dairy",
            "is_staple": False,
            "usual_location": "fridge",
        },
    )
    cp_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/canonical-products/{cp_id}",
        headers=headers,
        json={"name": "Salted Butter", "is_staple": True},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Salted Butter"
    assert data["is_staple"] is True


def test_patch_canonical_product_non_member(make_auth_token) -> None:
    """Non-member → 403."""
    _, group_id, headers = _make_user_and_group(
        "cp_patch_owner@example.com", "Patch CP Group 2", make_auth_token
    )

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/canonical-products",
        headers=headers,
        json={
            "name": "Eggs",
            "category": "eggs",
            "is_staple": False,
            "usual_location": "fridge",
        },
    )
    cp_id = create_resp.json()["id"]

    other_token = make_auth_token(email="cp_patch_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    resp = client.patch(
        f"/api/v1/canonical-products/{cp_id}",
        headers=other_headers,
        json={"name": "Free Range Eggs"},
    )
    assert resp.status_code == 403


def test_patch_canonical_product_not_found(make_auth_token) -> None:
    """Unknown id → 404."""
    token = make_auth_token(email="cp_patch_404@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    resp = client.patch(
        f"/api/v1/canonical-products/{uuid.uuid4()}",
        headers=headers,
        json={"name": "Ghost Product"},
    )
    assert resp.status_code == 404


# ────────────────────────────────────────────────────────────────
# T016: POST /groups/{group_id}/inventory
# ────────────────────────────────────────────────────────────────


def test_create_inventory_item_with_barcode(db_session, make_auth_token) -> None:
    """(a) barcode-originated item creates row with correct fields."""
    _, group_id, headers = _make_user_and_group(
        "inv_barcode@example.com", "Inv Barcode Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)

    pc = ProductCache(
        barcode="8718309975563",
        source="off",
        name="Campina Yogurt",
        raw_data={},
    )
    db_session.add(pc)
    db_session.commit()

    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={
            "canonical_product_id": cp_id,
            "barcode": "8718309975563",
            "name": "Campina Yogurt",
            "location": "fridge",
            "expiry_date": "10-06-2026",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["canonical_product_id"] == cp_id
    assert data["barcode"] == "8718309975563"
    assert data["name"] == "Campina Yogurt"
    assert data["location"] == "fridge"
    assert data["status"] == "ok"
    assert data["expiry_date"] == "10-06-2026"


def test_create_inventory_item_manual_no_barcode(make_auth_token) -> None:
    """(b) manual item (no barcode) creates row with barcode=null."""
    _, group_id, headers = _make_user_and_group(
        "inv_manual@example.com", "Inv Manual Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)

    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={
            "canonical_product_id": cp_id,
            "name": "Homemade Yogurt",
            "location": "fridge",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["barcode"] is None
    assert data["name"] == "Homemade Yogurt"
    assert data["status"] == "ok"


def test_create_inventory_item_updates_cache_association(
    db_session, make_auth_token
) -> None:
    """(c) new canonical association updates product_cache.canonical_product_id."""
    _, group_id, headers = _make_user_and_group(
        "inv_assoc@example.com", "Inv Assoc Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)

    barcode = "4004150201563"
    pc = ProductCache(
        barcode=barcode,
        source="off",
        name="Quark Naturel",
        raw_data={},
    )
    db_session.add(pc)
    db_session.commit()

    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={
            "canonical_product_id": cp_id,
            "barcode": barcode,
            "name": "Quark Naturel",
            "location": "fridge",
        },
    )
    assert resp.status_code == 201

    db_session.refresh(pc)
    assert str(pc.canonical_product_id) == cp_id


# ────────────────────────────────────────────────────────────────
# Shared helper for US2 tests
# ────────────────────────────────────────────────────────────────


def _create_inventory_item(headers: dict, group_id: str, cp_id: str) -> str:
    """Create an inventory item via POST; return its id."""
    resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Test Item", "location": "fridge"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ────────────────────────────────────────────────────────────────
# T026: GET /groups/{group_id}/inventory
# ────────────────────────────────────────────────────────────────


def test_list_inventory_excludes_removed_items(db_session, make_auth_token) -> None:
    """Returns only active items (removed_at IS NULL); removed items excluded."""
    _, group_id, headers = _make_user_and_group(
        "inv_list@example.com", "Inv List Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)

    resp1 = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Active Item", "location": "fridge"},
    )
    assert resp1.status_code == 201
    active_id = resp1.json()["id"]

    resp2 = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Removed Item", "location": "pantry"},
    )
    assert resp2.status_code == 201
    removed_id = uuid.UUID(resp2.json()["id"])

    removed_item = db_session.get(InventoryItem, removed_id)
    assert removed_item is not None
    removed_item.removed_at = datetime.utcnow()
    db_session.commit()

    resp = client.get(f"/api/v1/groups/{group_id}/inventory", headers=headers)
    assert resp.status_code == 200
    returned_ids = [i["id"] for i in resp.json()]
    assert active_id in returned_ids
    assert str(removed_id) not in returned_ids


def test_list_inventory_includes_out_status(db_session, make_auth_token) -> None:
    """status=out items are included (ghost items stay in list)."""
    _, group_id, headers = _make_user_and_group(
        "inv_out@example.com", "Inv Out Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)

    create_resp = client.post(
        f"/api/v1/groups/{group_id}/inventory",
        headers=headers,
        json={"canonical_product_id": cp_id, "name": "Out Item", "location": "fridge"},
    )
    assert create_resp.status_code == 201
    item_id = uuid.UUID(create_resp.json()["id"])

    inv_item = db_session.get(InventoryItem, item_id)
    assert inv_item is not None
    inv_item.status = "out"
    db_session.commit()

    resp = client.get(f"/api/v1/groups/{group_id}/inventory", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "out"


def test_list_inventory_non_member_403(make_auth_token) -> None:
    """Non-member cannot list inventory."""
    _, group_id, _ = _make_user_and_group(
        "inv_list_owner@example.com", "Inv List Group 2", make_auth_token
    )

    other_token = make_auth_token(email="inv_list_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    resp = client.get(f"/api/v1/groups/{group_id}/inventory", headers=other_headers)
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────
# T027: PATCH /inventory/{item_id}
# ────────────────────────────────────────────────────────────────


def test_patch_inventory_status_ok_to_low(make_auth_token) -> None:
    """ok→low status cycle; response includes shopping_item_created=false placeholder."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv@example.com", "Patch Inv Group", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        headers=headers,
        json={"status": "low"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "low"
    assert data["shopping_item_created"] is False


def test_patch_inventory_status_low_to_out(make_auth_token) -> None:
    """low→out status cycle."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv2@example.com", "Patch Inv Group 2", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    client.patch(f"/api/v1/inventory/{item_id}", headers=headers, json={"status": "low"})
    resp = client.patch(f"/api/v1/inventory/{item_id}", headers=headers, json={"status": "out"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "out"


def test_patch_inventory_status_out_to_ok(make_auth_token) -> None:
    """out→ok status cycle."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv3@example.com", "Patch Inv Group 3", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    client.patch(f"/api/v1/inventory/{item_id}", headers=headers, json={"status": "low"})
    client.patch(f"/api/v1/inventory/{item_id}", headers=headers, json={"status": "out"})
    resp = client.patch(f"/api/v1/inventory/{item_id}", headers=headers, json={"status": "ok"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_patch_inventory_expiry_date_update(make_auth_token) -> None:
    """expiry_date field update persists and serializes as DD-MM-YYYY."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv4@example.com", "Patch Inv Group 4", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        headers=headers,
        json={"expiry_date": "20-12-2026"},
    )
    assert resp.status_code == 200
    assert resp.json()["expiry_date"] == "20-12-2026"


def test_patch_inventory_non_member_403(make_auth_token) -> None:
    """Non-member → 403."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv_owner@example.com", "Patch Inv Group 5", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    other_token = make_auth_token(email="patch_inv_outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    client.post("/api/v1/person/sync", headers=other_headers)

    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        headers=other_headers,
        json={"status": "low"},
    )
    assert resp.status_code == 403


def test_patch_inventory_unknown_item_404(make_auth_token) -> None:
    """Unknown item → 404."""
    token = make_auth_token(email="patch_inv_404@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/person/sync", headers=headers)

    resp = client.patch(
        f"/api/v1/inventory/{uuid.uuid4()}",
        headers=headers,
        json={"status": "low"},
    )
    assert resp.status_code == 404


def test_patch_inventory_invalid_status_422(make_auth_token) -> None:
    """Invalid status value → 422."""
    _, group_id, headers = _make_user_and_group(
        "patch_inv5@example.com", "Patch Inv Group 6", make_auth_token
    )
    cp_id = _create_canonical_product(headers, group_id)
    item_id = _create_inventory_item(headers, group_id, cp_id)

    resp = client.patch(
        f"/api/v1/inventory/{item_id}",
        headers=headers,
        json={"status": "invalid_status"},
    )
    assert resp.status_code == 422
