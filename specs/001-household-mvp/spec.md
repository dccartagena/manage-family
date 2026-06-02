# Feature Specification: Household Manager MVP

**Feature Branch**: `001-household-mvp`

**Created**: 2026-06-02

**Status**: Draft

**Input**: User description: "Build the MVP for Household Manager based on the attached masterplan"

## Clarifications

### Session 2026-06-02

- Q: How should concurrent shopping item edits be resolved when two devices check an item simultaneously (e.g., one offline)? → A: Last write wins — most recent timestamp overwrites any conflict
- Q: What ordering rule defines "urgency" on the overview dashboard? → A: Overdue tasks first → today's tasks → today's events → outstanding shopping count → upcoming events (next 7 days)
- Q: What happens when the sole owner of a group leaves? → A: If other members exist, the longest-standing member is automatically promoted to owner; if the owner is the only member, the group and all its data are deleted
- Q: Do reminders support recurrence rules like tasks and events? → A: No — reminders are always one-shot; recurring alerts are covered by recurring events
- Q: What happens to a recurring task when its assignee is removed from the household? → A: Task stays, assignee field is cleared; task becomes unassigned and visible to all household members

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Passwordless Login (Priority: P1)

A person receives a magic link in their email and clicks it to log in. No password is created
or remembered. On subsequent visits, the same one-click flow applies.

**Why this priority**: Every other story depends on identity. Without login nothing else works.
First thing every user hits. Passwordless is an explicit accessibility and UX requirement.

**Independent Test**: Send a magic-link email, click link, confirm landing in the app as an
authenticated user with a visible profile. Delivers standalone value: verified identity.

**Acceptance Scenarios**:

1. **Given** a person has not yet logged in, **When** they enter their email and request a link, **Then** an email with a login link arrives within 60 seconds
2. **Given** a person clicks a valid magic link, **When** it has not expired, **Then** they are logged in and land on the dashboard
3. **Given** a person clicks an expired or already-used magic link, **When** attempting authentication, **Then** they see a clear error message and are prompted to request a new link
4. **Given** a logged-in person returns to the app, **When** their session is still valid, **Then** they are taken directly to the dashboard without re-authenticating

---

### User Story 2 - Create Household & Invite Members (Priority: P1)

A person creates a household group, becomes its owner, generates a shareable invite link, and
sends it to family members. Each recipient clicks the link, authenticates, and joins the household.
A person can belong to multiple unrelated households simultaneously.

**Why this priority**: Without at least one household and two members, no other feature (tasks,
shopping, events) has meaningful collaborative value. This unlocks all social features.

**Independent Test**: One user creates group; second user joins via link; both see each other
as members. Delivers standalone value: a formed household ready for daily use.

**Acceptance Scenarios**:

1. **Given** a logged-in person creates a household, **When** creation completes, **Then** they are listed as owner and the household appears in their list
2. **Given** an owner, **When** they generate an invite link, **Then** a unique link is produced that can be shared externally
3. **Given** a recipient opens an invite link, **When** they authenticate, **Then** a membership is created and they see the household in their list
4. **Given** an invite link has reached its use limit or expiry, **When** a new recipient tries to use it, **Then** the link is rejected with a clear message
5. **Given** a person is a member of two unrelated households, **When** they view their app, **Then** both households are listed and their data is separately scoped
6. **Given** a household group is nested under a parent group (e.g., a sub-family), **When** a member of the parent views their data, **Then** they can see events from the sub-group but not its tasks or shopping

---

### User Story 3 - Chores & Recurring Tasks (Priority: P2)

A household member creates a chore (e.g., "Take out bins"), assigns it to another member, and
sets it to repeat weekly. The assignee marks it done; the next occurrence appears automatically.

**Why this priority**: Chores are the primary daily driver. Once people have a household, this
is the first thing they use. Validates core product value.

**Independent Test**: Create recurring task, assign it, mark done, verify next occurrence
regenerates. Delivers standalone value: shared chore tracking.

**Acceptance Scenarios**:

1. **Given** a household member creates a task with a recurrence (e.g., weekly), **When** the task is saved, **Then** it appears in the task list with its recurrence stated
2. **Given** a task exists, **When** a member assigns it to another household member, **Then** the assignee sees it listed under their assignments
3. **Given** an assignee marks a task done, **When** the action is confirmed, **Then** the task shows a persistent "Done" state and the next scheduled occurrence is queued
4. **Given** a one-off task is marked done, **When** done is toggled, **Then** it shows done state; toggling again restores it to undone
5. **Given** a member views the task list, **When** filters are applied (e.g., "assigned to me" or "today"), **Then** only matching tasks are shown
6. **Given** a task is overdue, **When** viewed in the list, **Then** it is visually distinguished without using red (red is reserved for errors only)

---

### User Story 4 - Shared Shopping List (Priority: P2)

A household member adds "Milk" to the shopping list. While one person is shopping, they check
off "Milk" on their phone. Every other household member's list updates immediately without
page refresh.

**Why this priority**: Real-time shopping list is a daily driver and the feature most likely
to convert sceptical family members. Validates the real-time sync capability.

**Independent Test**: Two devices in same household; item checked on one appears checked on
other within seconds. Delivers standalone value: collaborative shopping coordination.

**Acceptance Scenarios**:

1. **Given** a household member adds an item to the shopping list, **When** another member views the list, **Then** the item is visible without requiring a page refresh
2. **Given** a member checks off an item, **When** the action is confirmed, **Then** the item appears visually distinct (checked/greyed) for all household members within 3 seconds
3. **Given** a member unchecks an item, **When** the action is confirmed, **Then** the item returns to unchecked state for all members
4. **Given** a member deletes an item, **When** the action is confirmed, **Then** the item disappears from all members' lists
5. **Given** a device goes offline, **When** the member returns online, **Then** changes made offline are synchronised using last-write-wins; the most recently timestamped state for each item prevails

---

### User Story 5 - Household Events & Calendar Feed (Priority: P2)

A household creates a "School play" event for next Friday. A grandparent at the top of the
family tree subscribes to their iCal feed URL and sees the event appear in Google Calendar.
Native calendar alerts fire at the right time.

**Why this priority**: Calendar feed is what makes this more than a to-do app and delivers
notifications on every platform, including iPhone, without any push infrastructure.

**Independent Test**: Create event in sub-household; subscribe parent's iCal URL in Google
Calendar; event appears; native alert fires. Delivers standalone value: cross-platform
notification without push infrastructure.

**Acceptance Scenarios**:

1. **Given** a household member creates an event with a date and title, **When** another member views the calendar, **Then** the event is listed
2. **Given** an event is created in a sub-group, **When** a parent-group member views their calendar feed, **Then** the event is included in their feed
3. **Given** a user's iCal feed URL is subscribed in an external calendar, **When** the external calendar polls the feed, **Then** the feed returns valid iCal data containing all events and due reminders for that user
4. **Given** an event has a recurrence rule, **When** the feed is polled, **Then** all future occurrences within a reasonable horizon are included in the iCal data
5. **Given** a user's feed URL may have been exposed, **When** the user resets their feed URL, **Then** the old URL stops returning data and a new secret URL is active

---

### User Story 6 - Timed Reminders (Priority: P3)

A household member sets a reminder: "Put bins out – 8pm Sunday". At approximately 8pm on Sunday
their phone's native calendar app fires an alert. No app notification infrastructure required.

**Why this priority**: Reminders complete the notification story. Builds on the calendar feed.
Useful but not blocking — the app has value without it.

**Independent Test**: Create reminder for a specific time; observe it appear in calendar feed
after the scheduler tick; verify native calendar alert fires. Delivers standalone value: time-based alerts.

**Acceptance Scenarios**:

1. **Given** a member creates a reminder with a specific date/time, **When** the scheduled time arrives, **Then** the reminder appears in the member's iCal feed within 10 minutes
2. **Given** a reminder is in the calendar feed, **When** the subscribed external calendar app fires its native alert, **Then** the alert matches the reminder title and time
3. **Given** a reminder has fired, **When** the member views their reminders list, **Then** the reminder shows as delivered

---

### User Story 7 - Overview Dashboard (Priority: P3)

A person with two households opens the app and sees a single prioritised list ordered as: overdue tasks, today's tasks, today's events, outstanding shopping count, then upcoming events within 7 days — all sourced from all their groups.

**Why this priority**: The dashboard surfaces the answer to "what needs my attention?" — the
core product question. Requires all other features to exist first.

**Independent Test**: Seed one household with overdue tasks and another with upcoming events; dashboard shows all in correct priority order (overdue → today → events → shopping → upcoming), correctly scoped. Delivers standalone value: single view across all families.

**Acceptance Scenarios**:

1. **Given** a member has overdue tasks across any of their households, **When** they open the dashboard, **Then** overdue tasks appear at the top, visually prioritised without using red
2. **Given** a member has upcoming events within the next 7 days, **When** they view the dashboard, **Then** events are shown with day and time
3. **Given** a member has unchecked shopping items, **When** they view the dashboard, **Then** the shopping count is shown
4. **Given** a member belongs to two households with separate data, **When** they view the dashboard, **Then** items from both appear, labelled with their household name
5. **Given** a member has no pending items, **When** they view the dashboard, **Then** a calm, positive empty state is shown (no alarm, no urgency language)

---

### Edge Cases

- What happens when a user is the sole owner of a group and tries to leave? → If other members exist, the longest-standing member is auto-promoted to owner. If the owner is the only member, the group and all its data are permanently deleted.
- What happens when an invite link is shared publicly and reaches its use limit before the intended recipient joins?
- What happens when a recurring task's assignee is removed from the household? → Task remains; assignee field is cleared; task becomes unassigned and visible to all remaining household members for pick-up
- What happens when a device is offline and a shopping item is checked simultaneously on two different devices? → Last-write-wins: the check with the most recent timestamp is the final state; no conflict UI required
- What happens when a user's calendar app polls the feed URL after it has been reset?
- What happens when a reminder's scheduled time falls during a daylight-saving-time clock change?
- What happens when an event from a sub-group is visible to a grandparent but the grandparent leaves the parent group?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to authenticate using only their email address, with no password required, via a time-limited link sent to that address
- **FR-002**: System MUST allow any authenticated user to create a household group, making them the sole owner of that group
- **FR-003**: Group owners MUST be able to generate shareable invite links for their group, with optional expiry date and maximum use count
- **FR-004**: System MUST grant household membership to any user who opens a valid, unexpired invite link and completes authentication
- **FR-005**: System MUST allow a single user to be a member of multiple independent household groups simultaneously, with each group's data kept separate
- **FR-006**: System MUST support household groups nested under parent groups, representing multi-generational family structures up to five levels deep
- **FR-007**: System MUST restrict task, shopping, and expense data to members of the owning household only; events and shared reminders MUST be visible to members of all ancestor groups
- **FR-008**: System MUST allow household members to create tasks with a title, optional assignee, and optional standard recurrence rule
- **FR-009**: System MUST allow members to mark a task done or undone; recurring tasks MUST produce the next occurrence when marked done
- **FR-010**: System MUST provide a shared shopping list per household where items can be added, checked, unchecked, and deleted; changes MUST be visible to all household members within 3 seconds
- **FR-011**: System MUST allow household members to create events with a title, date/time, and optional recurrence rule
- **FR-012**: Events MUST roll up to parent groups so that members of ancestor groups can see events from all descendant households in their calendar feed
- **FR-013**: System MUST generate a unique, secret calendar feed URL per user that returns valid iCal data including that user's events and due reminders
- **FR-014**: System MUST allow users to reset their calendar feed URL, invalidating the previous URL immediately
- **FR-015**: System MUST allow members to create personal one-shot reminders with a specific date and time; reminders do not recur; due reminders MUST appear in the user's calendar feed within 10 minutes of the scheduled time
- **FR-016**: System MUST provide an overview dashboard that surfaces, across all the user's groups, items in this priority order: (1) overdue tasks, (2) tasks due today, (3) events today, (4) outstanding shopping item count, (5) upcoming events within 7 days
- **FR-017**: System MUST be installable on a mobile device as a web app and MUST allow core list screens (tasks, shopping) to be viewed when the device is offline
- **FR-018**: System MUST apply accessibility requirements to every screen: fixed bottom-tab navigation, text label on every icon, explicit persistent state feedback, calm low-saturation palette, respect for reduced-motion preference, and adjustable text size and contrast
- **FR-019**: System MUST allow users to store and apply display preferences including text size, contrast mode, and notification batching preference
- **FR-020**: When a group owner leaves a group that has other members, the system MUST automatically promote the longest-standing member to owner without interruption
- **FR-021**: When the sole member of a group (who is also the owner) leaves, the system MUST permanently delete the group and all associated data, after presenting a clear confirmation warning
- **FR-022**: When a member is removed from a household, all tasks assigned to that member MUST have their assignee field cleared; the tasks themselves MUST remain, becoming unassigned

### Key Entities

- **Person**: A registered user who exists independently of any household. Has display name, email, and accessibility preferences (text size, contrast, motion).
- **Group (Household)**: A named node in the family tree. May have a parent group (enabling nesting). The creator becomes its owner. Depth is limited to five levels.
- **Membership**: Links one person to one group with a role of owner or member. A person may hold memberships in multiple independent groups.
- **Invite**: A shareable link carrying a secret token that grants group membership. May carry an expiry date and a maximum use count.
- **Task**: A household-scoped work item with a title, optional recurrence rule, optional assignee, and a binary done/not-done state.
- **Shopping Item**: A household-scoped list entry with a name and a checked/unchecked state, visible and editable by all household members in real time.
- **Event**: A household-scoped happening with a title, date/time, and optional recurrence. Visible to members of the owning group and all ancestor groups.
- **Reminder**: A personal, one-shot timed alert belonging to one person, with a single scheduled date and time. Always fires once. Delivered by appearing in the user's calendar feed.
- **Calendar Feed**: A per-user data export identified by a secret URL, containing that user's events and due reminders in iCal format, consumed by external calendar applications.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can receive a login link, authenticate, create a household, and invite a second member in under 3 minutes
- **SC-002**: A checked shopping item is visible as checked to all household members within 3 seconds on the same network
- **SC-003**: A newly created event appears in a subscribed external calendar within 60 minutes (bounded by the external calendar's own polling interval)
- **SC-004**: A timed reminder appears in the user's calendar feed within 10 minutes of the scheduled time
- **SC-005**: A user belonging to two households sees all relevant data on one dashboard without switching accounts or navigating away
- **SC-006**: A grandparent-group member's calendar feed contains events from all descendant households
- **SC-007**: Core list screens (tasks, shopping) remain usable with no network connection; changes made offline synchronise upon reconnection
- **SC-008**: Every shipped screen passes baseline accessibility checks: fixed navigation, all icons labelled, no red used for non-errors, explicit state confirmations present, reduced-motion preference respected
- **SC-009**: A recurring task that is marked done produces its next occurrence automatically, with the correct next date
- **SC-010**: Resetting a calendar feed URL renders the previous URL non-functional within 60 seconds

## Assumptions

- All users are adults; no minor-specific or guardian-controlled access model is required for the MVP
- All users operate within a single country; one app-level time zone configuration applies throughout (no per-user time zone selection in MVP)
- Users have a personal calendar application (e.g. Google Calendar, Outlook) capable of subscribing to an iCal URL and firing native alerts
- Invite links are shared outside the app (WhatsApp, email, SMS); the app does not provide in-app messaging
- The external calendar application's own polling cadence (typically 15–60 minutes) determines how quickly new events appear after creation; the app cannot control this
- Web Push notifications, food inventory, barcode scanning, expense tracking, and meal planning are explicitly out of scope for this MVP
- The app is for private, non-commercial, extended-family use only
- Two roles are sufficient: owner (group creator, manages membership) and member (all other authenticated household members); no guest or read-only role is needed
- Password-based login is not offered; magic links are the sole authentication method
