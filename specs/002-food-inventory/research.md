# Research: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04

## Decision Log

### 1. Barcode Scanning Library

**Decision**: `@zxing/browser` — EAN-13 only, dynamically imported on the scanner page.

**Rationale**: `@zxing/browser` is the maintained browser port of the ZXing multi-format
barcode library. It decodes EAN-13 from a live video stream using WASM, with no native bridge
or app store dependency. The masterplan specifies it explicitly. Dynamic import keeps it out
of the main bundle; it only loads when the user opens the scan page.

**Alternatives considered**:
- `quagga2`: Pure JS, no WASM dependency — but EAN-13 accuracy is notably worse in low-light
  conditions common in kitchens. Rejected on accuracy grounds.
- Native `BarcodeDetector` API: Zero JS weight, but Safari support is absent as of 2026.
  Rejected on browser compatibility.

---

### 2. External Product Lookup Chain and API Abstractions

**Decision**: Lookup order is product_cache → Open Food Facts → AH → Jumbo.
All AH and Jumbo calls execute in `ProductLookupService` (FastAPI backend only).
Open Food Facts may be called from either frontend or backend.

**Rationale**: The household primarily shops at Aldi/Lidl, which have no known unofficial
APIs but whose products (international EAN-13 barcodes) are well-covered by Open Food Facts
(~27,000 Dutch products at 99.1% quality). AH and Jumbo cover the secondary stores.
Calling AH/Jumbo from the backend only keeps the unofficial APIs behind a single abstraction;
if they break or change, only `ProductLookupService` needs updating.

First-source-wins: whichever source returns a hit is written to `product_cache` and returned
immediately. Subsequent scans of the same barcode never hit external APIs.

**Reference implementations for AH and Jumbo**:
- `https://github.com/PaulVerhoeven1/grocy-dutch-supermarket` (Python, closest to this use case)
- `https://github.com/bartmachielsen/SupermarktConnector` (Python)

**Alternatives considered**:
- Calling all sources in parallel and merging results: adds complexity, wastes API calls for
  the common case where OFF already has the product. Rejected in favour of sequential chain.

---

### 3. Canonical Product Association on First Scan

**Decision**: When a barcode is cached but lacks a `canonical_product_id` for this group,
the backend returns the product data with `canonical_product_id: null`. The frontend shows
a suggestion based on `category`/`name` ("This looks like Milk — is that right?"). The user
confirms or creates a new canonical product. The association is written back to `product_cache`
on save.

**Rationale**: The `product_cache` is global (no `group_id`); the `canonical_product` is
group-scoped. A single barcode can therefore map to different canonical products in different
households (one household calls it "Plant milk", another "Oat milk"). The association is
stored on `product_cache.canonical_product_id` as a soft hint — each group resolves it
independently by looking at their own `canonical_product` records.

Wait — the spec says `product_cache.canonical_product_id` is a nullable FK. But if the cache
is global and canonical_products are group-scoped, this FK would store only one household's
association. This is acceptable: the first household to associate a barcode sets the hint for
all subsequent households (who can override it). The hint is used only for the suggestion prompt,
not as an authoritative mapping. This matches the spec intent.

---

### 4. ShoppingItem — Adding canonical_product_id

**Decision**: Add `canonical_product_id UUID NULLABLE FK → canonical_product(id)` to
`shopping_items`. Existing rows get `NULL` (no backfill needed). The column is used for:
1. Deduplication check in staple auto-add logic
2. Pre-fill on shopping-list loop-close (bought → inventory)

**Rationale**: The spec explicitly requires shopping list entries to carry `canonical_product_id`
for the deduplication check (`shopping_item where canonical_product_id = X and checked = false`).
Nullable avoids breaking existing manually-added shopping items that have no canonical product.

**Migration safety**: Nullable column addition on an existing table is safe under concurrent
writes (no lock beyond a brief metadata lock in Postgres).

---

### 5. Expiry Defaults by Category

**Decision**: Category-to-days mapping is stored as a constant dictionary in the API layer
(not in the database). Household overrides are stored in `canonical_product.expiry_days_default`.

| Category key | Default days |
|---|---|
| `raw_meat_fish` | 2 |
| `fresh_dairy` | 5 |
| `fresh_pasta` | 3 |
| `cheese` | 14 |
| `eggs` | 28 |
| `fresh_produce` | 5 |
| `frozen` | 90 |
| `canned_jarred` | 365 |
| `dry_goods` | 180 |

Resolution order: `canonical_product.expiry_days_default` → category constant → no pre-fill.

**Rationale**: A DB table for this would add a migration and query for data that changes
rarely and doesn't vary per household (only the override does). A constant is simpler and
satisfies KISS.

---

### 6. Status Tap-to-Cycle UX

**Decision**: `PATCH /inventory/{item_id}` with `{ "status": "<new_status>" }`. Frontend
computes the next state in the cycle (`ok → low → out → ok`) and sends the target state.
The staple auto-add side-effect is triggered server-side when `status` is set to `low`.

**Rationale**: Server owns the side-effect logic (auto-add to shopping list). Client sends
the target state explicitly rather than a "cycle" command — makes the intent clear in the
API contract and allows the client to optimistically update the UI before the response.

---

### 7. Inventory Screen "Out" Items Visibility

**Decision**: `status = out` items are fetched in the same list query and rendered at the
bottom of each location group with `opacity-40` and a strikethrough name. They are never
filtered out by default. A future "hide out items" toggle is out of scope.

**Rationale**: Spec explicitly requires out items to remain visible ("ghost/muted styling").
Hiding them would require a separate query or client-side filter; keeping them in the same
list query is simpler and matches the spec intent.

---

### 8. Loop-Close Endpoint

**Decision**: `POST /groups/{group_id}/inventory/from-shopping` accepts a list of shopping
item IDs. For each, it creates an `inventory_item` pre-filled from the linked `canonical_product`
record, then marks the shopping item as checked (if not already).

**Rationale**: The loop-close is a batch operation (multiple bought items at once). A single
endpoint is cleaner than N individual inventory POSTs. The shopping items are not deleted —
they stay checked on the shopping list per existing behaviour.
