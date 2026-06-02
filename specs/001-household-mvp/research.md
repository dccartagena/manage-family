# Research: Household Manager MVP

**Branch**: `001-household-mvp` | **Date**: 2026-06-03

## Decision Log

### 1. Frontend Framework

**Decision**: Next.js 14 (App Router) + shadcn/ui (Radix-based)

**Rationale**: Vercel-native — zero-config deployment, built-in ISR, edge middleware for session
refresh, first-class TypeScript support. Masterplan explicitly notes "Next = Vercel-native".
shadcn/ui provides accessible Radix primitives with Tailwind styling, satisfying the
accessibility-first component library requirement from section 9 of the masterplan and FR-018.

**Alternatives considered**:
- SvelteKit + Melt UI/Bits UI: smaller runtime bundle, excellent accessibility libs, but requires
  explicit Vercel adapter configuration and has a smaller Supabase ecosystem. Risk: deployment
  surprises on Hobby tier. Rejected on integration risk, not capability.

---

### 2. iCal Feed Generation

**Decision**: `icalendar` Python library for RFC 5545 output; `recurring-ical-events` for
server-side recurrence expansion when generating feed content.

**Rationale**: `icalendar` is the de facto standard for Python iCal generation (production-grade,
actively maintained, RFC-compliant). `recurring-ical-events` expands RRULE strings into concrete
occurrences for a given time window — needed when `/ical/{secret}` must enumerate upcoming
occurrences for external calendar apps.

**Alternatives considered**: Hand-rolled string templating. Rejected: brittle, not RFC 5545
compliant, breaks on edge cases (DST transitions, multi-day events, all-day events).

---

### 3. Offline Sync Strategy

**Decision**: Workbox `NetworkFirst` strategy for list API calls; `CacheFirst` for static assets.
Mutations queued in IndexedDB when offline; replayed via service worker on reconnection.
Conflict resolution: **last-write-wins** by `updated_at` timestamp (clarified in spec).

**Rationale**: Lists (tasks, shopping) must be fresh when online — NetworkFirst ensures this.
When offline, the cached response serves stale data clearly labelled as offline. Mutations
(check item, mark task done) are locally applied optimistically and queued. On reconnect,
the queue is drained in order; server's `updated_at` determines winner for any concurrent edit.

**Alternatives considered**: Cache-then-network (race condition on slow connections);
background sync API (poor iOS support). Rejected for reliability reasons.

---

### 4. RLS Policy Design for Group Tree Visibility

**Decision**: Two classes of RLS policy, backed by a reusable `person_reachable_groups`
Postgres function.

```sql
-- Returns all group IDs that person_id can see events/reminders FROM
-- (own groups + all ancestor groups in the tree)
CREATE OR REPLACE FUNCTION person_reachable_groups(p_id UUID)
RETURNS TABLE(id UUID) AS $$
  WITH RECURSIVE tree AS (
    SELECT g.id, g.parent_group_id
    FROM groups g
    JOIN memberships m ON m.group_id = g.id AND m.person_id = p_id
    UNION ALL
    SELECT g.id, g.parent_group_id
    FROM groups g
    JOIN tree t ON g.id = t.parent_group_id
  )
  SELECT id FROM tree;
$$ LANGUAGE sql STABLE SECURITY DEFINER;
```

**Operations data (tasks, shopping_items)** — visible only within owning household:
```sql
USING (
  EXISTS (
    SELECT 1 FROM memberships
    WHERE group_id = [table].group_id
    AND person_id = auth.uid()
  )
)
```

**Events** — visible to owning group members AND all ancestor group members (rollup):
```sql
USING (
  [table].group_id IN (SELECT id FROM person_reachable_groups(auth.uid()))
)
```

**Reminders** — owned by person, no group scoping:
```sql
USING (person_id = auth.uid())
```

**Rationale**: Single recursive CTE function keeps policy logic in one place; policies stay
thin. `SECURITY DEFINER` allows the function to query groups without triggering its own RLS.
Recursive CTE is fast at ≤5 levels and ~20 groups — no closure table needed (constitution
explicitly prohibits closure tables here).

**Alternatives considered**: Closure table for O(1) ancestor lookups. Rejected: premature
optimisation, adds a write-time maintenance burden, prohibited by constitution.

---

### 5. External Scheduler Protection (`/jobs/tick`)

**Decision**: Shared secret in `X-Scheduler-Secret` HTTP header, validated against
`SCHEDULER_SECRET` environment variable. Returns 403 immediately on mismatch.

**Rationale**: Calendar clients cannot send auth headers (so the secret lives in the iCal URL),
but the scheduler endpoint is server-to-server and CAN use a header — cleaner than a URL secret
for a POST/GET endpoint. `SCHEDULER_SECRET` is a random 32-byte hex string set in Vercel env
vars and in cron-job.org's custom headers configuration.

**Alternatives considered**: URL query param secret (leaks in server logs); IP allowlist
(cron-job.org uses many IPs, allowlist maintenance burden). Rejected.

---

### 6. Supabase Realtime for Shopping List

**Decision**: Supabase Realtime `postgres_changes` subscription, one channel per household
(`shopping:group_id=eq.{group_id}`).

**Rationale**: Supabase Realtime broadcasts Postgres WAL changes to subscribed clients with
≤1s latency in practice — well within the 3-second SC-002 target. Filtering by `group_id`
ensures each client only receives changes for their household. No WebSocket server to manage
(Supabase hosts it). Free tier supports Realtime.

**Pattern**:
```ts
const channel = supabase
  .channel(`shopping:${groupId}`)
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'shopping_items',
    filter: `group_id=eq.${groupId}`,
  }, (payload) => updateLocalState(payload))
  .subscribe()
```

**Alternatives considered**: Polling every 5 seconds (misses the 3s target under load);
custom WebSocket server (cannot run in serverless). Rejected.

---

### 7. Magic Link Auth Flow

**Decision**: Supabase Auth `signInWithOtp({ email })` → magic link → `@supabase/ssr`
session management in Next.js middleware → JWT passed as `Authorization: Bearer` header to
FastAPI → `python-jose` + Supabase JWKS verification.

**Flow**:
1. User enters email → `supabase.auth.signInWithOtp({ email })`
2. Supabase sends magic link email
3. User clicks link → Supabase redirects to `/auth/callback?code=...`
4. Next.js callback route exchanges code for session via `supabase.auth.exchangeCodeForSession`
5. Session cookie set; `middleware.ts` refreshes on every request
6. API calls include `Authorization: Bearer {access_token}`
7. FastAPI `auth.py` validates JWT signature against Supabase JWKS endpoint

**Alternatives considered**: Manual JWT handling in Next.js (reinvents what `@supabase/ssr`
provides); server-side session store (stateful, violates serverless constraint). Rejected.

---

### 8. Timezone Handling

**Decision**: All timestamps stored as UTC `TIMESTAMPTZ` in Postgres. `fire_at` for reminders
computed server-side from user's local wall-clock time using `zoneinfo` IANA lookup. Frontend
renders times using `Intl.DateTimeFormat` with the configured app timezone.

**App timezone**: Single IANA timezone string in environment config (e.g., `APP_TIMEZONE=Europe/London`). All users share this timezone (per spec assumption: single-country app).

**Why**: `zoneinfo` (Python 3.9+ stdlib) handles DST automatically — no fixed UTC offsets that
break twice a year. This is a non-negotiable constitution constraint.

**Alternatives considered**: Fixed UTC offset per user; client-side `Date` objects for storage.
Both rejected: DST breaks, sync bugs across devices.

---

### 9. Recurring Task Next-Occurrence Generation

**Decision**: When a recurring task is marked done, the API computes the next occurrence using
`python-dateutil`'s `rrule` parser from the task's `rrule` field + current `due_at`. A new
Task row is **inserted** with `done=False` and the computed `due_at`. The original row is
**not** deleted (historical record).

**Rationale**: Append-only is simpler to reason about and avoids race conditions from updating
the same row. Keeps task history. The done row is filtered out of active lists.

**Alternatives considered**: Updating `due_at` in place (loses history, race condition if two
clients race); generating all future occurrences at creation time (unbounded rows). Rejected.
