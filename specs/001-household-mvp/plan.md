# Implementation Plan: Household Manager MVP

**Branch**: `001-household-mvp` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-household-mvp/spec.md`

## Summary

Build a private household coordination PWA: passwordless auth, multi-household membership with
nested group trees, chores/tasks with RRULE recurrence, real-time shared shopping list,
household events with iCal feed rollup to parent groups, timed reminders, and an urgency-ranked
overview dashboard. Backend: Python 3.12 + FastAPI on Vercel Hobby (serverless). Frontend:
Next.js 14 + Tailwind + shadcn/ui as an installable PWA. All persistence in Supabase Postgres
(free tier). Notifications delivered via per-user secret `.ics` feed; no push infrastructure.

## Technical Context

**Language/Version**: Python 3.12+ (API), TypeScript 5+ (PWA)

**Primary Dependencies**:
- API: `fastapi`, `sqlmodel`, `alembic`, `supabase`, `python-jose[cryptography]`, `python-dateutil`, `recurring-ical-events`, `icalendar`, `psycopg2-binary`
- Frontend: Next.js 14 (App Router), Tailwind CSS, shadcn/ui (Radix-based), `@supabase/supabase-js`, `@supabase/ssr`, Workbox

**Storage**: Supabase Postgres (free tier, via Supabase connection pooler); IndexedDB (offline PWA cache + change queue)

**Testing**: pytest + httpx (API integration tests); vitest + Testing Library (component tests)

**Target Platform**: Vercel Hobby (serverless, Python 3.12 runtime + Next.js); iOS/Android/desktop via PWA install

**Project Type**: web-service (FastAPI) + PWA (Next.js); monorepo, two Vercel deployments from one project

**Performance Goals**:
- Shopping item check reflected to all household members within 3 seconds (SC-002)
- Reminder appears in iCal feed within 10 minutes of scheduled time (SC-004)
- iCal feed endpoint response under 2 seconds

**Constraints**:
- Vercel bundle ≤ 500 MB; no ML or data-science libs
- Serverless: no on-disk state, no long-lived DB connections — pooler only
- Supabase free tier: 500 MB DB, 2 GB bandwidth, 50 MB file storage (not used)
- External scheduler (cron-job.org) mandatory; Vercel free cron = once/day only
- Non-commercial private use; app must stay within free-tier quotas
- Headless API-first: FastAPI is the sole data gateway; frontend accesses all data through REST API only; direct Supabase DB queries from frontend prohibited (FR-023); Supabase Auth session management and Realtime subscriptions are approved infrastructure-level exceptions

**Scale/Scope**: ~10–100 users, ~5–20 households, ≤5 levels of nesting, low hundreds of tasks/events

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Think Before Coding | ✅ PASS | Spec and research resolve all ambiguities before code |
| II. TDD | ✅ PASS | Tasks enforce test-first per slice; failing test → green → refactor |
| III. Simplicity First | ✅ PASS | Recursive CTE (not closure table); RRULE (not custom format); no custom push infra |
| IV. Surgical Changes | N/A | Plan stage |
| V. Goal-Driven Execution | ✅ PASS | FR and SC defined; each task slice has a verification step |
| VI. No Hard-Coding | ✅ PASS | All secrets and URLs in env vars; IANA timezone via `zoneinfo` |
| VII. No Global Variables | ✅ PASS | Serverless functions are stateless; Supabase client created per-request |
| VIII. Explicit Over Implicit | ✅ PASS | RLS policies documented in data-model.md; no hidden query magic |
| IX. Consistent Formatting | ✅ PASS | Python: ruff + black; TypeScript: ESLint + Prettier; enforced in CI |
| X. Fail Fast | ✅ PASS | Pydantic validation at API boundary; external calls retry then raise |
| XI. Minimal Dependencies | ✅ PASS | Every dep justified in research.md; no speculative additions |
| XII. Comment the Why | ✅ PASS | Non-obvious decisions documented (recursive CTE, last-write-wins, iCal URL auth) |

**Project Constraints (from constitution)**:

| Constraint | Status | Notes |
|------------|--------|-------|
| Serverless & stateless | ✅ PASS | All DB access via Supabase pooler; no on-disk or in-memory state |
| Free-tier hard constraint | ✅ PASS | External scheduler mandatory; no Vercel sub-daily cron dependency |
| Bundle lean | ✅ PASS | Dependency list reviewed; heavy libs excluded |
| Notifications via iCal | ✅ PASS | Primary path; Web Push deferred out of MVP |
| Accessibility build constraint | ✅ PASS | shadcn/Radix selected; FR-018 applied to every screen from day one |
| Privacy by structure | ✅ PASS | RLS policies enforce local/rollup rules before any code ships |
| Headless API-first | ✅ PASS | FR-023: FastAPI is sole data gateway; frontend REST-only; Supabase Auth + Realtime are approved infrastructure exceptions |

**No violations → Complexity Tracking section omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/001-household-mvp/
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
├── main.py                  # FastAPI app instance (Vercel entrypoint)
├── db.py                    # Supabase/Postgres session via pooler
├── auth.py                  # JWT verification (Supabase JWKS)
├── models.py                # SQLModel table models
├── routers/
│   ├── groups.py            # Group CRUD, invite generation/acceptance
│   ├── tasks.py             # Task CRUD, assignment, done toggle
│   ├── shopping.py          # Shopping list CRUD
│   ├── events.py            # Event CRUD
│   ├── ical.py              # Per-user .ics feed generation
│   ├── reminders.py         # Reminder CRUD
│   └── jobs.py              # GET /jobs/tick (external scheduler endpoint)
└── migrations/              # Alembic migration files

web/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── (auth)/          # Login, magic-link callback
│   │   ├── dashboard/       # Overview dashboard
│   │   ├── groups/          # Group management, invite flow
│   │   ├── tasks/           # Task list and CRUD
│   │   ├── shopping/        # Shopping list (real-time)
│   │   ├── events/          # Event list and CRUD
│   │   └── reminders/       # Reminder CRUD
│   ├── components/          # Shared shadcn/ui + custom components
│   ├── lib/
│   │   ├── supabase.ts      # Supabase client factory (SSR-aware)
│   │   ├── sync.ts          # Offline queue + IndexedDB helpers
│   │   └── realtime.ts      # Supabase Realtime channel management
│   └── middleware.ts        # Session refresh (Supabase SSR)
├── public/
│   └── manifest.webmanifest
├── workbox.config.js
└── next.config.ts

vercel.json                  # Routes: /api/* → api/, /* → web/
pyproject.toml               # Python dependencies + tool config
package.json                 # Root workspace (optional) or in web/
```

**Structure Decision**: Web application option (Option 2 variant). `api/` is a standalone FastAPI app deployed as a single Vercel serverless function. `web/` is the Next.js PWA. Both deployed from the same Vercel project via `vercel.json` routing.
