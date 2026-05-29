# Project Instructions

These rules override all implementation decisions.

## Think Before Coding

Don't assume. Surface tradeoffs. Ask rather than guess when uncertain.
- State assumptions explicitly
- Present multiple interpretations — don't pick silently when ambiguity exists
- Push back when simpler approach exists
- Stop when confused — name what's unclear, ask

## Test-Driven Development

Write test before feature. No production code without test written first.

## Simplicity First — No Speculative Code

Write minimum viable code for immediate problem. Features added when required, not anticipated. Each module does one thing well.
- No abstractions for single-use code
- No unrequested "flexibility" or "configurability"
- No error handling for impossible scenarios
- If 200 lines could be 50, rewrite it

## Surgical Changes

Change only what task requires. Don't improve adjacent code, comments, or formatting. Match existing style.
- Orphaned imports/variables/functions from changes — remove them
- Unrelated dead code noticed — mention it, don't delete it

## Goal-Driven Execution

Define success criteria before writing code:

| Instead of… | Do… |
|---|---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

Multi-step tasks: state brief plan `[Step] → verify: [check]`.

## No Hard-Coding — Config Over Constants

Values changeable between environments live in config files — never inline. Includes URLs, thresholds, timeouts, feature flags, credentials.

## No Global Variables

State and behaviour belong inside objects that own them. No global variables — ever. Expose only what callers need; hide everything else.

## Explicit Over Implicit

Avoid magic, clever one-liners, or non-obvious side effects. Future reader should never guess what code does or why.

## Consistent Formatting and Naming

Follow existing conventions (casing, file structure, naming, import ordering) without exception. Names describe what something *represents*, not what it *does mechanically*. Don't introduce new patterns without discussion.

## Fail Fast and Fail Loudly

Validate inputs early. Raise clear descriptive errors — never silently continue into undefined state.

## Minimal Dependencies

Add external library only when it solves real recurring problem not worth owning. Every dep = maintenance surface + security exposure. Prefer standard library; justify every addition.

## Comment the Why, Not the What

Always explain *why* a decision was made, especially non-obvious ones. Includes tradeoffs, workarounds, constraints. Never reverse-engineer intent from behaviour.
