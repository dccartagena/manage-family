# Quickstart: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04

## Prerequisites

- Existing household MVP running (see `specs/001-household-mvp/quickstart.md`)
- Python 3.12+ with `.venv` activated
- Node.js 20+ with `web/node_modules` installed
- Supabase local dev running (`supabase start`)

## Backend Setup

### 1. Install new frontend dependency

```bash
cd web
npm install @zxing/browser
```

### 2. Run the migration

```bash
cd /path/to/repo
source .venv/bin/activate
alembic -c api/alembic.ini upgrade head
```

This creates `canonical_products`, `product_cache`, `inventory_items` tables and adds
`canonical_product_id` to `shopping_items`.

### 3. Add environment variables

Copy any new vars from `api/.env.example` to `api/.env`. The inventory feature uses only
existing vars (`DATABASE_URL`, `SUPABASE_*`). No new secrets required.

### 4. Register the new router

`api/main.py` must include the inventory router:

```python
from api.routers import inventory
app.include_router(inventory.router, prefix="/api/v1")
```

## Frontend Setup

The barcode scanner uses the device camera. In development:

- **Chrome/Firefox on localhost**: Camera access works without HTTPS.
- **Mobile device on local network**: Requires either HTTPS or a dev tunnel
  (`npx next dev --hostname 0.0.0.0` + ngrok or similar).

## Running Tests

```bash
# API integration tests (from repo root)
source .venv/bin/activate
pytest api/tests/test_inventory.py -v

# Frontend component tests
cd web
npm test -- --run src/app/inventory
```

## Key Files

| File | Purpose |
|------|---------|
| `api/routers/inventory.py` | Inventory CRUD + product lookup endpoint |
| `api/services/product_lookup.py` | `ProductLookupService` — OFF → AH → Jumbo chain |
| `api/migrations/versions/0002_food_inventory.py` | DB migration |
| `web/src/components/BarcodeScanner.tsx` | `@zxing/browser` wrapper |
| `web/src/app/inventory/page.tsx` | Inventory list page |
| `web/src/app/inventory/scan/page.tsx` | Scan + add item flow |
| `web/src/lib/inventory.ts` | Frontend API client functions |

## External API Notes

**Open Food Facts**: No auth required. Rate limit: be respectful; the cache means each
barcode is only looked up once.

**AH and Jumbo**: Unofficial APIs. Calls are backend-only via `ProductLookupService`.
If either API changes its contract, only `api/services/product_lookup.py` needs updating.
