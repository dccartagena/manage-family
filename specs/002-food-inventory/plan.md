# Implementation Plan: Food Inventory

**Branch**: `002-food-inventory` | **Date**: 2026-06-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-food-inventory/spec.md`

## Summary

Add a food inventory feature to the existing household PWA: EAN-13 barcode scan via device
camera, Dutch product lookup chain (product cache → Open Food Facts → AH → Jumbo), a canonical
product abstraction layer, three-state status model, expiry tracking with calm surface, staple
auto-add to shopping list, removal wastage capture, and shopping-list loop-close. Backend
extends the existing FastAPI service with three new tables and an inventory router. Frontend
adds a new `/inventory` section to the Next.js PWA with a barcode scanner component.

## Technical Context

**Language/Version**: Python 3.12+ (API), TypeScript 5+ (PWA) — same as feature 001

**Primary Dependencies**:
- API (new): `httpx` (already present) for external product API calls
- Frontend (new): `@zxing/browser` for EAN-13 barcode scanning via device camera

**Storage**: Supabase Postgres — three new tables (`canonical_product`, `product_cache`,
`inventory_item`) + `canonical_product_id` column added to existing `shopping_items` table

**Testing**: pytest + httpx (API integration tests); vitest + Testing Library (component tests)
— same toolchain as feature 001

**Target Platform**: Vercel Hobby + PWA — same as feature 001; camera access requires HTTPS
(already satisfied by Vercel deployment and localhost dev server)

**Project Type**: web-service (FastAPI) + PWA (Next.js) — same monorepo structure as 001

**Performance Goals**:
- Cached barcode lookup returns in under 200ms (DB-only; no external call)
- External product lookup completes in under 3 seconds across the full chain
- Inventory screen loads active items in under 2 seconds

**Constraints**:
- AH and Jumbo API calls from backend only (`ProductLookupService`) — unofficial APIs must
  be isolated to one place so changes are contained
- Open Food Facts may be called from frontend directly (CORS-permissive; no auth required)
- Camera access requires HTTPS or localhost; no camera fallback for non-HTTPS contexts
- `shopping_items` table already exists — migration must add `canonical_product_id` column
  as nullable FK to avoid breaking existing rows
- Free-tier constraint: no additional Vercel functions; inventory router added to existing API
- Bundle constraint: `@zxing/browser` must be tree-shaken (dynamic import on scanner page only)

**Scale/Scope**: Same household scale as 001 (~10–100 users, ~5–20 households)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Think Before Coding | ✅ PASS | All ambiguities resolved in research.md; no silent choices |
| II. TDD | ✅ PASS | Tasks enforce test-first per slice |
| III. Simplicity First | ✅ PASS | No new abstraction layers beyond `ProductLookupService` (justified: AH/Jumbo API isolation); no speculative features |
| IV. Surgical Changes | ✅ PASS | Only adds new files + one nullable column migration; no existing file edits beyond `models.py`, `main.py`, `shopping.py` |
| V. Goal-Driven Execution | ✅ PASS | FR and SC defined; each task slice has a verification step |
| VI. No Hard-Coding | ✅ PASS | External API base URLs in env vars; expiry defaults in constants module |
| VII. No Global Variables | ✅ PASS | Serverless; `ProductLookupService` is instantiated per-request |
| VIII. Explicit Over Implicit | ✅ PASS | Status cycle logic explicit in service layer; no framework magic |
| IX. Consistent Formatting | ✅ PASS | Python: ruff + black; TypeScript: ESLint + Prettier; matches existing files |
| X. Fail Fast | ✅ PASS | Product lookup raises after exhausting chain; no silent 404 swallowing |
| XI. Minimal Dependencies | ✅ PASS | `@zxing/browser` justified (only EAN-13 scanner lib with pure-browser WASM support, no native bridge); `httpx` already present |
| XII. Comment the Why | ✅ PASS | Non-obvious: lookup chain order, canonical_product_id nullable on shopping_items, first-source-wins cache |

**Project Constraints (from constitution)**:

| Constraint | Status | Notes |
|------------|--------|-------|
| Serverless & stateless | ✅ PASS | `ProductLookupService` stateless; no in-process cache; product_cache is DB-backed |
| Free-tier hard constraint | ✅ PASS | No new Vercel functions; no external paid APIs |
| Bundle lean | ✅ PASS | `@zxing/browser` dynamically imported on scanner page only |
| Notifications via iCal | N/A | No new notification surface in this feature |
| Accessibility build constraint | ✅ PASS | Scanner fallback to manual entry; tap-to-cycle has aria-label; amber styling only |
| Privacy by structure | ✅ PASS | All three new tables scoped by `group_id`; RLS mirrors existing pattern |
| Headless API-first | ✅ PASS | Frontend calls FastAPI; no direct Supabase DB queries from frontend |

**No violations → Complexity Tracking section omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/002-food-inventory/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # REST endpoint contracts
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
api/
├── models.py                          # + CanonicalProduct, ProductCache, InventoryItem; ShoppingItem gets canonical_product_id
├── routers/
│   ├── inventory.py                   # NEW: inventory CRUD + product lookup endpoint
│   └── shopping.py                    # PATCH: loop-close endpoint added
├── services/
│   └── product_lookup.py              # NEW: ProductLookupService (OFF → AH → Jumbo chain)
├── migrations/versions/
│   └── 0002_food_inventory.py         # NEW: three new tables + shopping_items FK

web/src/
├── app/
│   └── inventory/
│       ├── page.tsx                   # NEW: inventory list (use-soon + location groups)
│       ├── scan/
│       │   └── page.tsx               # NEW: barcode scanner + product lookup + add form
│       └── __tests__/
│           └── inventory.test.tsx     # NEW: component tests
├── components/
│   └── BarcodeScanner.tsx             # NEW: @zxing/browser wrapper, EAN-13 only
└── lib/
    └── inventory.ts                   # NEW: API client functions for inventory endpoints
```
