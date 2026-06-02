<!--
SYNC IMPACT REPORT
==================
Version change: [NEW] → 1.0.0 (initial ratification)

Modified principles: none (first adoption)

Added sections:
  - Core Principles (12 principles)
  - Project Constraints (serverless, accessibility, hosting)
  - Development Workflow
  - Governance

Removed sections: none

Templates reviewed:
  - .specify/templates/plan-template.md    ✅ Constitution Check section is dynamic — no change needed
  - .specify/templates/spec-template.md    ✅ User story + acceptance scenario structure aligns with TDD principle
  - .specify/templates/tasks-template.md   ✅ TDD note and phase ordering align with principles 2, 4, 5

Follow-up TODOs:
  - None — all fields resolved from user input and MASTERPLAN.md
-->

# Household Manager Constitution

## Core Principles

### I. Think Before Coding

Before writing any code, state assumptions explicitly. When ambiguity exists, present multiple
interpretations and ask — do not pick silently. Push back when a simpler approach exists.
Stop when confused: name what is unclear, then ask.

**MUST**: Surface tradeoffs before implementation decisions.
**MUST NOT**: Assume intent when two valid interpretations exist.

### II. Test-Driven Development

Tests are written before production code. No feature, fix, or refactor ships without a test
written first that describes the expected behaviour. Red → Green → Refactor. No exceptions.

**MUST**: Write failing test before writing implementation.
**MUST NOT**: Write production code to fix behaviour not yet described by a test.

### III. Simplicity First — No Speculative Code

Write the minimum viable code for the immediate problem. Modules do one thing well. Features
are added when required, not anticipated.

- No abstractions for single-use code.
- No unrequested "flexibility" or "configurability".
- No error handling for scenarios that cannot occur.
- If 200 lines could be 50, rewrite it.

**MUST**: Justify every abstraction with a present, concrete use case.
**MUST NOT**: Add configurability, hooks, or extension points unless explicitly requested.

### IV. Surgical Changes

Change only what the task requires. Adjacent code, comments, and formatting are left untouched.
Match existing style in the file being edited.

- Orphaned imports, variables, or functions created by the change: remove them.
- Unrelated dead code noticed during work: mention it, do not delete it.

**MUST**: Scope changes to the stated task.
**MUST NOT**: Refactor, reformat, or "improve" code not touched by the task.

### V. Goal-Driven Execution

Define success criteria before writing code. Multi-step tasks state a brief plan with
verification step per stage.

| Instead of… | Do… |
|---|---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

**MUST**: State `[Step] → verify: [check]` for multi-step tasks.
**MUST NOT**: Begin implementation before success criteria are defined.

### VI. No Hard-Coding — Config Over Constants

Values that differ between environments live in config files, never inlined. This includes
URLs, thresholds, timeouts, feature flags, credentials, and environment-specific constants.

**MUST**: Externalise environment-dependent values to config.
**MUST NOT**: Hardcode production URLs, secrets, or tunable thresholds in source code.

### VII. No Global Variables

State and behaviour belong inside the objects that own them. Global variables are never used.
Expose only what callers need; hide everything else.

**MUST**: Encapsulate state within its owning scope.
**MUST NOT**: Introduce module-level mutable state or global singletons.

### VIII. Explicit Over Implicit

Avoid magic, clever one-liners, or non-obvious side effects. A future reader must never
need to guess what code does or why. Prefer verbose clarity over terse cleverness.

**MUST**: Make control flow, state mutations, and side effects visible at the call site.
**MUST NOT**: Use hidden conventions, framework magic, or implicit side effects without
documentation of why they are unavoidable.

### IX. Consistent Formatting and Naming

Follow existing conventions without exception: casing, file structure, naming, import ordering.
Names describe what something *represents*, not what it *does mechanically*. New patterns are not
introduced without discussion.

**MUST**: Match the naming and formatting style present in the file being edited.
**MUST NOT**: Introduce new structural patterns or naming conventions unilaterally.

### X. Fail Fast and Fail Loudly

Validate inputs early. Raise clear, descriptive errors — never silently continue into undefined
state. Error messages include enough context to debug: parameters, response body, status codes.

**MUST**: Validate at system boundaries (user input, external APIs) and raise specific errors.
**MUST NOT**: Swallow exceptions, use catch-all handlers, or allow invalid state to propagate.

### XI. Minimal Dependencies

Add an external library only when it solves a real, recurring problem not worth owning.
Every dependency is a maintenance surface and a security exposure. Prefer the standard library.
Every addition must be justified.

**MUST**: Justify each new dependency with a documented reason.
**MUST NOT**: Add dependencies speculatively or for convenience when the standard library suffices.

### XII. Comment the Why, Not the What

Always explain *why* a decision was made, especially non-obvious ones. This includes tradeoffs,
workarounds, and constraints. Well-named identifiers document the what; comments document
the why. Never reverse-engineer intent from behaviour.

**MUST**: Document non-obvious decisions with their rationale inline.
**MUST NOT**: Write comments that restate what the code already makes clear.

## Project Constraints

These constraints are derived from the Household Manager architecture and are non-negotiable
for the lifetime of this project.

**Serverless & stateless** — All persistence lives in Supabase. No on-disk SQLite, no
in-memory state between requests, no long-lived DB connections, no in-process background workers.
Reach Postgres exclusively through the Supabase connection pooler.

**Free-tier hard constraint** — Vercel Hobby and Supabase free tier are permanent constraints.
Vercel free cron runs once per day; timed reminders MUST use an external scheduler (cron-job.org)
hitting `GET /jobs/tick`. Do not depend on sub-daily Vercel cron.

**Bundle lean** — Python bundle MUST stay under 500 MB. Heavy ML or data-science libs are
prohibited. Every added dependency is reviewed against this constraint.

**Notifications via iCal** — The app does not deliver push notifications directly. All
alerting flows through the per-user `.ics` feed subscribed by Google/Outlook. Web Push is
Android-only optional enhancement, never primary.

**Accessibility is a build constraint** — Calm palette, fixed navigation, labeled icons,
explicit state, `prefers-reduced-motion` respected, and passwordless login (magic links)
are day-one requirements applied to every shipped screen, not post-ship polish.

**Privacy by structure** — Operational data (tasks, shopping, inventory, expenses) stays local
to the owning household. Only event/reminder rollup crosses household boundaries up the
group tree. RLS enforces this in Postgres.

## Development Workflow

**Phase gate** — Each phase (Foundation → Daily Drivers → Calendar) MUST be verified as
working end-to-end before the next phase begins. Do not carry forward unverified code.

**Vertical slices** — Each task is a vertical slice: model → service → endpoint → test,
all committed together. Partial implementations that cannot be verified are not merged.

**Recursive CTE for group tree** — The `WITH RECURSIVE` query is the sole mechanism for
traversing the group hierarchy. Closure tables and nested sets are prohibited — complexity
cost exceeds benefit at the scale of this application.

**RRULE for recurrence** — All recurring chores and events use iCal RRULE. No custom
recurrence format. Python libs: `python-dateutil` / `recurring-ical-events`.

**Timezone handling** — All timestamps stored in UTC. Render in single app-configured local
timezone. Compute `fire_at` from wall-clock time using IANA timezone via `zoneinfo` to
handle DST automatically. Never hardcode a fixed UTC offset.

**iCal feed security** — Per-user unguessable feed URL with rotate-on-demand. Secret lives
in the URL itself (calendar apps cannot send auth headers). Provide "reset feed URL" action.

## Governance

This constitution supersedes all other practice documents and implementation preferences.

**Amendment procedure**:
1. Propose change with rationale and impact assessment.
2. Update this file, increment version per semantic versioning policy.
3. Propagate changes to affected templates and runtime guidance.
4. Record the amendment in the Sync Impact Report at the top of this file.

**Versioning policy**:
- MAJOR: Backward-incompatible principle removal or redefinition.
- MINOR: New principle or section added, or materially expanded guidance.
- PATCH: Clarifications, wording fixes, non-semantic refinements.

**Compliance**:
- Every PR/review MUST verify that the implementation aligns with the principles above.
- Complexity violations MUST be documented in the plan's Complexity Tracking table with
  explicit justification and rejected simpler alternatives.
- Runtime development guidance lives in `specs/[feature]/plan.md` per feature.

**Version**: 1.0.0 | **Ratified**: 2026-06-02 | **Last Amended**: 2026-06-02
