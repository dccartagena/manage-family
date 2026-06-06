# Food Inventory — Feature Requirements

> This feature builds on top of an existing system with the following tables already in
> place: `person`, `group`, `membership`, `invite`, `task`, `event`, `reminder`,`shopping_item`. 

---

## Scope

The inventory loop: **add item → track state → surface what needs attention → link to shopping list**.

In scope:
- Barcode scan + Dutch product lookup (with manual fallback)
- Three-state status model: `ok` / `low` / `out`
- Canonical product layer: track "is there milk?" not "is there brand X milk?"
- Expiry tracking (THT — best before only; manual input; inferred over time)
- Staple vs occasional replenishment mode driving shopping list automation
- Loop-close: shopping list "bought" → back into inventory
- Wastage capture on removal

---

## Definitions

### Canonical product

A household-defined abstract product concept — "milk", "coffee", "pasta" — that represents
what the household cares about having, independent of brand or packaging. Canonical products
are scoped to a `group_id` so each household defines their own vocabulary.

A canonical product carries the staple flag and usual storage location. The question
*"is there milk in the fridge?"* is answered by querying inventory items linked to the
"milk" canonical product.

Multiple specific products (barcodes) can map to the same canonical product. Scanning
any brand of milk links back to the household's single "milk" canonical concept.

### Specific product (product cache)

A record of a particular branded or packaged product identified by its EAN barcode.
Returned by an external lookup source and cached locally. Carries brand name, product name
as labelled, category, and the raw source response. Links to a canonical product once
the association has been made.

### Inventory item

One physical instance of a product present in the household (or recently removed). Links
to both the specific product (barcode) and the canonical product. Carries location,
status, expiry date, and removal metadata.

### Staple

A canonical product the household considers always necessary. When a staple's status
drops to `low`, it is automatically added to the shopping list if not already present.

### Occasional

A canonical product the household buys situationally. Never auto-added to the shopping
list. Added manually when needed.

---

## Data model

### `canonical_product`

Household-level. Persists indefinitely across inventory cycles.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `group_id` | uuid FK | Scoped to the household |
| `name` | text | e.g. "Milk", "Coffee", "Pasta" |
| `category` | text | e.g. dairy, dry goods, frozen |
| `is_staple` | boolean | Drives shopping list auto-add |
| `usual_location` | text | `fridge / freezer / pantry / other` |
| `expiry_days_default` | int | Nullable; overrides category default for this household |

### `product_cache`

Keyed on barcode. Written once on first successful lookup; never re-fetched unless
invalidated. An item scanned once never pays the external API cost again.

| Column | Type | Notes |
|---|---|---|
| `barcode` | text PK | EAN-13 |
| `canonical_product_id` | uuid FK | Nullable until the user makes the association |
| `source` | text | `off`, `ah`, `jumbo`, `manual` |
| `name` | text | Product name as returned by source |
| `brand` | text | |
| `category` | text | Used to suggest a canonical product |
| `raw_data` | jsonb | Full response from source |
| `cached_at` | timestamptz | |

### `inventory_item`

One row per physical instance.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `group_id` | uuid FK | |
| `canonical_product_id` | uuid FK | What this item abstractly is (e.g. "milk") |
| `barcode` | text FK | Which specific product; nullable for manual items |
| `name` | text | Display name; copied from cache or entered manually |
| `location` | text | `fridge / freezer / pantry / other` |
| `status` | text | `ok / low / out` |
| `expiry_date` | date | Nullable; manually entered (DD-MM-YYYY) |
| `added_by` | uuid FK | Person |
| `added_at` | timestamptz | |
| `removed_at` | timestamptz | Nullable; soft-delete |
| `removed_reason` | text | Nullable: `used / thrown / transferred` |

**RLS rule:** a user sees `inventory_item` rows where `group_id` is any group they are
a member of. The same rule applies to `canonical_product` and `product_cache`.

---

## Behaviour rules

### Status model

Three states: `ok`, `low`, `out`.

- Status is updated by tapping the item; cycles `ok → low → out` with a single tap.
- **"Out" items remain visible** with ghost/muted styling at the bottom of their location
  group. Items do not silently disappear.

### Staple auto-add to shopping list

Triggered when any `inventory_item` linked to a staple `canonical_product` has its status
changed to `low`.

```
on status_change to 'low':
  if inventory_item.canonical_product.is_staple:
    existing = shopping_item where group_id = inventory_item.group_id
                                and canonical_product_id = inventory_item.canonical_product_id
                                and checked = false
    if not existing:
      create shopping_item(group_id, name, canonical_product_id)
      show confirmation: "Added [canonical name] to your shopping list"
```

The trigger is at the canonical product level, not the barcode level. "Milk is running low"
regardless of which brand was scanned.

### Expiry surface

- Items within 3 days of `expiry_date` appear in a "use soon" section pinned at the top
  of the inventory screen.
- Display is calm amber styling. No red. No badge counts on the app icon.
- As the household's own data grows, expiry defaults should be inferred from previous
  inputs for the same canonical product (e.g. if the household consistently sets milk
  expiry to 4 days, pre-fill 4 days on the next scan).

### Expiry defaults by category (THT / best before only)

Pre-filled when a product is added. User overrides freely. If
`canonical_product.expiry_days_default` is set for this household, use that value instead.

| Category | Default days |
|---|---|
| Raw meat / fish | 2 |
| Fresh dairy (milk, yogurt) | 5 |
| Fresh pasta / dough | 3 |
| Cheese | 14 |
| Eggs | 28 |
| Fresh produce | 5 |
| Frozen | 90 |
| Canned / jarred | 365 |
| Dry goods (pasta, rice) | 180 |

Date input and display uses **DD-MM-YYYY** throughout — the standard on Dutch packaging.

---

## Entry flows

### Barcode scan (fast path)

1. User opens camera (`@zxing/browser`, EAN-13).
2. Barcode detected → `GET /inventory/product/{barcode}`.
3. If `product_cache` already has this barcode with a `canonical_product_id` for this
   group: form pre-fills fully (name, location, expiry default) — no prompts.
4. If the barcode is known but not yet associated with a canonical product: suggest one
   based on category/name (e.g. "This looks like Milk — is that right?"). User confirms
   or selects a different canonical product from the household's list, or creates a new one.
5. If the barcode is unknown (lookup returns nothing): manual form opens with barcode
   silently stored. User enters name, selects or creates a canonical product, and sets
   is_staple and usual_location once.
6. On save: `inventory_item` is created. If a new canonical product was created or
   associated, `product_cache` is updated with the `canonical_product_id`.

### Manual entry

Same form as scan confirmation, empty. Barcode silently stored if the scan returned no
result. The canonical product selection is the same flow: pick from the household's
existing list or create a new one.

### Shopping list loop-close

When items are marked "bought" on the shopping list: show a batch prompt —
*"Add to inventory?"* — pre-selected, one-tap dismiss. Pre-fill location and canonical
product from the existing canonical_product record.

---

## Inventory screen layout

- **"Use soon" section** pinned at top: items where `expiry_date` is within 3 days.
- **Main list** grouped by location (fridge, freezer, pantry, other).
- **Ghost items** (`status = out`) shown at the bottom of each location group, muted.
- Status updated by tapping the item.

---

## Removal and wastage

On item removal, one prompt: *"Used it up or throwing it away?"* Default: used up.
Writes `removed_at` and `removed_reason` (`used / thrown / transferred`). No reporting
UI in this iteration; data captured for future surfacing.

---

## External product lookup

### Overview

The household primarily shops at **Aldi and Lidl** (no known unofficial APIs; served by
Open Food Facts and manual entry), and secondarily at **Albert Heijn** and **Jumbo**
(unofficial APIs available). The lookup order reflects this: Open Food Facts first, then
AH, then Jumbo.

Expose one backend route: `GET /inventory/product/{barcode}`. Checks sources in order,
writes hits to `product_cache`, returns a unified schema, or returns 404 (frontend opens
manual form).

All AH and Jumbo API calls are made from the **FastAPI backend only**, abstracted behind a
`ProductLookupService`. Open Food Facts may be called from the frontend directly (it is
CORS-open and requires no authentication).

### Sources and references

**Open Food Facts**
- Endpoint: `https://world.openfoodfacts.org/api/v2/product/{barcode}.json`
- Documentation: https://openfoodfacts.github.io/openfoodfacts-server/reference/api/
- Dutch dashboard (coverage): https://wiki.openfoodfacts.org/Dashboard/Netherlands
- Free, open, CORS-permissive. ~27,000 Dutch products at 99.1% data quality. Primary
  source for Aldi and Lidl products (international own-brands share EAN barcodes across
  European markets).

**Albert Heijn unofficial API**
- Reference implementations:
  - https://github.com/PaulVerhoeven1/grocy-dutch-supermarket (Python; barcode lookup for
    AH and Jumbo; designed for personal grocery tools — closest to this use case)
  - https://github.com/bartmachielsen/SupermarktConnector (Python; AH + Jumbo mobile API)
  - https://github.com/LouayCoding/albert-heijn-api (Node.js; product info, ingredients,
    allergens)
- Covers AH huismerk and AH-sold products. Unofficial and subject to change; abstract
  behind `ProductLookupService` so updates are isolated to one place.

**Jumbo unofficial API**
- Reference implementations: same repositories as above (grocy-dutch-supermarket and
  SupermarktConnector both support Jumbo).
- Covers Jumbo huismerk and Jumbo-sold products. Same caveats as AH.

### Lookup chain

```
1. product_cache (local)  → return immediately if hit
2. Open Food Facts        → write to cache, return if hit
3. AH unofficial API      → write to cache, return if hit
4. Jumbo unofficial API   → write to cache, return if hit
5. 404                    → frontend opens manual form with barcode stored
```
