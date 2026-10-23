---
name: oolite-773
description: Coordinate the OoliteProject/oolite#773 fix (window frame/focus after the splash, without breaking #555 centring) by dispatching the oolite-773-* subagents in order and resuming from ~/oolite-773/STATUS.md. Use when Kieron types /oolite-773 or asks to continue the #773 work.
---
# Coordinate the #773 fix

You are the coordinator. Do no technical work yourself: dispatch the subagents, read their short reports, and keep Kieron informed in 1 to 3 lines per step. This session should run on Sonnet (`/model sonnet`); the subagents choose their own models.

Kieron is on the Pro plan, so keep replies short, and stop at each checkpoint so he can continue in a fresh session if he's near his limit.

## Resume
Read `~/oolite-773/STATUS.md` (if it exists) and continue from the first step that isn't done.

## Steps
1. **Harness:** dispatch `oolite-773-harness`.
   **Checkpoint A:** tell Kieron whether stock 1.93 reproduces the bug in the container, and in which mode. If it doesn't reproduce in either mode, stop and ask how to proceed.
2. **Baseline:** dispatch `oolite-773-tester` with `~/oolite-773/appimages/stock.AppImage`, label `stock`.
3. **Option 1:** dispatch `oolite-773-fixdev` with "option 1", then `oolite-773-tester` with `opt1.AppImage`, label `opt1`.
   **Checkpoint B:** show the stock and opt1 tables side by side.
   - If opt1 has frame=no at 0 and is centred on every window manager where stock was centred, recommend opt1 and go to step 5 (skip 4).
   - Otherwise say which window manager breaks and go to step 4.
4. **Option 2,** then **option 3** if 2 fails: fixdev, then tester for each. **Checkpoint C:** compare and recommend.
5. **Write-up:** dispatch `oolite-773-writer` for the chosen option.
   **Checkpoint D:** give Kieron the paths to `pr-description.md`, `comment-773.md` and the patch.

## Rules
- Never install anything on the host; it all runs in Docker.
- **Ask Kieron before** forking OoliteProject/oolite, pushing, opening the PR or commenting on GitHub. Each needs its own yes.
- If an agent reports it's blocked, don't retry it more than once; tell Kieron.
- After each step, check the agent appended to STATUS.md; if not, append the step's outcome yourself, in one line.
