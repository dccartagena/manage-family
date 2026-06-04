# Data Model: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04

## New Entities

### CanonicalProduct

Household-defined abstract product concept. Persists indefinitely. Scoped to one group.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → groups(id), NOT NULL | Household scope |
| name | TEXT | NOT NULL | e.g. "Milk", "Coffee", "Pasta" |
| category | TEXT | NOT NULL | e.g. `fresh_dairy`, `dry_goods`, `frozen` |
| is_staple | BOOLEAN | NOT NULL, DEFAULT FALSE | Drives shopping list auto-add |
| usual_location | TEXT | NOT NULL, CHECK (usual_location IN ('fridge','freezer','pantry','other')) | |
| expiry_days_default | INTEGER | NULLABLE, CHECK (expiry_days_default > 0) | Overrides category constant for this household |

**Invariants**:
- `name` should be unique per `group_id` (enforced at application layer; no DB unique constraint
  because households may have naming edge cases and the collision risk is low)
- Cannot be deleted while active `inventory_item` rows reference it

**RLS**: visible to all members of the owning group.

---

### ProductCache

Keyed on barcode. One row per EAN-13 barcode, globally shared (no `group_id`).
Written once on first successful external lookup; never re-fetched unless invalidated.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| barcode | TEXT | PK | EAN-13 (13-digit string) |
| canonical_product_id | UUID | FK → canonical_products(id), NULLABLE | Set when first household makes the association; hint for subsequent households |
| source | TEXT | NOT NULL, CHECK (source IN ('off','ah','jumbo','manual')) | Lookup source |
| name | TEXT | NOT NULL | Product name as returned by source |
| brand | TEXT | NULLABLE | |
| category | TEXT | NULLABLE | Used to suggest canonical product |
| raw_data | JSONB | NOT NULL, DEFAULT '{}' | Full response from source |
| cached_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**Invariants**:
- `barcode` is exactly 13 digits (enforced at application layer before insert)
- Once written, a row is never updated by the lookup chain — only `canonical_product_id`
  may be updated when a household makes the association

**RLS**: readable by any authenticated user (global cache). Only the API backend may write.

---

### InventoryItem

One row per physical instance of a product in the household. Soft-deleted on removal.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → groups(id), NOT NULL | |
| canonical_product_id | UUID | FK → canonical_products(id), NOT NULL | Abstract identity |
| barcode | TEXT | FK → product_cache(barcode), NULLABLE | NULL for manual (no-barcode) items |
| name | TEXT | NOT NULL | Display name; copied from cache or entered manually |
| location | TEXT | NOT NULL, CHECK (location IN ('fridge','freezer','pantry','other')) | |
| status | TEXT | NOT NULL, DEFAULT 'ok', CHECK (status IN ('ok','low','out')) | |
| expiry_date | DATE | NULLABLE | DD-MM-YYYY display; stored as DATE |
| added_by | UUID | FK → persons(id), NOT NULL | |
| added_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| removed_at | TIMESTAMPTZ | NULLABLE | Non-null = soft-deleted |
| removed_reason | TEXT | NULLABLE, CHECK (removed_reason IN ('used','thrown','transferred')) | Required when removed_at is set |

**State transitions**:

```
status:  ok ──(tap)──► low ──(tap)──► out ──(tap)──► ok
                 │
                 └─ if canonical_product.is_staple:
                      check shopping_items for active (unchecked) entry
                      if none: create shopping_item(group_id, name, canonical_product_id)
```

**Active items**: `removed_at IS NULL`
**Ghost items**: `removed_at IS NULL AND status = 'out'` — shown muted, not removed from query

**RLS**: visible to all members of the owning group (same `group_id`-based policy as tasks/shopping).

---

## Modified Entities

### ShoppingItem (existing)

One nullable column added. All existing rows default to NULL.

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| canonical_product_id | UUID | NEW — FK → canonical_products(id), NULLABLE | Links to canonical product for deduplication and loop-close pre-fill |

**Migration**: `ALTER TABLE shopping_items ADD COLUMN canonical_product_id UUID REFERENCES canonical_products(id);`
No backfill; existing rows remain NULL.

---

## Indexes

```sql
-- Inventory list queries (primary access pattern: active items by group + location)
CREATE INDEX idx_inventory_items_group_active
    ON inventory_items(group_id, location)
    WHERE removed_at IS NULL;

-- Expiry surface (use-soon query)
CREATE INDEX idx_inventory_items_expiry
    ON inventory_items(group_id, expiry_date)
    WHERE removed_at IS NULL AND expiry_date IS NOT NULL;

-- Staple auto-add deduplication check
CREATE INDEX idx_shopping_items_canonical
    ON shopping_items(group_id, canonical_product_id)
    WHERE checked = FALSE AND canonical_product_id IS NOT NULL;

-- Canonical product lookup by group
CREATE INDEX idx_canonical_products_group
    ON canonical_products(group_id);
```

---

## RLS Policies

All three new tables follow the existing household-scoped pattern from feature 001.

**canonical_products** — members of the owning group:
```sql
CREATE POLICY canonical_products_group_member ON canonical_products
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM memberships
            WHERE memberships.group_id = canonical_products.group_id
              AND memberships.person_id = auth.uid()
        )
    );
```

**inventory_items** — members of the owning group:
```sql
CREATE POLICY inventory_items_group_member ON inventory_items
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM memberships
            WHERE memberships.group_id = inventory_items.group_id
              AND memberships.person_id = auth.uid()
        )
    );
```

**product_cache** — any authenticated user may read; API backend writes:
```sql
CREATE POLICY product_cache_read ON product_cache
    FOR SELECT USING (auth.uid() IS NOT NULL);
```

---

## Migration File

**File**: `api/migrations/versions/0002_food_inventory.py`

Operations in order:
1. Create `canonical_products` table
2. Create `product_cache` table
3. Create `inventory_items` table
4. Add `canonical_product_id` nullable FK column to `shopping_items`
5. Create all indexes listed above
