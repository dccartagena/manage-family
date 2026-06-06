# Feature Specification: Food Inventory

**Feature Branch**: `002-food-inventory`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "Food inventory management with barcode scan, Dutch product lookup, expiry tracking, staple replenishment, and shopping list loop-close"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scan and Add Item (Priority: P1)

A household member scans a product barcode to add it to the inventory. If the product is already known, the form pre-fills with no prompts. If it is new, the member associates it with a canonical product (e.g., "Milk") and saves.

**Why this priority**: Core input mechanism. All downstream value — expiry alerts, staple tracking, shopping automation — depends on items being in inventory. Without this, nothing else works.

**Independent Test**: Can be tested end-to-end by scanning a barcode, confirming the product details, and verifying the item appears in the inventory list under the correct location group. Delivers standalone value: household can track what they have.

**Acceptance Scenarios**:

1. **Given** a known barcode already associated with a canonical product, **When** the member scans it, **Then** the add-item form pre-fills with name, location, and suggested expiry date — no further prompts required before saving.
2. **Given** a barcode known to the product cache but not yet linked to a canonical product, **When** the member scans it, **Then** the system suggests a canonical product based on category/name; member can confirm, pick a different one, or create a new canonical product.
3. **Given** an unknown barcode (no lookup result from any source), **When** the member scans it, **Then** a manual entry form opens with the barcode silently stored; member fills in name and selects or creates a canonical product.
4. **Given** any successfully added item, **When** the save action completes, **Then** the item appears in the inventory list under the correct location group immediately.

---

### User Story 2 - Track Status and Surface Expiring Items (Priority: P2)

A household member opens the inventory screen and sees what needs attention: items expiring within 3 days are pinned at the top, and any item's status can be updated with a single tap cycling through `ok → low → out`.

**Why this priority**: The primary daily-use interaction. Households need to see what is running low or about to expire without opening each item individually.

**Independent Test**: Can be tested by viewing the inventory screen with known items at various statuses and expiry dates, verifying the "use soon" section appears at top, and tapping an item to cycle its status.

**Acceptance Scenarios**:

1. **Given** inventory items with `expiry_date` within 3 days, **When** the inventory screen loads, **Then** those items appear in a "use soon" section pinned at the top, styled in calm amber.
2. **Given** any inventory item, **When** a member taps it once, **Then** its status cycles: `ok → low → out`.
3. **Given** an item with `status = out`, **When** viewed in the inventory list, **Then** it appears at the bottom of its location group with muted/ghost styling — it does not disappear.
4. **Given** items across multiple locations, **When** the main inventory list is displayed, **Then** items are grouped by location (fridge, freezer, pantry, other).

---

### User Story 3 - Staple Auto-Add to Shopping List (Priority: P3)

When a staple item's status is set to `low`, the system automatically adds it to the household's shopping list if it is not already there, and shows a brief confirmation.

**Why this priority**: Closes the replenishment loop without extra steps. Reduces the cognitive load of remembering to add staples to the shopping list.

**Independent Test**: Can be tested by setting a staple item to `low` and verifying a new shopping list entry appears for the corresponding canonical product.

**Acceptance Scenarios**:

1. **Given** an inventory item linked to a staple canonical product with status `ok`, **When** the member taps it to change status to `low`, **Then** a shopping list entry is created for that canonical product and a brief confirmation message is shown ("Added [name] to your shopping list").
2. **Given** a staple item already on the shopping list (unchecked), **When** another item for the same canonical product is set to `low`, **Then** no duplicate shopping list entry is created.
3. **Given** a non-staple (occasional) item, **When** its status is set to `low`, **Then** no shopping list entry is created automatically.

---

### User Story 4 - Remove Item with Wastage Capture (Priority: P4)

When removing an item from inventory, the member is asked whether the item was used up, thrown away, or transferred. The answer is recorded without any reporting UI.

**Why this priority**: Captures data needed for future wastage analysis with minimal friction. Low priority because the data has no immediate visible payoff in this iteration.

**Independent Test**: Can be tested by removing an item and verifying the removal reason is persisted with a `removed_at` timestamp.

**Acceptance Scenarios**:

1. **Given** an active inventory item, **When** the member initiates removal, **Then** a prompt appears asking "Used it up or throwing it away?" with "used up" pre-selected and a "transferred" option available.
2. **Given** the removal prompt, **When** the member confirms, **Then** the item's `removed_at` timestamp and `removed_reason` are saved; the item no longer appears in the active inventory list.

---

### User Story 5 - Shopping List Loop-Close (Priority: P5)

After marking shopping list items as "bought", the member is prompted to add them to inventory in a batch flow when they explicitly end the shopping session. Location and canonical product are pre-filled from the canonical product record.

**Why this priority**: Closes the full inventory loop. Without this, bought items must be manually re-added, breaking the automation value.

**Independent Test**: Can be tested by marking a shopping list item as bought and verifying the inventory add prompt appears with pre-filled details.

**Acceptance Scenarios**:

1. **Given** one or more shopping list items marked as "bought", **When** the member confirms the batch prompt ("Add to inventory?"), **Then** new inventory items are created pre-filled with location and canonical product from the canonical product record.
2. **Given** the batch prompt, **When** the member dismisses it with one tap, **Then** no inventory items are created and the shopping items remain marked as bought.

---

### Edge Cases

- What happens when a barcode scan returns results from multiple lookup sources (e.g., Open Food Facts and AH return different names for same EAN)? → First-source-wins; cached result is used on subsequent scans.
- How does the system handle a product with no category to infer expiry default? → No expiry date is pre-filled; member sets it manually.
- What if two household members simultaneously set the same staple to `low`? → Shopping list deduplication check prevents duplicate entries regardless of race.
- What happens when a canonical product is deleted while inventory items reference it? → Deletion is blocked if active inventory items exist.
- What if expiry date is not set on an item? → Item never appears in the "use soon" section; no expiry warning is shown.
- What if a member adds an item manually (no barcode)? → Full manual form; barcode field silently stores `null`; canonical product selection is the same flow.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Household members MUST be able to add inventory items by scanning an EAN-13 barcode using the device camera.
- **FR-002**: Household members MUST be able to add inventory items manually without a barcode.
- **FR-003**: System MUST perform a product lookup from the configured source chain (product cache → Open Food Facts → AH → Jumbo) and cache the result on first successful lookup.
- **FR-004**: System MUST allow household members to associate a scanned product with an existing or newly created canonical product.
- **FR-005**: System MUST pre-fill the add-item form (name, location, expiry date) when a barcode is already associated with a canonical product in the household.
- **FR-006**: Inventory items MUST carry a location (`fridge / freezer / pantry / other`), status (`ok / low / out`), quantity (positive integer), unit (canonical enum: `piece / can / bag / bottle / box / jar / packet / roll / grams / kilograms / liters / milliliters`), and optional expiry date (DD-MM-YYYY). Unit is selected based on the product; free-text is not permitted.
- **FR-007**: Household members MUST be able to update an item's status with a single tap, cycling `ok → low → out`.
- **FR-008**: System MUST display items with `expiry_date` within 3 days in a "use soon" section pinned at the top of the inventory screen, styled in calm amber.
- **FR-009**: Inventory screen MUST group items by location, with `status = out` items shown at the bottom of each group in muted styling (not hidden).
- **FR-010**: When an inventory item linked to a staple canonical product is set to `low`, system MUST automatically create a shopping list entry for that canonical product if one does not already exist (unchecked).
- **FR-011**: System MUST display a brief confirmation message when a staple item is auto-added to the shopping list.
- **FR-012**: Non-staple (occasional) canonical products MUST NOT be auto-added to the shopping list on any status change.
- **FR-013**: On item removal, system MUST prompt the member to record removal reason (`used / thrown / transferred`) with "used" as default, and persist `removed_at` and `removed_reason`.
- **FR-014**: When the member explicitly ends the shopping session, system MUST present a single batch prompt to add all bought items to inventory, pre-filling location and canonical product from the canonical product record. The prompt does NOT appear per-item check.
- **FR-015**: System MUST pre-fill expiry date using: (1) the canonical product's `expiry_days_default` if set for the household, else (2) category-based defaults, else (3) no pre-fill.
- **FR-016**: All inventory data MUST be scoped to the household group; members MUST only see items belonging to groups they are members of.
- **FR-017**: Product cache entries MUST be written on first successful external lookup and reused on all subsequent scans of the same barcode — no repeat external calls for cached barcodes.
- **FR-018**: When an external lookup source returns an error or times out, the system MUST retry that source exactly once before skipping to the next source in the chain (cache → OFF → AH → Jumbo).

### Key Entities

- **Canonical Product**: Household-defined abstract product concept (e.g., "Milk"). Carries `is_staple` flag, `usual_location`, and optional `expiry_days_default`. Scoped to a group. Multiple barcodes can map to one canonical product.
- **Product Cache**: Barcode-keyed record of a specific branded product returned by an external lookup source. Cached on first fetch. Links to a canonical product once associated.
- **Inventory Item**: One logical stock entry per canonical product per location in the household. Links to both product cache (barcode) and canonical product. Carries location, status, quantity (positive integer), unit (canonical enum: piece/can/bag/bottle/box/jar/packet/roll/grams/kilograms/liters/milliliters), optional expiry date, and removal metadata. Soft-deleted on removal. One row tracks e.g. "3 cans of tomatoes in the pantry".

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Members can add an item from barcode scan to saved inventory entry in under 30 seconds for a previously scanned product.
- **SC-002**: Members can add a new (never-seen) product from scan to saved inventory entry in under 90 seconds including canonical product association.
- **SC-003**: Items expiring within 3 days appear in the "use soon" section without any manual action from household members.
- **SC-004**: 100% of staple items set to `low` result in a shopping list entry (no misses), with zero duplicate entries created.
- **SC-005**: Inventory screen loads and displays all active items grouped by location within 2 seconds on a standard household connection.
- **SC-006**: Previously scanned barcodes never trigger external product lookups — cache hit rate for repeat scans is 100%.
- **SC-007**: Removal reason is captured for every item removed through the UI with no extra steps beyond the confirmation prompt.

---

## Assumptions

- Household members are on mobile devices with a working camera for barcode scanning.
- EAN-13 is the only barcode format in scope; QR codes and other formats are out of scope.
- External product lookup APIs (Open Food Facts, AH, Jumbo) are called from the backend only; Open Food Facts may also be called directly from the frontend given its CORS-open nature.
- AH and Jumbo product lookups use unofficial/undocumented JSON endpoints (no auth required, reverse-engineered). No official partner API or web scraping is involved.
- On external lookup error or timeout, the service retries the failing source once before skipping to the next source in the chain. If all sources fail after their single retry, the service raises a 404.
- Product cache entries are permanent. `cached_at` is audit metadata only — no TTL, no scheduled invalidation. Manual re-fetch is not in scope for v1.
- Expiry inference from household history (pre-filling based on past inputs for same canonical product) is a nice-to-have and out of scope for v1; only category defaults and `expiry_days_default` are used.
- Reporting on wastage data (thrown vs used) is out of scope for this iteration; data is captured for future surfacing.
- The shopping list table (`shopping_item`) already exists with `group_id`, `name`, `canonical_product_id`, and `checked` columns.
- RLS policies on `canonical_product`, `product_cache`, and `inventory_item` enforce group-scoped visibility.
- Date format throughout is DD-MM-YYYY, matching Dutch packaging conventions.
- "Transferred" as a removal reason is captured but has no downstream integration in this iteration.

---

## Clarifications

### Session 2026-06-04

- Q: What method is used to access AH and Jumbo product data? → A: Unofficial/undocumented JSON endpoints (no auth, reverse-engineered); no official API or scraping.
- Q: On external lookup error/timeout, retry or skip to next source? → A: Retry the failing source once, then skip to next source.
- Q: Does ProductCache expire (TTL)? → A: Permanent — `cached_at` is audit-only; no TTL, no background invalidation.
- Q: When does loop-close "Add to inventory?" prompt appear? → A: Once, when member explicitly ends the shopping session — not per-item check.
- Q: One row per physical unit, or quantity field? → A: One row per canonical product per location, with `quantity` (positive integer) and `unit` (canonical enum: piece/can/bag/bottle/box/jar/packet/roll/grams/kilograms/liters/milliliters) fields. Free-text unit not permitted.
