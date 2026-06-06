# API Contracts: Household Manager MVP

**Branch**: `001-household-mvp` | **Date**: 2026-06-03

All endpoints are REST over HTTPS. Base path: `/api/v1`.
Authentication: `Authorization: Bearer {supabase_access_token}` on all endpoints except
`/health` and `/ical/{secret}` (feed URL is its own secret).

Error envelope:
```json
{ "detail": "<human-readable message>", "code": "<machine-readable code>" }
```

---

## Health

### `GET /health`
No auth. Returns 200 when API is reachable.

**Response 200**:
```json
{ "status": "ok" }
```

---

## Groups

### `POST /groups`
Create a new household group. Caller becomes owner.

**Request**:
```json
{ "name": "Smith Family", "parent_group_id": "<uuid|null>" }
```

**Response 201**:
```json
{
  "id": "<uuid>",
  "name": "Smith Family",
  "parent_group_id": null,
  "depth": 0,
  "role": "owner"
}
```

**Errors**: 400 if parent_group_id has depth = 4 (would exceed max nesting).

---

### `GET /groups`
List all groups the caller is a member of.

**Response 200**:
```json
[
  { "id": "<uuid>", "name": "Smith Family", "depth": 0, "role": "owner" },
  { "id": "<uuid>", "name": "London Household", "depth": 1, "role": "member" }
]
```

---

### `DELETE /groups/{group_id}/membership`
Leave a group. Triggers auto-promotion or group deletion per owner-departure rules.

**Response 204**: No content.

**Errors**: 403 if caller is not a member.

---

## Invites

### `POST /groups/{group_id}/invites`
Generate an invite link. Caller must be owner.

**Request**:
```json
{ "expires_at": "<ISO8601|null>", "max_uses": "<int|null>" }
```

**Response 201**:
```json
{
  "id": "<uuid>",
  "token": "<64-char hex>",
  "invite_url": "https://<app>/join/<token>",
  "expires_at": null,
  "max_uses": null,
  "uses": 0
}
```

**Errors**: 403 if caller is not owner.

---

### `POST /invites/{token}/accept`
Accept an invite. Creates a membership for the caller. Idempotent if already a member.

**Response 200**:
```json
{ "group_id": "<uuid>", "group_name": "Smith Family", "role": "member" }
```

**Errors**: 410 if token expired or exhausted.

---

## Tasks

### `GET /groups/{group_id}/tasks`
List tasks for a household. Supports query params: `?done=false`, `?assignee_id=<uuid>`.

**Response 200**:
```json
[
  {
    "id": "<uuid>",
    "title": "Take out bins",
    "rrule": "FREQ=WEEKLY;BYDAY=SU",
    "due_at": "2026-06-07T20:00:00Z",
    "done": false,
    "assignee_id": "<uuid|null>"
  }
]
```

---

### `POST /groups/{group_id}/tasks`
Create a task.

**Request**:
```json
{
  "title": "Take out bins",
  "rrule": "FREQ=WEEKLY;BYDAY=SU",
  "due_at": "2026-06-07T20:00:00Z",
  "assignee_id": "<uuid|null>"
}
```

**Response 201**: Full task object (same shape as GET item).

---

### `PATCH /tasks/{task_id}`
Update task fields (title, assignee, due_at). Partial update.

**Request**: Any subset of `{ "title", "assignee_id", "due_at", "rrule" }`.

**Response 200**: Updated task object.

---

### `POST /tasks/{task_id}/done`
Mark task done. If recurring, inserts next occurrence and returns it.

**Response 200**:
```json
{
  "task": { /* completed task with done=true */ },
  "next_occurrence": { /* new task row | null if one-off */ }
}
```

---

### `DELETE /tasks/{task_id}/done`
Mark task undone (toggle back).

**Response 200**: Updated task object with `done: false`.

---

## Shopping

### `GET /groups/{group_id}/shopping`
List shopping items.

**Response 200**:
```json
[
  { "id": "<uuid>", "name": "Milk", "checked": false, "updated_at": "..." }
]
```

---

### `POST /groups/{group_id}/shopping`
Add an item.

**Request**: `{ "name": "Milk" }`

**Response 201**: Shopping item object.

---

### `PATCH /shopping/{item_id}`
Check/uncheck or rename an item. `updated_at` is server-set (last-write-wins arbiter).

**Request**: Any subset of `{ "name", "checked" }`.

**Response 200**: Updated item with new `updated_at`.

---

### `DELETE /shopping/{item_id}`
Delete an item.

**Response 204**: No content.

---

## Events

### `GET /groups/{group_id}/events`
List events visible to caller for this group (respects rollup RLS).

**Response 200**:
```json
[
  {
    "id": "<uuid>",
    "group_id": "<uuid>",
    "title": "School play",
    "starts_at": "2026-06-13T18:00:00Z",
    "rrule": null
  }
]
```

---

### `POST /groups/{group_id}/events`
Create an event.

**Request**:
```json
{ "title": "School play", "starts_at": "2026-06-13T18:00:00Z", "rrule": null }
```

**Response 201**: Full event object.

---

### `DELETE /events/{event_id}`
Delete an event. Caller must be member of the owning group.

**Response 204**: No content.

---

## Reminders

### `GET /reminders`
List caller's reminders.

**Response 200**:
```json
[
  { "id": "<uuid>", "title": "Bins out", "fire_at": "2026-06-08T20:00:00Z", "delivered": false }
]
```

---

### `POST /reminders`
Create a one-shot reminder.

**Request**:
```json
{ "title": "Bins out", "fire_at_local": "2026-06-08T20:00:00", "timezone": "Europe/London" }
```
Server converts `fire_at_local + timezone → UTC` using `zoneinfo`.

**Response 201**: Reminder object with UTC `fire_at`.

---

### `DELETE /reminders/{reminder_id}`
Delete a reminder.

**Response 204**: No content.

---

## iCal Feed

### `GET /ical/{secret}`
No auth header. `secret` = `person.ical_secret` (UUID). Returns the user's personal iCal feed.

**Response 200**:
- Content-Type: `text/calendar; charset=utf-8`
- Body: RFC 5545 `.ics` file containing:
  - All events visible to the user (own groups + ancestor groups via rollup)
  - All due and pending reminders for the user

**Response 404**: If `secret` not found (covers rotated URL case).

---

### `POST /ical/rotate`
Authenticated. Rotates the caller's `ical_secret`. Old URL returns 404 immediately.

**Response 200**:
```json
{ "new_feed_url": "https://<app>/api/v1/ical/<new-uuid>" }
```

---

## Scheduler

### `GET /jobs/tick`
Protected by `X-Scheduler-Secret` header. Called by cron-job.org every ~5 minutes.

**Request header**: `X-Scheduler-Secret: <SCHEDULER_SECRET env var value>`

**Response 200**:
```json
{ "reminders_delivered": 3, "tick_at": "2026-06-03T12:05:00Z" }
```

**Response 403**: If header missing or secret mismatch.

**Behavior**: Finds all reminders where `fire_at <= now()` AND `delivered = FALSE`,
sets `delivered = TRUE`. These reminders will appear in the user's next iCal feed poll.

---

## Dashboard

### `GET /dashboard`
Returns urgency-ranked summary across all the caller's groups.

**Response 200**:
```json
{
  "overdue_tasks": [
    { "id": "<uuid>", "title": "...", "group_name": "...", "due_at": "..." }
  ],
  "today_tasks": [ /* same shape */ ],
  "today_events": [
    { "id": "<uuid>", "title": "...", "group_name": "...", "starts_at": "..." }
  ],
  "shopping_counts": [
    { "group_id": "<uuid>", "group_name": "...", "unchecked_count": 3 }
  ],
  "upcoming_events": [
    { "id": "<uuid>", "title": "...", "group_name": "...", "starts_at": "..." }
  ]
}
```

Priority order matches FR-016: overdue_tasks → today_tasks → today_events → shopping_counts → upcoming_events (next 7 days).

---

## Person Preferences

### `PATCH /person/prefs`
Update caller's display preferences.

**Request**: Any subset of:
```json
{
  "text_size": "normal|large|xlarge",
  "contrast": "normal|high",
  "reduce_motion": true,
  "notification_batching": "immediate|morning_summary"
}
```

**Response 200**: Updated `ui_prefs` object.
