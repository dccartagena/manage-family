# Data Model: Household Manager MVP

**Branch**: `001-household-mvp` | **Date**: 2026-06-03

## Entity Definitions

### Person

Represents one registered user. Exists independently of any household.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| email | TEXT | NOT NULL, UNIQUE | Supabase Auth user email |
| display_name | TEXT | NOT NULL | |
| ui_prefs | JSONB | NOT NULL, DEFAULT '{}' | Keys: text_size, contrast, reduce_motion, notification_batching |
| ical_secret | UUID | NOT NULL, UNIQUE, DEFAULT gen_random_uuid() | Rotatable; lives in iCal feed URL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**State transitions**: `ical_secret` may be rotated on demand (FR-014). New UUID generated; old URL immediately invalid.

---

### Group

A named node in the family tree. Self-referencing parent enables nesting.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| parent_group_id | UUID | FK → group(id), NULLABLE | NULL = root group |
| name | TEXT | NOT NULL | |
| depth | SMALLINT | NOT NULL, DEFAULT 0, CHECK (depth BETWEEN 0 AND 4) | 0 = root; max 5 levels |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**State transitions**:
- Creation: `depth` = parent's `depth + 1`; parent must have `depth < 4`
- Deletion: Triggered when sole member-owner leaves (FR-021); cascades to all owned entities

**Invariants**:
- `depth` must equal the number of ancestor hops to a root group
- Circular parent references are prohibited (enforced by application layer before insert)

---

### Membership

Links one person to one group with a role. Many-to-many with role.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| person_id | UUID | FK → person(id) NOT NULL | |
| group_id | UUID | FK → group(id) NOT NULL | |
| role | TEXT | NOT NULL, CHECK (role IN ('owner', 'member')) | |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Used for owner auto-promotion (longest-standing member) |
| UNIQUE | (person_id, group_id) | | One membership per person per group |

**State transitions**:
- Join: New row via invite token acceptance
- Leave: Row deleted; if departing person is owner → see Owner Departure rules below
- Role change: `role` updated from 'member' to 'owner' during auto-promotion

**Owner Departure Rules** (FR-020, FR-021):
1. If other members exist: member with smallest `joined_at` is promoted to owner; departing owner's row deleted
2. If sole member: group deleted (cascade deletes all tasks, shopping items, events, reminders, invites for this group)

---

### Invite

A shareable, time-limited, use-counted token for joining a group.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → group(id) NOT NULL | |
| created_by | UUID | FK → person(id) NOT NULL | Must be owner of group |
| token | TEXT | NOT NULL, UNIQUE, DEFAULT encode(gen_random_bytes(32), 'hex') | 64-char hex; lives in invite URL |
| expires_at | TIMESTAMPTZ | NULLABLE | NULL = no expiry |
| max_uses | INTEGER | NULLABLE, CHECK (max_uses > 0) | NULL = unlimited |
| uses | INTEGER | NOT NULL, DEFAULT 0 | Incremented on each accepted join |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**Validity check**: An invite is valid when:
- `expires_at IS NULL OR expires_at > now()`
- `max_uses IS NULL OR uses < max_uses`

**State transitions**:
- Active → Exhausted: `uses` reaches `max_uses`
- Active → Expired: `expires_at` passes
- Redemption: `uses` incremented atomically; Membership row created in same transaction

---

### Task

A household-scoped work item with optional recurrence and assignment.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → group(id) NOT NULL | |
| assignee_id | UUID | FK → person(id) NULLABLE | Cleared when assignee leaves (FR-022) |
| title | TEXT | NOT NULL | |
| rrule | TEXT | NULLABLE | iCal RRULE string; NULL = one-off task |
| done | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| due_at | TIMESTAMPTZ | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Auto-updated via trigger |

**State transitions**:
- Undone → Done: `done = TRUE`; if `rrule IS NOT NULL` → new Task row inserted with `done = FALSE` and `due_at` = next occurrence (computed via `python-dateutil`)
- Done → Undone: `done = FALSE` (toggle for one-off tasks)
- Assignee removal: `assignee_id` set to NULL when membership deleted (FR-022)

**Visibility**: LOCAL to owning group (RLS: membership check only, no rollup)

---

### ShoppingItem

A household-scoped list entry; real-time sync via Supabase Realtime.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → group(id) NOT NULL | |
| name | TEXT | NOT NULL | |
| checked | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last-write-wins arbiter |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**Conflict resolution**: Last-write-wins by `updated_at`. On offline sync, the mutation with the
most recent `updated_at` is applied; earlier conflicting mutations are silently discarded.

**Visibility**: LOCAL to owning group (RLS: membership check only, no rollup)

---

### Event

A household-scoped happening with optional recurrence. Rolls up to ancestor groups.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| group_id | UUID | FK → group(id) NOT NULL | |
| title | TEXT | NOT NULL | |
| starts_at | TIMESTAMPTZ | NOT NULL | UTC |
| rrule | TEXT | NULLABLE | iCal RRULE string |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**Visibility**: ROLLS UP — visible to members of owning group AND all ancestor groups
(RLS: `person_reachable_groups` function, see research.md §4)

---

### Reminder

A personal, one-shot timed alert. Delivered via calendar feed when due.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| person_id | UUID | FK → person(id) NOT NULL | |
| title | TEXT | NOT NULL | |
| fire_at | TIMESTAMPTZ | NOT NULL | UTC; computed from wall-clock + IANA zone (zoneinfo) |
| delivered | BOOLEAN | NOT NULL, DEFAULT FALSE | Set TRUE by /jobs/tick when past due |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**State transitions**:
- Pending (`delivered = FALSE`, `fire_at > now()`): not yet in feed
- Due (`fire_at <= now()`, `delivered = FALSE`): `/jobs/tick` moves it into the iCal feed and sets `delivered = TRUE`
- Delivered (`delivered = TRUE`): remains in feed for the calendar app's next poll cycle

**Visibility**: Personal — RLS: `person_id = auth.uid()` only

---

## Relationships

```
Person ────< Membership >──── Group ────< Group (self, parent nesting)
Person ────< Reminder
Group  ────< Task
Group  ────< ShoppingItem
Group  ────< Event
Group  ────< Invite
Person ─────< Task (assignee_id, nullable)
```

## RLS Policy Summary

| Table | Policy | Condition |
|-------|--------|-----------|
| person | SELECT/UPDATE own row | `id = auth.uid()` |
| group | SELECT | member of group (via membership) |
| group | INSERT | authenticated user (becomes owner via membership insert) |
| membership | SELECT | own rows OR rows in groups user belongs to |
| invite | SELECT/INSERT | owner of the referenced group |
| task | ALL | member of group |
| shopping_items | ALL | member of group |
| event | SELECT | `group_id IN (SELECT id FROM person_reachable_groups(auth.uid()))` |
| event | INSERT/UPDATE/DELETE | member of group |
| reminder | ALL | `person_id = auth.uid()` |

## Migration Strategy

Alembic manages all schema changes. Migration files live in `api/migrations/`.
Baseline migration creates all tables, indexes, RLS policies, and the `person_reachable_groups` function.

**Key indexes**:
- `memberships(person_id)` — group tree traversal
- `memberships(group_id)` — member lookups
- `tasks(group_id, done, due_at)` — dashboard query
- `shopping_items(group_id)` — list fetch
- `events(group_id, starts_at)` — calendar feed
- `reminders(person_id, delivered, fire_at)` — tick job
- `invites(token)` — invite acceptance lookup
