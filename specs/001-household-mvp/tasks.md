# Tasks: Household Manager MVP

**Input**: Design documents from `specs/001-household-mvp/`

**Branch**: `001-household-mvp` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/api.md ✅

**Tests**: Included — one failing-test task precedes each story phase's implementation (T008a, T018a, T026a, T034a, T043a, T050a, T059a, T065a). Constitution §II TDD: write failing tests before production code per slice.

**Headless**: FastAPI is the sole data gateway (FR-023). Frontend accesses all data via REST API only. Direct Supabase DB table queries from frontend are prohibited. Supabase Auth session management and Supabase Realtime subscriptions are approved infrastructure-level exceptions.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no pending deps)
- **[Story]**: Maps to user story (US1–US7) — setup/foundational phases have no story label
- Exact file paths included in every task description

## Path Conventions

- **API**: `api/` at repo root (FastAPI serverless function)
- **Routers**: `api/routers/`
- **Migrations**: `api/migrations/versions/`
- **Tests**: `api/tests/`
- **Web**: `web/` at repo root (Next.js 14 PWA)
- **Pages**: `web/src/app/`
- **Components**: `web/src/components/`
- **Lib**: `web/src/lib/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [X] T001 Create directory skeleton: `api/`, `api/routers/`, `api/migrations/versions/`, `api/tests/`, `web/src/app/(auth)/`, `web/src/app/dashboard/`, `web/src/app/groups/`, `web/src/app/tasks/`, `web/src/app/shopping/`, `web/src/app/events/`, `web/src/app/reminders/`, `web/src/components/`, `web/src/lib/`, `web/public/` per plan.md project structure
- [X] T002 Configure `pyproject.toml` — Python 3.12 project metadata; deps: fastapi, sqlmodel, alembic, supabase, python-jose[cryptography], python-dateutil, recurring-ical-events, icalendar, psycopg2-binary; dev deps: pytest, httpx, ruff, black
- [X] T003 [P] Configure `web/package.json` — Next.js 14, @supabase/supabase-js, @supabase/ssr, tailwindcss, all shadcn/ui deps, workbox-cli, vitest, @testing-library/react
- [X] T004 [P] Configure `web/next.config.ts`, `web/tailwind.config.ts`, `web/tsconfig.json` — TypeScript strict mode, Tailwind content paths covering `web/src/**/*.{ts,tsx}`
- [X] T005 [P] Create `vercel.json` — route `/api/*` to FastAPI serverless function (`api/main.py`), route `/*` to Next.js; ensures clear frontend/backend boundary at the routing layer
- [X] T006 [P] Create `api/.env.example` (DATABASE_URL, DATABASE_POOL_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, SCHEDULER_SECRET, APP_TIMEZONE) and `web/.env.local.example` (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL)
- [X] T007 [P] Configure `web/.eslintrc.json` and `web/.prettierrc` — TypeScript + React rules, Tailwind class sorting plugin
- [X] T008 [P] Initialize FastAPI app in `api/main.py` — `FastAPI(title="Household Manager API", docs_url="/docs", openapi_url="/openapi.json")` so OpenAPI schema is auto-available at `/api/v1/docs` and `/api/v1/openapi.json` for any headless client; `GET /health` returning `{"status":"ok"}`; CORS middleware for Vercel domain; router import stubs (one per routers/ file)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work begins until this phase is complete

- [X] T008a Write failing tests for foundational layer in `api/tests/test_auth.py` — assert `get_current_person` raises HTTP 401 on missing, expired, and invalid Bearer token; assert valid Supabase JWT returns correct `person_id` UUID; in `api/tests/test_db.py` — assert `get_session` dependency yields a live session via `DATABASE_POOL_URL`; all tests MUST fail before T009–T018 are implemented
- [X] T009 Initialize Alembic: create `alembic.ini` and `api/migrations/env.py` — set `target_metadata = SQLModel.metadata`, connect via `DATABASE_POOL_URL` env var, configure `include_schemas = True`
- [X] T010 Implement `api/db.py` — SQLModel engine via psycopg2 pooler URL (`DATABASE_POOL_URL`), `get_session` FastAPI dependency yielding a session, `pool_pre_ping=True` for serverless cold starts
- [X] T011 Implement `api/auth.py` — `get_current_person` FastAPI dependency: extract `Authorization: Bearer` token, validate JWT signature against Supabase JWKS URL, return `person_id` UUID (sub claim); raise HTTP 401 on invalid, expired, or missing token
- [X] T012 Define all 8 SQLModel table models in `api/models.py`: Person, Group, Membership, Invite, Task, ShoppingItem, Event, Reminder — all fields, types, nullable flags, constraints per `data-model.md`
- [X] T013 Write `api/migrations/versions/0001_baseline.py` — create all 8 tables with all constraints; create all 7 indexes per `data-model.md §Key indexes`; create `updated_at` auto-trigger on `tasks` and `shopping_items`; create `person_reachable_groups(p_id UUID)` recursive CTE function with `SECURITY DEFINER`; apply all RLS policies per `data-model.md §RLS Policy Summary`
- [X] T014 [P] Implement `web/src/lib/supabase.ts` — auth-only Supabase client (FR-023 headless: frontend uses Supabase SDK exclusively for auth session management, NOT for direct table queries); `createBrowserClient()` for auth state in client components; `createServerClient(cookies)` for SSR session refresh in server components and route handlers using `@supabase/ssr`
- [X] T015 Implement `web/src/middleware.ts` — call `supabase.auth.getUser()` on every request, refresh session cookie via `@supabase/ssr`, redirect unauthenticated requests on non-auth paths to `/login`
- [X] T016 [P] Create `web/src/app/layout.tsx` — root layout: shadcn/ui ThemeProvider, mount `<BottomNav />`, apply CSS variable classes derived from `ui_prefs` (text-size, contrast, reduce-motion) stored in session/cookie
- [X] T017 [P] Create `web/src/components/BottomNav.tsx` — fixed bottom navigation bar with 5 labeled icon tabs: Dashboard, Tasks, Shopping, Events, Reminders; each tab has `aria-label` AND visible text label per FR-018; active tab highlighted
- [X] T018 [P] Configure PWA: `web/public/manifest.webmanifest` (name, short_name, icons, display:standalone, start_url:/, background_color, theme_color); `web/workbox.config.js` (NetworkFirst strategy for `/api/v1/*`, CacheFirst for `/_next/static/*`); register service worker in `web/src/app/layout.tsx`

**Checkpoint**: Foundation ready — user story implementation can begin in parallel

---

## Phase 3: User Story 1 — Passwordless Login (Priority: P1) 🎯 MVP

**Goal**: User enters email, receives magic link, clicks it, lands on dashboard as authenticated user. Session persists across visits.

**Independent Test**: Navigate to `/login` → enter email → magic link email arrives within 60s → click link → land on `/dashboard` as authenticated user. Return visit (valid session) goes directly to dashboard. Expired link shows error page with re-request CTA.

### Implementation for User Story 1

- [ ] T018a [US1] Write failing API tests in `api/tests/test_person.py` — `POST /person/sync` creates Person row on first call and is idempotent on repeat; `PATCH /person/prefs` accepts valid `ui_prefs` keys; both return 401 without auth; write failing component test in `web/src/app/(auth)/__tests__/login.test.tsx` — email form renders and transitions to confirmation state on submit; all tests MUST fail before T019–T026 are implemented
- [ ] T019 [US1] Create `web/src/app/(auth)/login/page.tsx` — email input form, call `supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: '/auth/callback' } })`, transition to "Check your email" confirmation state after submit
- [ ] T020 [US1] Create `web/src/app/(auth)/callback/route.ts` — GET route handler: extract `code` from URL params, call `supabase.auth.exchangeCodeForSession(code)`, call `POST /api/v1/person/sync` with Bearer token to upsert Person row, redirect to `/dashboard`
- [ ] T021 [US1] Create `web/src/app/(auth)/error/page.tsx` — expired/invalid magic link error screen: clear message, "Request a new link" CTA navigating to `/login`; no technical jargon
- [ ] T022 [US1] Implement `api/routers/person.py` — `POST /person/sync`: upsert Person row using `person_id` from JWT sub, `email` from JWT claims, `display_name` defaulting to email prefix; idempotent on repeated calls; return full person object
- [ ] T023 [US1] Register person router at `/api/v1/person` in `api/main.py`; add `PATCH /person/prefs` to `api/routers/person.py` — update `ui_prefs` JSONB (text_size, contrast, reduce_motion, notification_batching) per `contracts/api.md §Person Preferences`
- [ ] T024 [US1] Create `web/src/app/(auth)/settings/page.tsx` — display preferences UI: text size selector (normal/large/xlarge), contrast toggle, reduce-motion toggle; call `PATCH /api/v1/person/prefs` on each change; persist selection in session
- [ ] T025 [P] [US1] Add contrast-mode CSS class stub in `web/src/app/globals.css` — `.contrast-high {}` placeholder; Tailwind safelist entry for `.contrast-high`; font-scale custom properties are owned by T072 — do not define here
- [ ] T026 [US1] Wire session persistence: confirm `web/src/middleware.ts` passes active sessions through to `/dashboard` without re-auth; verify behavior on browser refresh and tab close/reopen

**Checkpoint**: US1 complete — authenticated access independently functional

---

## Phase 4: User Story 2 — Create Household & Invite Members (Priority: P1)

**Goal**: User creates household, generates invite link, second user joins. Both see each other as members. Nested sub-groups supported up to depth 4.

**Independent Test**: User A creates group → generates invite URL → copies link. User B opens link (auth via US1), joins group. Both call `GET /api/v1/groups`, see the same group in each response. User A leaves (sole owner, other members exist) → User B auto-promoted to owner.

### Implementation for User Story 2

- [ ] T026a [US2] Write failing API tests in `api/tests/test_groups.py` and `api/tests/test_invites.py` — `POST /groups` creates group and sets caller as owner; `GET /groups` lists caller's memberships only; `POST /groups/{id}/invites` is owner-only (403 for non-owner) and generates unique token; `POST /invites/{token}/accept` grants membership and returns 410 on exhausted or expired token; owner departure with other members promotes member with smallest `joined_at` to owner; sole-member departure deletes group and all associated data; all tests MUST fail before T027–T034 are implemented
- [ ] T027 [P] [US2] Implement `api/routers/groups.py` — `POST /groups`: create Group row, validate parent `depth ≤ 3` if `parent_group_id` provided, insert Membership as owner; `GET /groups`: list all groups for caller via memberships join; return group id, name, depth, role
- [ ] T028 [US2] Implement `DELETE /groups/{group_id}/membership` in `api/routers/groups.py` — owner departure: if other members exist, promote member with smallest `joined_at` to owner then delete departing membership (FR-020); if sole member, delete group + cascade all data (FR-021); else delete membership only; return 403 if caller not a member
- [ ] T029 [P] [US2] Implement `api/routers/invites.py` — `POST /groups/{group_id}/invites` (owner-only): generate 64-char hex token, create Invite row, return token + invite_url; `POST /invites/{token}/accept`: validate token validity (`expires_at` and `max_uses`), create Membership, increment `uses` atomically in a single transaction, return group_id + role; return 410 on exhausted/expired token
- [ ] T030 [US2] Register groups router at `/api/v1/groups` and invites router at `/api/v1` in `api/main.py`
- [ ] T031 [P] [US2] Create `web/src/app/groups/page.tsx` — list all user's groups via `GET /api/v1/groups`; name, role badge, depth indicator; "Create Household" button; tap group to navigate to detail
- [ ] T032 [P] [US2] Create `web/src/app/groups/new/page.tsx` — create household form: name field required, optional parent_group_id dropdown showing only groups where depth ≤ 3; `POST /api/v1/groups` on submit; redirect to group detail on success
- [ ] T033 [US2] Create `web/src/app/groups/[id]/page.tsx` — group detail: member list with role badges via `GET /api/v1/groups`; "Generate Invite Link" button (`POST /api/v1/groups/{id}/invites` → copy URL to clipboard); "Leave Group" button with confirmation warning (FR-021 permanent-deletion warning if sole member)
- [ ] T034 [US2] Create `web/src/app/join/[token]/page.tsx` — invite acceptance: fetch group name from token, show "Join [Group Name]" CTA, call `POST /api/v1/invites/{token}/accept` on confirm, redirect to `/groups` on success; show expired/exhausted error state with link to request new invite

**Checkpoint**: US2 complete — formed household with ≥2 members, ready for collaborative features

---

## Phase 5: User Story 3 — Chores & Recurring Tasks (Priority: P2)

**Goal**: Member creates recurring chore, assigns it, assignee marks done, next occurrence auto-generated. Overdue tasks visually distinguished without red.

**Independent Test**: Create task FREQ=WEEKLY, assign to member B. Member B calls `POST /tasks/{id}/done`. Response has `next_occurrence.due_at` 7 days later. `GET /groups/{id}/tasks` shows original `done=true` excluded from default view and new occurrence with `done=false` included.

### Implementation for User Story 3

- [ ] T034a [US3] Write failing API tests in `api/tests/test_tasks.py` — `POST /groups/{id}/tasks` creates task with optional `rrule` and `assignee_id`; `GET /groups/{id}/tasks` returns only `done=FALSE` by default; `POST /tasks/{id}/done` sets `done=TRUE` and returns `next_occurrence` for RRULE tasks; `DELETE /tasks/{id}/done` restores `done=FALSE`; removing a member clears `assignee_id` on that member's tasks in the group (FR-022); all tests MUST fail before T035–T043 are implemented
- [ ] T035 [P] [US3] Implement `api/routers/tasks.py` — `GET /groups/{group_id}/tasks`: return tasks where `done=FALSE` by default; support `?done=true` and `?assignee_id=<uuid>` query params; `POST /groups/{group_id}/tasks`: create task with optional `rrule`, `due_at`, `assignee_id`; validate caller is group member
- [ ] T036 [US3] Implement `PATCH /tasks/{task_id}` in `api/routers/tasks.py` — partial update of `title`, `assignee_id`, `due_at`, `rrule`; validate caller is member of task's group; return updated task object
- [ ] T037 [US3] Implement `POST /tasks/{task_id}/done` in `api/routers/tasks.py` — set `done=TRUE`; if `rrule IS NOT NULL`, parse rrule + `due_at` via `python-dateutil.rrule` to compute next occurrence datetime, insert new Task row with `done=FALSE` and computed `due_at`; return `{"task": {...done}, "next_occurrence": {...} | null}`
- [ ] T038 [P] [US3] Implement `DELETE /tasks/{task_id}/done` in `api/routers/tasks.py` — set `done=FALSE` (toggle back); validate caller is group member; return updated task
- [ ] T039 [US3] Add assignee-clearing side effect to `DELETE /groups/{group_id}/membership` in `api/routers/groups.py` — `UPDATE tasks SET assignee_id=NULL WHERE group_id=group_id AND assignee_id=departing_person_id` before removing membership (FR-022)
- [ ] T040 [US3] Register tasks router at `/api/v1` in `api/main.py`
- [ ] T041 [P] [US3] Create `web/src/app/tasks/page.tsx` — task list per selected group via `GET /api/v1/groups/{id}/tasks`; filter tabs (All / My Tasks / Today / Overdue); overdue tasks styled with amber/orange border (never red per FR-018); check button per task calls `POST /api/v1/tasks/{id}/done`; group selector dropdown if user has multiple groups
- [ ] T042 [P] [US3] Create `web/src/app/tasks/new/page.tsx` — create task form: title (required), assignee selector (group members from `GET /api/v1/groups/{id}`), due date/time picker, recurrence picker (None / Daily / Weekly / Monthly mapped to RRULE strings); `POST /api/v1/groups/{id}/tasks` on submit
- [ ] T043 [US3] Create `web/src/app/tasks/[id]/page.tsx` — task detail: editable title, assignee, due date (`PATCH /api/v1/tasks/{id}` on change), "Mark Done" / "Undo" toggle, recurrence label, next occurrence preview shown after marking done for recurring tasks

**Checkpoint**: US3 complete — shared chore tracking with automatic recurrence independently functional

---

## Phase 6: User Story 4 — Shared Shopping List (Priority: P2)

**Goal**: Checked item appears on all household members' screens within 3 seconds. Offline mutations persist and sync on reconnect using last-write-wins.

**Independent Test**: Open shopping list on two browser tabs (same group). Check item on tab A. Item appears checked on tab B via Realtime within 3s (SC-002). Disconnect tab A (DevTools offline), uncheck item, reconnect — change syncs; server `updated_at` determines winner if concurrent.

### Implementation for User Story 4

- [ ] T043a [US4] Write failing API tests in `api/tests/test_shopping.py` — add/list/patch/delete shopping items; `PATCH` response confirms `updated_at` is set server-side (last-write-wins arbiter, client must not set it); 403 for non-members; write failing component test in `web/src/app/shopping/__tests__/shopping.test.tsx` — checked item renders visually distinct; offline indicator renders when `navigator.onLine` is false; all tests MUST fail before T044–T050 are implemented
- [ ] T044 [P] [US4] Implement `api/routers/shopping.py` — `GET /groups/{group_id}/shopping`: list items; `POST /groups/{group_id}/shopping`: add item by name; `PATCH /shopping/{item_id}`: update `name` or `checked`; server always sets `updated_at=now()` as last-write-wins arbiter; `DELETE /shopping/{item_id}`: remove item; all ops validate caller is group member
- [ ] T045 [US4] Register shopping router at `/api/v1` in `api/main.py`
- [ ] T046 [US4] Implement `web/src/lib/realtime.ts` — `subscribeToShopping(groupId, onPayload)`: create Supabase `postgres_changes` channel on `shopping_items` table filtered by `group_id=eq.{groupId}`; return cleanup function; call cleanup on component unmount per research.md §6; NOTE: this is the ONLY approved direct Supabase usage outside auth per FR-023 (Realtime subscriptions are an approved infrastructure exception); all CRUD operations MUST go through FastAPI REST endpoints
- [ ] T047 [US4] Implement `web/src/lib/sync.ts` — IndexedDB change queue: `enqueueShoppingMutation(op)` stores pending op when offline; `drainShoppingQueue()` replays queue in order on reconnect by calling `PATCH /api/v1/shopping/{item_id}`; skip queued op if server's `updated_at` for the item is newer (last-write-wins merge per clarification Q1)
- [ ] T048 [P] [US4] Create `web/src/app/shopping/page.tsx` — fetch initial list via `GET /api/v1/groups/{id}/shopping`; subscribe to real-time updates via `realtime.ts` on mount (FR-023 headless: REST load + Realtime subscription, no direct Supabase table queries); optimistic local state update on check; queue failed/offline mutations via `sync.ts`; group selector if multiple groups
- [ ] T049 [US4] Implement `navigator.onLine` detection in `web/src/app/shopping/page.tsx` — show "Offline" indicator badge when disconnected; trigger `drainShoppingQueue()` when `online` event fires
- [ ] T050 [P] [US4] Extend `web/workbox.config.js` precache manifest — add `web/src/app/shopping/page.tsx` and `web/src/app/tasks/page.tsx` to offline cache (FR-017 requires both tasks and shopping offline); Workbox NetworkFirst for `/api/v1/*` and service worker registration already configured in T018 — do not duplicate

**Checkpoint**: US4 complete — real-time collaborative shopping with offline resilience independently functional

---

## Phase 7: User Story 5 — Household Events & Calendar Feed (Priority: P2)

**Goal**: Event in sub-group visible to parent-group members via iCal feed. Feed returns RFC 5545 iCal data. URL rotatable.

**Independent Test**: Create event in group G (child of P). Subscribe user from group P to their feed URL. Poll `GET /ical/{secret}`. Event from G present in response (rollup via `person_reachable_groups` RLS). Call `POST /ical/rotate`. Old URL returns 404; new URL returns feed.

### Implementation for User Story 5

- [ ] T050a [US5] Write failing API tests in `api/tests/test_events.py` and `api/tests/test_ical.py` — `POST /groups/{id}/events` creates event; `GET /ical/{secret}` returns `Content-Type: text/calendar` with VEVENT for that event; parent-group member's secret includes sub-group event via RLS rollup (US2 AC6, FR-012); `POST /ical/rotate` invalidates old secret (subsequent `GET /ical/{old_secret}` returns 404); all tests MUST fail before T051–T059 are implemented
- [ ] T051 [P] [US5] Implement `api/routers/events.py` — `GET /groups/{group_id}/events`: list events (event-table RLS via `person_reachable_groups` handles rollup at DB layer, no app-layer join needed); `POST /groups/{group_id}/events`: create event with `title`, `starts_at` UTC, optional `rrule`; `DELETE /events/{event_id}`: caller must be member of event's `group_id`
- [ ] T052 [US5] Register events router at `/api/v1` in `api/main.py`
- [ ] T053 [US5] Implement `api/routers/ical.py` — `GET /ical/{secret}` (no auth header): look up Person by `ical_secret` (404 if not found); fetch all events visible to person (RLS filters automatically); expand recurring events using `recurring-ical-events` over a 12-month window; build iCal Calendar using `icalendar` library with PRODID, VERSION, CALSCALE; emit one VEVENT per occurrence; return `text/calendar; charset=utf-8` response
- [ ] T054 [US5] Implement `POST /ical/rotate` in `api/routers/ical.py` (auth required) — generate new `uuid.uuid4()`, `UPDATE persons SET ical_secret=new_uuid WHERE id=person_id`, return `{"new_feed_url": "https://.../api/v1/ical/{new_uuid}"}`
- [ ] T055 [US5] Register ical router at `/api/v1` in `api/main.py`
- [ ] T056 [P] [US5] Create `web/src/app/events/page.tsx` — event list per group via `GET /api/v1/groups/{id}/events`; sorted by `starts_at` ascending; recurring badge on events with `rrule`; "Add Event" button; group selector if multiple groups
- [ ] T057 [P] [US5] Create `web/src/app/events/new/page.tsx` — create event form: title (required), `datetime-local` picker (displays in APP_TIMEZONE), recurrence selector (None/Daily/Weekly/Monthly/Yearly → RRULE strings); `POST /api/v1/groups/{id}/events` on submit
- [ ] T058 [US5] Create `web/src/app/events/[id]/page.tsx` — event detail: title, starts_at display in APP_TIMEZONE, recurrence label; "Delete" button calling `DELETE /api/v1/events/{id}` (403-aware — only renders for members of owning group)
- [ ] T059 [US5] Extend `web/src/app/(auth)/settings/page.tsx` — iCal feed section: display current feed URL, copy-to-clipboard button, "Reset Feed URL" button with confirmation (calls `POST /api/v1/ical/rotate`); subscription instructions for Google Calendar and Outlook per `quickstart.md §6`

**Checkpoint**: US5 complete — event creation with cross-group rollup and iCal feed independently functional

---

## Phase 8: User Story 6 — Timed Reminders (Priority: P3)

**Goal**: Personal one-shot reminder fires at scheduled time (wall-clock + IANA timezone) and appears in iCal feed within 10 minutes of scheduled time.

**Independent Test**: Create reminder `fire_at_local=now+2min`, `timezone=APP_TIMEZONE`. Wait for `/jobs/tick` call (or trigger with correct header). `GET /reminders` shows `delivered=TRUE`. Poll iCal feed; VEVENT with VALARM for reminder present.

### Implementation for User Story 6

- [ ] T059a [US6] Write failing API tests in `api/tests/test_reminders.py` and extend `api/tests/test_ical.py` — `POST /reminders` with `fire_at_local`+`timezone` stores converted UTC `fire_at`; `GET /jobs/tick` with correct `X-Scheduler-Secret` sets `delivered=TRUE` on due reminders and returns count; wrong `X-Scheduler-Secret` returns 403; delivered reminders appear as VEVENT entries in the iCal feed; all tests MUST fail before T060–T065 are implemented
- [ ] T060 [P] [US6] Implement `api/routers/reminders.py` — `GET /reminders`: caller's reminders only (RLS enforces `person_id=auth.uid()`); `POST /reminders`: accept `fire_at_local` + `timezone`, convert to UTC via `zoneinfo.ZoneInfo(timezone)`, store as `fire_at` UTC; `DELETE /reminders/{reminder_id}`: caller's own only
- [ ] T061 [US6] Implement `api/routers/jobs.py` — `GET /jobs/tick`: validate `X-Scheduler-Secret` header against `SCHEDULER_SECRET` env var (return 403 immediately on mismatch); `UPDATE reminders SET delivered=TRUE WHERE fire_at <= now() AND delivered=FALSE`; return `{"reminders_delivered": int, "tick_at": "<UTC ISO>"}`
- [ ] T062 [US6] Extend `api/routers/ical.py` `GET /ical/{secret}` — include `delivered=TRUE` reminders for that person as VEVENT entries with `VALARM DISPLAY` component (5-min default trigger) so external calendar app fires native alert; also include undelivered reminders with future `fire_at` so calendar shows them coming up
- [ ] T063 [US6] Register reminders router at `/api/v1/reminders` and jobs router at `/api/v1/jobs` in `api/main.py`
- [ ] T064 [P] [US6] Create `web/src/app/reminders/page.tsx` — reminder list via `GET /api/v1/reminders`; `fire_at` rendered in APP_TIMEZONE, title, "Delivered" badge for `delivered=TRUE`; "Add Reminder" button; DELETE button per item calls `DELETE /api/v1/reminders/{id}`
- [ ] T065 [US6] Create `web/src/app/reminders/new/page.tsx` — create reminder form: title input, `datetime-local` picker (APP_TIMEZONE display), reads `APP_TIMEZONE` from env; `POST /api/v1/reminders` with `{ fire_at_local, timezone }` on submit

**Checkpoint**: US6 complete — personal timed reminders delivered via iCal feed independently functional

---

## Phase 9: User Story 7 — Overview Dashboard (Priority: P3)

**Goal**: Single screen surfaces overdue tasks → today tasks → today events → shopping counts → upcoming events (7 days) across all user's groups in priority order. Labelled by group name.

**Independent Test**: Seed data: 1 overdue task (group A), 1 event today (group B), 2 unchecked shopping items (group A). `GET /dashboard` returns `overdue_tasks` with that task, `today_events` with that event, `shopping_counts` with count=2; all labelled with correct group names.

### Implementation for User Story 7

- [ ] T065a [US7] Write failing API tests in `api/tests/test_dashboard.py` — `GET /dashboard` returns `overdue_tasks`, `today_tasks`, `today_events`, `shopping_counts`, `upcoming_events` sections; each task and event item includes `group_name`; empty dashboard returns all sections as empty arrays (not 404); all tests MUST fail before T066–T070 are implemented
- [ ] T066 [US7] Implement `api/routers/dashboard.py` — `GET /dashboard`: single optimized multi-query to fetch across all caller's groups: (1) overdue tasks (`due_at < now()`, `done=FALSE`), (2) tasks due today (`done=FALSE`), (3) events today, (4) unchecked shopping item count per group, (5) events in next 7 days; each item includes `group_name`; return structured JSON per `contracts/api.md §Dashboard`
- [ ] T067 [US7] Register dashboard router at `/api/v1/dashboard` in `api/main.py`
- [ ] T068 [P] [US7] Create `web/src/app/dashboard/page.tsx` — fetch data via `GET /api/v1/dashboard`; sections in FR-016 priority order: Overdue Tasks, Today's Tasks, Today's Events, Shopping Counts (badge per group), Upcoming Events (7 days); each item shows group name label; overdue styled amber (never red)
- [ ] T069 [US7] Implement empty dashboard state in `web/src/app/dashboard/page.tsx` — calm positive message (e.g., "All caught up!") with no urgency language, no alarm icons, no red when all 5 sections are empty (US7 acceptance scenario 5, FR-018)
- [ ] T070 [US7] Make `/dashboard` the post-login redirect target in `web/src/app/(auth)/callback/route.ts`; set Dashboard as the active tab highlight in `web/src/components/BottomNav.tsx` on that route

**Checkpoint**: US7 complete — all 7 user stories independently functional and integrated

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility compliance (FR-018), PWA install, headless compliance audit, production deployment validation

- [ ] T071 [P] Apply `prefers-reduced-motion` CSS in `web/src/app/globals.css` — wrap all `transition`/`animation` declarations in `@media (prefers-reduced-motion: no-preference)`; add `.reduce-motion` class that sets `animation: none; transition: none` for the `reduce_motion` ui_pref toggle (FR-018)
- [ ] T072 [P] Apply text-size CSS custom properties in `web/src/app/globals.css` — `--font-scale-normal: 1rem`, `--font-scale-large: 1.125rem`, `--font-scale-xlarge: 1.25rem`; apply from ui_prefs in `web/src/app/layout.tsx` via inline style or data attribute; add Tailwind safelist for dynamic classes (FR-018, FR-019)
- [ ] T073 [P] Apply contrast palette in `web/src/app/globals.css` — default: calm low-saturation token set; `.contrast-high` override class: increase text/background contrast ratios to ≥ 4.5:1; toggle class from ui_prefs `contrast` field in `web/src/app/layout.tsx` (FR-018, FR-019)
- [ ] T074 Audit all page files `web/src/app/*/page.tsx` for FR-018 color compliance — verify no Tailwind `red-*` classes used for non-error states (overdue = amber, info = neutral); replace any violations
- [ ] T075 [P] Audit interactive icon usages across `web/src/components/` and all page files — every icon-only button must have a visible text label (not just `aria-label`); update any icon-only buttons to include a `<span>` label sibling per FR-018
- [ ] T076 Add PWA install prompt: create `web/src/components/InstallPrompt.tsx` (listen for `beforeinstallprompt` event, show "Add to Home Screen" button banner); mount in `web/src/app/layout.tsx` below nav (FR-017)
- [ ] T077 Run `quickstart.md` end-to-end: `supabase db push`, `uvicorn api.main:app`, `npm run dev` in `web/` — fix any migration errors, env var gaps, routing mismatches, or Vercel routing issues discovered during local run
- [ ] T078 [P] Write `api/tests/test_critical_paths.py` — integration tests (pytest + httpx): 401 without auth token, group create → invite generate → invite accept flow, task `done` + `next_occurrence` recurrence, `/jobs/tick` correct-secret delivers reminders and wrong-secret returns 403
- [ ] T079 Validate Vercel bundle: confirm combined Python deps + Next.js assets ≤ 500 MB; verify `vercel.json` routes in preview deployment; confirm Supabase production connection pooler URL and `SCHEDULER_SECRET` set in Vercel environment variables; configure cron-job.org job targeting `GET https://{vercel_domain}/api/v1/jobs/tick` with `X-Scheduler-Secret: {SCHEDULER_SECRET}` header at ≤10 minute interval (required for SC-004, FR-015); run `vercel --prod` per `quickstart.md §7`
- [ ] T080 [P] Audit frontend for FR-023 headless compliance — run `sg run --pattern 'supabase.from($A)' --lang ts web/src/` and `sg run --pattern 'supabase.from($A)' --lang tsx web/src/` to confirm no direct Supabase table queries exist in `web/src/**` outside `web/src/lib/realtime.ts`; any hit that is NOT in `realtime.ts` is a violation of FR-023 and MUST be replaced with a call to the corresponding `/api/v1/*` endpoint; document approved exceptions (realtime.ts) with inline comment

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Requires Phase 1 complete — BLOCKS all user stories
- **US1 Login (Phase 3)**: Requires Phase 2; BLOCKS US2–US7 (auth precondition for all)
- **US2 Groups (Phase 4)**: Requires US1 — groups need authenticated users
- **US3 Tasks (Phase 5)**: Requires US2 — tasks scoped to groups; independent of US4, US5
- **US4 Shopping (Phase 6)**: Requires US2 — shopping scoped to groups; independent of US3, US5
- **US5 Events (Phase 7)**: Requires US2 — events scoped to groups; independent of US3, US4
- **US6 Reminders (Phase 8)**: Requires US5 — reminders extend the iCal feed built in US5
- **US7 Dashboard (Phase 9)**: Requires US3, US4, US5 — aggregates tasks, shopping, events
- **Polish (Phase 10)**: Requires all user stories complete

### User Story Dependencies

- **US1 (P1)** → after Foundational: no story deps
- **US2 (P1)** → after US1: needs authenticated users
- **US3 (P2)** → after US2: tasks need groups
- **US4 (P2)** → after US2: shopping needs groups; **parallel with US3**
- **US5 (P2)** → after US2: events need groups; **parallel with US3, US4**
- **US6 (P3)** → after US5: reminders extend iCal feed
- **US7 (P3)** → after US3, US4, US5: aggregates all data

### Within Each User Story

- API router before Next.js pages (frontend needs endpoints — headless: REST first, then UI)
- Models defined in Foundational (T012) before any router can reference them
- Core endpoint implementation before feed/dashboard extension (e.g., T053 before T062)

---

## Parallel Examples

### Phase 1 Setup — all [P] tasks can start together

```bash
# Run simultaneously:
T003: Configure web/package.json
T004: Configure web/next.config.ts, tailwind, tsconfig
T005: Create vercel.json
T006: Create .env.example files
T007: Configure web/.eslintrc.json + .prettierrc
T008: Initialize api/main.py skeleton (OpenAPI schema included)
```

### After US2 Complete — US3 + US4 + US5 in parallel

```bash
# Developer A: User Story 3 (Tasks) — T035–T043
# Developer B: User Story 4 (Shopping) — T044–T050
# Developer C: User Story 5 (Events + iCal) — T051–T059
```

### Within US2 — parallel API + frontend

```bash
# Simultaneously:
T027: Implement api/routers/groups.py POST/GET
T029: Implement api/routers/invites.py create/accept
T031: Create web/src/app/groups/page.tsx list
T032: Create web/src/app/groups/new/page.tsx form
# Then sequentially:
T028: Leave group / owner-departure logic (depends on T027)
T033: Group detail page (depends on T027, T029)
T034: Join invite page (depends on T029)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL — blocks all**)
3. Complete Phase 3: US1 — Passwordless Login
4. Complete Phase 4: US2 — Household + Invite
5. **STOP and VALIDATE**: Formed household with authenticated members — core social structure works
6. Deploy to Vercel Hobby + Supabase free tier — demo to family

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. +US1 → Authenticated users (required building block)
3. +US2 → Formed households ← **Demo-able milestone**
4. +US3, US4, US5 (parallel) → Tasks, shopping, events ← **Core product value**
5. +US6, US7 → Reminders + dashboard ← **Full MVP**
6. +Polish → Accessibility + headless audit + production-ready ← **Ship**

### Parallel Team Strategy

With multiple developers:
- Dev A: US1 → US2 (sequential, auth dependency)
- Once US2 complete:
  - Dev A: US3 (tasks)
  - Dev B: US4 (shopping + offline)
  - Dev C: US5 (events + iCal)
- All join: US6, US7, Polish

---

## Notes

- `[P]` = different files, no pending deps — safe to parallelize
- `[Story]` label maps each task to its user story for independent delivery tracking
- Each story phase ends at a testable checkpoint before moving forward
- TDD: 8 test tasks (T008a, T018a, T026a, T034a, T043a, T050a, T059a, T065a) — write failing tests before each story's implementation; Red → Green → Refactor (constitution §II)
- **Headless constraint (FR-023)**: frontend MUST NOT query Supabase tables directly; all data ops go through `/api/v1/*` REST calls; only approved exceptions are (1) Supabase Auth session management in `web/src/lib/supabase.ts` and (2) Supabase Realtime subscription in `web/src/lib/realtime.ts`; T080 audits compliance before ship
- All timestamps stored UTC; `APP_TIMEZONE` drives display only (research.md §8)
- Serverless constraint: no on-disk state, no long-lived DB connections — pooler only (T010 critical)
- Recursive CTE (`person_reachable_groups`) is the single RLS anchor for event rollup — do not bypass it with application-layer joins (research.md §4)
- Last-write-wins for shopping conflicts: server always sets `updated_at` on PATCH — do not let client set it (research.md §3, spec clarification Q1)
- FastAPI auto-generates OpenAPI schema at `/api/v1/docs` and `/api/v1/openapi.json` — any future client (mobile app, CLI) can consume the API contract directly
