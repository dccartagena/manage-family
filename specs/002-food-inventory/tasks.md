# Tasks: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04
**Input**: `specs/002-food-inventory/` — plan.md, spec.md, research.md, data-model.md, contracts/api.md

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Tests**: Included — constitution principle II (TDD) is non-negotiable; tests precede every implementation task.

**Format**: `[ID] [P?] [Story?] Description — file path`

- **[P]**: Parallelizable (different files, no in-flight dependencies)
- **[USN]**: Belongs to User Story N
- File paths are project-relative from repo root

---

## Phase 1: Setup

**Purpose**: Install new dependency, create constant module, scaffold service skeleton. No user story work until complete.

- [X] T001 Install `@zxing/browser` — run `npm install @zxing/browser` in `web/` and verify it appears in `web/package.json` dependencies
- [X] T002 [P] Create category expiry defaults constant in `api/constants/expiry.py` — `EXPIRY_DAYS_BY_CATEGORY: dict[str, int]` mapping (raw_meat_fish→2, fresh_dairy→5, fresh_pasta→3, cheese→14, eggs→28, fresh_produce→5, frozen→90, canned_jarred→365, dry_goods→180)
- [X] T003 [P] Scaffold `api/services/product_lookup.py` — `ProductLookupService` class with `lookup_barcode(barcode: str) -> ProductCacheRead` stub, `_fetch_from_off`, `_fetch_from_ah`, `_fetch_from_jumbo` private stubs that raise `NotImplementedError`

**Checkpoint**: `python -c "from api.constants.expiry import EXPIRY_DAYS_BY_CATEGORY"` imports cleanly; `npm list @zxing/browser` shows installed version.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB models, migration, router skeleton, and shared test/client stubs that all user stories depend on.

**⚠️ CRITICAL**: No user story implementation begins until this phase passes its checkpoint.

- [X] T004 Add `CanonicalProduct` SQLModel table class to `api/models.py` — fields: id (UUID PK gen_random_uuid), group_id (FK groups, NOT NULL), name (TEXT NOT NULL), category (TEXT NOT NULL), is_staple (BOOL NOT NULL DEFAULT FALSE), usual_location (TEXT NOT NULL CHECK fridge/freezer/pantry/other), expiry_days_default (INT NULLABLE CHECK >0)
- [X] T005 Add `ProductCache` SQLModel table class to `api/models.py` — fields: barcode (TEXT PK), canonical_product_id (UUID FK canonical_products NULLABLE), source (TEXT NOT NULL CHECK off/ah/jumbo/manual), name (TEXT NOT NULL), brand (TEXT NULLABLE), category (TEXT NULLABLE), raw_data (JSON NOT NULL DEFAULT {}), cached_at (TIMESTAMPTZ NOT NULL DEFAULT now())
- [X] T006 Add `InventoryItem` SQLModel table class to `api/models.py` — fields: id (UUID PK gen_random_uuid), group_id (FK groups NOT NULL), canonical_product_id (FK canonical_products NOT NULL), barcode (TEXT FK product_cache NULLABLE), name (TEXT NOT NULL), location (TEXT NOT NULL CHECK fridge/freezer/pantry/other), status (TEXT NOT NULL DEFAULT ok CHECK ok/low/out), expiry_date (DATE NULLABLE), added_by (FK persons NOT NULL), added_at (TIMESTAMPTZ NOT NULL DEFAULT now()), removed_at (TIMESTAMPTZ NULLABLE), removed_reason (TEXT NULLABLE CHECK used/thrown/transferred)
- [X] T007 Add `canonical_product_id` nullable UUID FK column to `ShoppingItem` in `api/models.py` — `Field(default=None, foreign_key="canonical_products.id")`
- [X] T008 Write `api/migrations/versions/0002_food_inventory.py` — operations in order: (1) create `canonical_products` table, (2) create `product_cache` table, (3) create `inventory_items` table, (4) `ALTER TABLE shopping_items ADD COLUMN canonical_product_id UUID REFERENCES canonical_products(id)`, (5) create all 4 indexes from data-model.md, (6) create RLS policies: `canonical_products_group_member` (FOR ALL via memberships), `inventory_items_group_member` (FOR ALL via memberships), `product_cache_read` (FOR SELECT WHERE auth.uid() IS NOT NULL)
- [X] T009 [P] Create `api/routers/inventory.py` — `APIRouter(tags=["inventory"])`, `_get_membership(group_id, person_id, session)` helper matching pattern in `api/routers/shopping.py`; no endpoints yet
- [X] T010 Register `inventory.router` in `api/main.py` with `prefix="/api/v1"`
- [X] T011 [P] Create `web/src/lib/inventory.ts` — type definitions (`CanonicalProduct`, `InventoryItem`, `ProductLookupResult`, `LoopCloseResult`) and typed async function stubs for all 9 client operations: `lookupBarcode`, `listCanonicalProducts`, `createCanonicalProduct`, `updateCanonicalProduct`, `listInventory`, `createInventoryItem`, `updateInventoryItem`, `deleteInventoryItem`, `fromShoppingItems` — stubs `throw new Error("not implemented")` so component tests can mock them cleanly

**Checkpoint**: `alembic -c api/alembic.ini upgrade head` applies cleanly; `python -c "from api.routers import inventory"` imports without error; `npm run build` in `web/` compiles without type errors on `inventory.ts` stubs.

---

## Phase 3: User Story 1 — Scan and Add Item (Priority: P1) 🎯 MVP

**Goal**: Member scans EAN-13 barcode → product looked up (cache → OFF → AH → Jumbo) → form pre-fills → item saved to inventory under correct location group.

**Independent Test**: Navigate to `/inventory/scan`, scan a barcode, associate with a canonical product, save — verify item appears in DB with correct `group_id`, `canonical_product_id`, and `location`. Test with a cache-hit barcode (fast path) and a cold barcode (triggers OFF call).

### Tests (write first — must be RED before implementation)

- [X] T012 [P] [US1] Write failing integration tests for `GET /inventory/product/{barcode}` — (a) barcode in product_cache returns 200 with `canonical_product_id` populated, (b) unknown barcode triggers OFF mock and writes to cache, returns 200, (c) barcode unknown to all sources returns 404 — `api/tests/test_inventory.py`
- [X] T013 [P] [US1] Write failing integration tests for `POST /groups/{group_id}/canonical-products` — (a) member creates product, 201 returned, (b) non-member gets 403 — `api/tests/test_inventory.py`
- [X] T014 [P] [US1] Write failing integration test for `GET /groups/{group_id}/canonical-products` — member gets list, non-member 403 — `api/tests/test_inventory.py`
- [X] T015 [P] [US1] Write failing integration tests for `PATCH /canonical-products/{id}` — member updates name and is_staple, non-member 403, unknown id 404 — `api/tests/test_inventory.py`
- [X] T016 [P] [US1] Write failing integration tests for `POST /groups/{group_id}/inventory` — (a) barcode-originated item creates row with correct fields, (b) manual item (no barcode) creates row with barcode=NULL, (c) new canonical association updates `product_cache.canonical_product_id` — `api/tests/test_inventory.py`
- [X] T017 [P] [US1] Write failing component tests for `BarcodeScanner.tsx` — (a) renders video element, (b) calls `onDetected` callback with decoded barcode string, (c) renders error state when camera permission denied — `web/src/components/__tests__/BarcodeScanner.test.tsx`

### Implementation

- [X] T018 [US1] Implement `ProductLookupService.lookup_barcode()` in `api/services/product_lookup.py` — check `product_cache` first; on miss call OFF via httpx; on OFF miss call AH then Jumbo; write cache on first hit; raise `HTTPException(404)` if all sources miss (depends T012)
- [X] T019 [US1] Implement `GET /inventory/product/{barcode}` endpoint in `api/routers/inventory.py` — calls `ProductLookupService`, reads `canonical_product_id` from `product_cache`, returns `ProductLookupResult` Pydantic schema; no auth guard per contract (depends T012, T018)
- [X] T020 [US1] Implement `GET /groups/{group_id}/canonical-products` and `POST /groups/{group_id}/canonical-products` endpoints in `api/routers/inventory.py` — membership guard via `_get_membership`; pure Pydantic schemas for request/response (depends T013, T014)
- [X] T021 [US1] Implement `PATCH /canonical-products/{id}` endpoint in `api/routers/inventory.py` — load canonical product, verify caller is group member, apply partial update, return updated schema (depends T015)
- [X] T022 [US1] Implement `POST /groups/{group_id}/inventory` endpoint in `api/routers/inventory.py` — membership guard; resolve expiry_days_default → category constant → None for expiry pre-fill; set `status="ok"`; if barcode provided and product_cache.canonical_product_id is NULL, update it; return `InventoryItemRead` schema (depends T016)
- [X] T023 [P] [US1] Implement `BarcodeScanner.tsx` in `web/src/components/BarcodeScanner.tsx` — dynamic import of `@zxing/browser`; initialize `BrowserMultiFormatReader` on mount; decode from video stream; call `onDetected(barcode: string)` on EAN-13 hit; show error message on camera permission denial; stop reader on unmount (depends T017)
- [X] T024 [P] [US1] Implement `lookupBarcode`, `listCanonicalProducts`, `createCanonicalProduct`, `updateCanonicalProduct`, `createInventoryItem` in `web/src/lib/inventory.ts` — replace stubs with real `fetch` calls to `NEXT_PUBLIC_API_URL`; attach Bearer token via `fetchAccessToken()` pattern from `web/src/app/shopping/page.tsx` (depends T011)
- [X] T025 [US1] Create `web/src/app/inventory/scan/page.tsx` — `"use client"`; render `BarcodeScanner`; on detect: call `lookupBarcode` → show pre-filled form (name, location, expiry, canonical product picker); on unknown barcode (404): open manual entry form; on save: call `createInventoryItem`; on success: redirect to `/inventory`; add nav link to inventory in existing navigation (depends T023, T024)

**Checkpoint**: `pytest api/tests/test_inventory.py -k "product or canonical" -v` all green; navigate to `/inventory/scan` in browser, scan a barcode, confirm details, verify item saved.

---

## Phase 4: User Story 2 — Track Status and Surface Expiring Items (Priority: P2)

**Goal**: Inventory list page shows items grouped by location; items expiring within 3 days pinned at top in amber; tapping item cycles status `ok → low → out`; out items shown with ghost styling.

**Independent Test**: Seed 5 items with varying statuses and expiry dates. Load `/inventory`. Verify: (a) use-soon section shows items with expiry ≤3 days from today, (b) items are grouped by location, (c) tapping an item changes its status and backend confirms, (d) out items render muted at group bottom.

### Tests (write first — must be RED before implementation)

- [ ] T026 [P] [US2] Write failing integration tests for `GET /groups/{group_id}/inventory` — returns only active items (removed_at IS NULL), includes status=out items, excludes removed items; non-member 403 — `api/tests/test_inventory.py`
- [ ] T027 [P] [US2] Write failing integration tests for `PATCH /inventory/{item_id}` status update — ok→low, low→out, out→ok cycle; expiry date update; non-member 403; unknown item 404; invalid status 422 — `api/tests/test_inventory.py` (no staple side-effect test yet — added in US3)
- [ ] T028 [P] [US2] Write failing component tests for inventory list page — (a) use-soon section renders for items with expiry ≤3 days and has amber class, (b) items render in location groups, (c) item with status=out has ghost/muted class — `web/src/app/inventory/__tests__/inventory.test.tsx`

### Implementation

- [ ] T029 [US2] Implement `GET /groups/{group_id}/inventory` endpoint in `api/routers/inventory.py` — query `WHERE group_id = :gid AND removed_at IS NULL`; serialize `expiry_date` as `DD-MM-YYYY` string; return list of `InventoryItemRead` (depends T026)
- [ ] T030 [US2] Implement `PATCH /inventory/{item_id}` status/expiry endpoint in `api/routers/inventory.py` — accept `status` and `expiry_date` (both optional); validate status enum; persist; return updated item with `shopping_item_created: false` placeholder in response schema (staple side-effect added in T034) (depends T027)
- [ ] T031 [P] [US2] Implement `listInventory` and `updateInventoryItem` in `web/src/lib/inventory.ts` — replace stubs with real fetch calls; `updateInventoryItem` returns `InventoryItemUpdateResponse` that includes optional `shopping_item_created` + `shopping_item_name` fields (depends T024)
- [ ] T032 [US2] Create `web/src/app/inventory/page.tsx` — `"use client"`; fetch inventory on mount; compute use-soon (expiry ≤3 days from today); render use-soon section pinned at top with amber `bg-amber-50 border-amber-200` styling; render items grouped by location; render out-items with `opacity-40 line-through` at group bottom; tap item calls `updateInventoryItem` with next status in cycle; optimistic update with revert on error (depends T028, T031)

**Checkpoint**: `pytest api/tests/test_inventory.py -k "inventory" -v` all green; load `/inventory` in browser with seeded data; verify grouping, use-soon section, and tap-to-cycle.

---

## Phase 5: User Story 3 — Staple Auto-Add to Shopping List (Priority: P3)

**Goal**: Setting a staple item to `low` automatically creates a shopping list entry for its canonical product (if not already present) and shows a brief confirmation.

**Independent Test**: Mark a staple item as `low` via `PATCH /inventory/{item_id}`. Verify: (a) `shopping_items` row created with correct `canonical_product_id`, (b) second `low` tap on same canonical product does NOT create duplicate, (c) non-staple item `low` creates nothing.

### Tests (write first — must be RED before implementation)

- [ ] T033 [P] [US3] Write failing integration tests for staple side-effect in `PATCH /inventory/{item_id}` — (a) staple item status→low: response has `shopping_item_created: true` and new row in shopping_items, (b) staple already on list (unchecked): `shopping_item_created: false`, no duplicate, (c) non-staple item: `shopping_item_created: false` — `api/tests/test_inventory.py`

### Implementation

- [ ] T034 [US3] Add staple auto-add side-effect to `PATCH /inventory/{item_id}` in `api/routers/inventory.py` — when `status == "low"`: load `canonical_product`; if `is_staple`: query for unchecked `shopping_item` with same `canonical_product_id` and `group_id`; if absent: create `ShoppingItem`; set `shopping_item_created: True` and `shopping_item_name` in response (depends T033)
- [ ] T035 [US3] Update `updateInventoryItem` in `web/src/lib/inventory.ts` to read `shopping_item_created` and `shopping_item_name` from response and include in return type (depends T031)
- [ ] T036 [US3] Add shopping list auto-add toast in `web/src/app/inventory/page.tsx` — after `updateInventoryItem` resolves: if `shopping_item_created === true` show brief `"Added [name] to your shopping list"` toast for 3 seconds (depends T032, T035)

**Checkpoint**: `pytest api/tests/test_inventory.py -k "staple" -v` all green; tap a staple item to `low` in browser; verify toast appears and shopping list gains new item; tap second staple item for same canonical product to `low`; verify no duplicate.

---

## Phase 6: User Story 4 — Remove Item with Wastage Capture (Priority: P4)

**Goal**: Removing an item prompts for removal reason (used/thrown/transferred, default: used); `removed_at` and `removed_reason` are persisted; item disappears from active list.

**Independent Test**: Remove an inventory item via `DELETE /inventory/{item_id}` with `removed_reason: "thrown"`. Verify `removed_at` is set, `removed_reason == "thrown"`, and item is absent from `GET /groups/{group_id}/inventory` response.

### Tests (write first — must be RED before implementation)

- [ ] T037 [P] [US4] Write failing integration tests for `DELETE /inventory/{item_id}` — (a) valid removal with reason sets removed_at and removed_reason, item absent from GET list, (b) missing removed_reason → 422, (c) invalid reason value → 422, (d) non-member → 403, (e) unknown id → 404 — `api/tests/test_inventory.py`
- [ ] T038 [P] [US4] Write failing component tests for removal dialog — (a) renders reason picker with three options, (b) "used" is pre-selected, (c) confirm calls `deleteInventoryItem` with selected reason — `web/src/app/inventory/__tests__/inventory.test.tsx`

### Implementation

- [ ] T039 [US4] Implement `DELETE /inventory/{item_id}` in `api/routers/inventory.py` — accept `RemoveInventoryItemRequest(removed_reason: Literal["used","thrown","transferred"])`; set `removed_at = datetime.utcnow()` and `removed_reason`; return 204 (depends T037)
- [ ] T040 [P] [US4] Implement `deleteInventoryItem` in `web/src/lib/inventory.ts` — replace stub with `DELETE` request including `removed_reason` body (depends T011)
- [ ] T041 [US4] Add remove button and reason dialog to `web/src/app/inventory/page.tsx` — long-press or swipe-to-reveal remove button per item; dialog with "Used it up", "Throwing it away", "Transferring it" options (default: used); confirm calls `deleteInventoryItem`; optimistic removal from list with revert on error (depends T038, T040)

**Checkpoint**: `pytest api/tests/test_inventory.py -k "remove or delete" -v` all green; remove an item in browser; verify it disappears from list; verify `removed_reason` in DB.

---

## Phase 7: User Story 5 — Shopping List Loop-Close (Priority: P5)

**Goal**: After marking shopping items as bought, member is prompted to batch-add them to inventory. Location and canonical product pre-filled from canonical product record.

**Independent Test**: Mark 2 shopping items (one with `canonical_product_id`, one without) as bought. POST to loop-close endpoint. Verify: inventory items created for the linked item, skipped list contains the unlinked item ID.

### Tests (write first — must be RED before implementation)

- [ ] T042 [P] [US5] Write failing integration tests for `POST /groups/{group_id}/inventory/from-shopping` — (a) items with canonical_product_id get inventory rows created, (b) items without canonical_product_id appear in skipped list, (c) empty list → 422, (d) non-member → 403 — `api/tests/test_inventory.py`
- [ ] T043 [P] [US5] Write failing component tests for loop-close prompt in shopping page — (a) prompt appears when items are checked, (b) confirm calls `fromShoppingItems`, (c) dismiss hides prompt without calling API — `web/src/app/shopping/__tests__/shopping.test.tsx` (create file if absent)

### Implementation

- [ ] T044 [US5] Add `POST /groups/{group_id}/inventory/from-shopping` endpoint to `api/routers/shopping.py` — accept `LoopCloseRequest(shopping_item_ids: list[UUID])`; for each ID: load shopping_item, if has canonical_product_id create inventory_item pre-filled from canonical_product (location=usual_location, status=ok), else add to skipped; return `LoopCloseResponse(created: list[InventoryItemRead], skipped: list[UUID])` (depends T042)
- [ ] T045 [P] [US5] Implement `fromShoppingItems` in `web/src/lib/inventory.ts` — replace stub with POST to `/groups/{group_id}/inventory/from-shopping` (depends T011)
- [ ] T046 [US5] Add loop-close prompt to `web/src/app/shopping/page.tsx` — when items are checked/bought and at least one has `canonical_product_id`: show bottom sheet or banner "Add [N] item(s) to inventory?"; confirm calls `fromShoppingItems` and shows "Added [N] item(s)" toast; dismiss hides prompt; items without canonical_product_id excluded from count with no UI noise (depends T043, T045)

**Checkpoint**: `pytest api/tests/test_inventory.py -k "loop" -v` all green; mark a shopping item with canonical product as bought; verify loop-close prompt appears; confirm; verify inventory item created.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, bundle hygiene, end-to-end validation.

- [ ] T047 [P] Add accessibility attributes to `web/src/app/inventory/page.tsx` and `web/src/app/inventory/scan/page.tsx` — `aria-label` on status cycle buttons ("Cycle status for [name]"), `role="status"` on use-soon section, `aria-live="polite"` on toast, `aria-label` on barcode scanner video element
- [ ] T048 [P] Verify `@zxing/browser` tree-shaking — run `npm run build` in `web/`, check `.next/` bundle output; confirm scanner code absent from pages other than `/inventory/scan`
- [ ] T049 Run quickstart.md end-to-end validation — activate venv, `alembic -c api/alembic.ini upgrade head`, `pytest api/tests/test_inventory.py -v`, `cd web && npm test -- --run src/app/inventory`; all pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3–7 (User Stories)**: All depend on Phase 2 completion; stories can proceed in priority order (P1→P2→P3→P4→P5) or in parallel if staffed
- **Phase 8 (Polish)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 — no other story dependencies
- **US2 (P2)**: Depends only on Phase 2 — independently testable (does not require US1 scan page)
- **US3 (P3)**: Depends on US2 endpoint (`PATCH /inventory/{item_id}` must exist to extend)
- **US4 (P4)**: Depends only on Phase 2 — independently testable
- **US5 (P5)**: Depends only on Phase 2 — independently testable

### Within Each User Story

```
Tests (RED) → Models/stubs → Service/helpers → Endpoints → Frontend client → Frontend page → verify GREEN
```

---

## Parallel Opportunities

### Phase 2 — run together once Phase 1 is done

```
T004 (CanonicalProduct model)     ← sequential: each model builds on previous
T005 (ProductCache model)           (FK deps require order: T004 before T005, T005 before T006)
T006 (InventoryItem model)
T007 (ShoppingItem patch)
T008 (migration)                  ← after T004-T007
T009 (router skeleton)            ← parallel with T004-T007
T010 (register router)            ← after T009
T011 (inventory.ts stubs)         ← parallel with T004-T010
```

### Phase 3 (US1) — parallel test writing

```
Parallel: T012, T013, T014, T015, T016, T017 (all test files, independent)
Then parallel: T018 (service), T023 (BarcodeScanner), T024 (client stubs)
Sequential: T019, T020, T021, T022 (endpoints, after T018)
Sequential: T025 (scan page, after T023 + T024)
```

### Phase 4 (US2) — parallel test writing

```
Parallel: T026, T027, T028
Sequential: T029, T030 (endpoints)
Parallel: T031 (client), T032 (page, after T031)
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (migration + models + router)
3. Complete Phase 3: US1 tests → US1 implementation
4. **STOP and VALIDATE**: `pytest api/tests/test_inventory.py -k "product or canonical"` green; scan page works end-to-end
5. Deploy / demo

### Incremental Delivery

| Step | Adds | Validates independently |
|------|------|------------------------|
| Phase 1+2 | Foundation | Migration clean, imports OK |
| + Phase 3 | Scan + Add | Barcode scan → item in DB |
| + Phase 4 | Status + Expiry | Inventory list + tap-to-cycle |
| + Phase 5 | Staple auto-add | Shopping list gains entry on low |
| + Phase 6 | Wastage capture | Removal reason persisted |
| + Phase 7 | Loop-close | Bought → inventory batch |
| + Phase 8 | Polish | Accessibility + bundle |

---

## Notes

- `[P]` = different file from other `[P]` tasks in same phase — no shared write conflict
- `[USN]` maps tasks to user stories for traceability and independent scope
- RLS policies are in T008 (migration); do not add them separately
- `shopping.py` is modified only in T044 (loop-close endpoint); all other inventory endpoints live in `inventory.py`
- `expiry_date` stored as `DATE` in Postgres, serialized as `DD-MM-YYYY` string in all API responses
- `ProductLookupService` is instantiated per-request (no global state) — constitution principle VII
- Pydantic `BaseModel` for all request/response schemas — never `SQLModel`; this is a hard constraint per project memory
