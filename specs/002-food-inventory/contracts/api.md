# API Contracts: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04

All endpoints extend the existing REST API at base path `/api/v1`.
Authentication: `Authorization: Bearer {supabase_access_token}` on all endpoints.
Error envelope (existing convention):
```json
{ "detail": "<human-readable message>" }
```

---

## Product Lookup

### `GET /inventory/product/{barcode}`

Look up a product by EAN-13 barcode. Checks sources in order:
1. `product_cache` (local DB)
2. Open Food Facts
3. AH unofficial API
4. Jumbo unofficial API

On hit: writes to `product_cache` (if not already cached), returns unified product schema.
On miss after all sources: returns 404.

No auth required for this endpoint (barcode lookup is not sensitive). Bearer token still
accepted but not validated.

**Path parameter**: `barcode` — 13-digit EAN-13 string.

**Response 200**:
```json
{
  "barcode": "8718309975563",
  "name": "Campina Halfvolle Melk",
  "brand": "Campina",
  "category": "fresh_dairy",
  "source": "off",
  "canonical_product_id": "<uuid|null>",
  "canonical_product_name": "Milk"
}
```

`canonical_product_id` and `canonical_product_name` are `null` when the barcode is not yet
associated with a canonical product for this household.

**Response 404**: Product not found in any source. Frontend opens manual form.

---

## Canonical Products

### `GET /groups/{group_id}/canonical-products`

List all canonical products for the household. Used to populate the "associate with" picker.

**Response 200**:
```json
[
  {
    "id": "<uuid>",
    "group_id": "<uuid>",
    "name": "Milk",
    "category": "fresh_dairy",
    "is_staple": true,
    "usual_location": "fridge",
    "expiry_days_default": 4
  }
]
```

**Errors**: 403 if caller is not a member of the group.

---

### `POST /groups/{group_id}/canonical-products`

Create a new canonical product for the household.

**Request**:
```json
{
  "name": "Milk",
  "category": "fresh_dairy",
  "is_staple": true,
  "usual_location": "fridge",
  "expiry_days_default": 4
}
```

`expiry_days_default` is optional; omit to use the category default.

**Response 201**:
```json
{
  "id": "<uuid>",
  "group_id": "<uuid>",
  "name": "Milk",
  "category": "fresh_dairy",
  "is_staple": true,
  "usual_location": "fridge",
  "expiry_days_default": 4
}
```

**Errors**: 403 if not a member; 422 if validation fails.

---

### `PATCH /canonical-products/{canonical_product_id}`

Update a canonical product (e.g., toggle `is_staple`, change `usual_location`).

**Request** (all fields optional):
```json
{
  "name": "Oat Milk",
  "is_staple": false,
  "usual_location": "pantry",
  "expiry_days_default": null
}
```

**Response 200**: Updated canonical product (same schema as POST 201 response).

**Errors**: 403 if not a member of the owning group; 404 if not found.

---

## Inventory Items

### `GET /groups/{group_id}/inventory`

List all active inventory items for the household. Active = `removed_at IS NULL`.
Includes `status = out` items (ghost items). Frontend applies grouping and sorting.

**Response 200**:
```json
[
  {
    "id": "<uuid>",
    "group_id": "<uuid>",
    "canonical_product_id": "<uuid>",
    "canonical_product_name": "Milk",
    "barcode": "8718309975563",
    "name": "Campina Halfvolle Melk",
    "location": "fridge",
    "status": "ok",
    "expiry_date": "10-06-2026",
    "added_by": "<uuid>",
    "added_at": "2026-06-04T10:00:00Z"
  }
]
```

`expiry_date` is serialized as `DD-MM-YYYY` string (nullable; `null` when not set).
`barcode` is nullable (manual items have no barcode).

**Errors**: 403 if not a member.

---

### `POST /groups/{group_id}/inventory`

Add a new inventory item. Can originate from barcode scan or manual entry.

**Request**:
```json
{
  "canonical_product_id": "<uuid>",
  "barcode": "8718309975563",
  "name": "Campina Halfvolle Melk",
  "location": "fridge",
  "expiry_date": "10-06-2026"
}
```

`barcode` and `expiry_date` are optional. `status` always starts as `ok` (server-set).

**Response 201**: Created inventory item (same schema as GET list item).

**Side-effect**: If a new `canonical_product_id` is being associated with a `barcode` for
the first time, `product_cache.canonical_product_id` is updated.

**Errors**: 403 if not a member; 404 if `canonical_product_id` does not belong to this group;
422 if validation fails.

---

### `PATCH /inventory/{item_id}`

Update status and/or expiry date. Used for tap-to-cycle and expiry edits.

**Request** (all fields optional):
```json
{
  "status": "low",
  "expiry_date": "12-06-2026"
}
```

**Response 200**: Updated inventory item.

**Side-effect** when `status` is set to `low`:
If `canonical_product.is_staple = true` and no unchecked `shopping_item` exists for
`canonical_product_id` in this group, a new `shopping_item` is created and the response
includes a `shopping_item_created` flag:

```json
{
  "id": "<uuid>",
  "status": "low",
  ...
  "shopping_item_created": true,
  "shopping_item_name": "Milk"
}
```

`shopping_item_created` is `false` (or absent) when no shopping list entry was created.

**Errors**: 403 if not a member; 404 if not found; 422 if status value is invalid.

---

### `DELETE /inventory/{item_id}`

Soft-delete an inventory item (removal). Sets `removed_at` and `removed_reason`.

**Request**:
```json
{
  "removed_reason": "used"
}
```

`removed_reason` must be one of `used`, `thrown`, `transferred`.

**Response 204**: No content.

**Errors**: 403 if not a member; 404 if not found; 422 if `removed_reason` is missing or invalid.

---

## Shopping List Loop-Close

### `POST /groups/{group_id}/inventory/from-shopping`

Batch-create inventory items from a list of bought shopping item IDs. Pre-fills
`location` and `canonical_product_id` from the canonical product record.

**Request**:
```json
{
  "shopping_item_ids": ["<uuid>", "<uuid>"]
}
```

**Response 201**:
```json
{
  "created": [
    {
      "id": "<uuid>",
      "name": "Milk",
      "location": "fridge",
      "canonical_product_id": "<uuid>",
      "status": "ok"
    }
  ],
  "skipped": ["<uuid>"]
}
```

`skipped` contains shopping item IDs that had no `canonical_product_id` (cannot be
auto-added to inventory; user must add manually). These items are not modified.

**Errors**: 403 if not a member; 422 if list is empty.
