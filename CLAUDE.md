# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A context-aware keyboard-shortcut helper for the space game Oolite, which may later grow into a fuller HUD. Two parts:

1. **OXP add-on** [oxp/CtxKeys.oxp/](oxp/CtxKeys.oxp/): a JavaScript world script that listens for game events and sends JSON messages out of the game.
2. **Python helper window**: receives those messages, tracks the current context and shows the matching key list in a large font on the laptop screen, without taking focus from the game.

The original brief is in [PROMPT.md](PROMPT.md). The plan below replaces its "Planned approach" where they differ.

## Plan

### Getting messages out of the game

Each message is a JSON object with a `type` field, e.g. `{"type":"gui","to":"GUI_SCREEN_STATUS","from":"GUI_SCREEN_MAIN"}`. All sending goes through `this._emit()` in the world script, so the way messages are carried can change without touching the event handlers.

- **Phase 1, the log (now).** `_emit` calls `log("ctxkeys", json)`. That writes `HH:MM:SS.mmm [ctxkeys]: {json}` to `Latest.log`, and the helper follows the file (which is recreated at each game start). This works with the normal release AppImage. No logcontrol change is needed, because `_default = yes` shows custom log classes. It only suits event-driven or slow updates (about 1/s at most).
- **Phase 2, the debug console (for the HUD).** Switch to `oolite_test-1.92.1-x86_64.AppImage` from the official 1.92.1 GitHub release, which has `debug_functionality_support`. The helper listens on TCP `127.0.0.1:8563`; Oolite connects to it, and `_emit` sends messages with `debugConsole.consoleMessage(json)`. This supports updates at around 10/s and two-way queries. Prior art:
  - [maikschulz/oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge): the same pattern, with a Node server and the framing of the message packets (4-byte big-endian length, then a plist packet).
  - [OoliteProject/oolite-debug-console](https://github.com/OoliteProject/oolite-debug-console): the reference Python implementation of the protocol.

  `_emit` already prefers `debugConsole` when it exists and falls back to `log()`.

  Upstream may make the test build unnecessary: OoliteProject/oolite PR #756 enables the debug console in release builds, and our feature request OoliteProject/oolite#770 asks for a proper read-only telemetry feed.

### Steps

1. ✅ Launcher fix and data folders (see Environment).
2. ✅ Minimal add-on: `[ctxkeys]` lines appear in `Latest.log`.
3. ✅ Helper window that follows the log ([helper/](helper/)). `sources.LogSource.poll()` is the interface a TCP source will implement later; `state.GameState` turns messages into a context.
4. ✅ Key lists. On startup, [helper/keys.py](helper/keys.py) extracts `keyconfig2.plist` and `descriptions.plist` from the AppImage into `~/.cache/oolite-helper/` (refreshed when the AppImage changes). It then applies the `keyboard-code` layout and `KeyConfigOverrides` from `Settings/OoliteDefaults.plist`. [helper/plist.py](helper/plist.py) parses the OpenStep plists. [helper/contexts.py](helper/contexts.py) lists only action names per context; keys and wording always come from the files.
5. ✅ Near station, red alert and jump countdown (aegis, alert, clearance with a 1 s check for `TIMING_OUT`, autopilot and countdown events). Verified in play. Precedence in `GameState.context`: docked > menu > jump countdown > red alert > near station > flying.
6. ✅ Tests and CI (#6): fake game (`tests/fakegame.py`, `scenarios/`), fake Oolite (`tests/oxp/`), pytest suite, and CI with required checks. The code review is on #12; follow-ups #26 (key remaps, high) and #27 (robustness).
7. ⏳ Trade advisor (#17): add-on market/trade/systems/chart messages (#18, done); market memory (#19); interactive trade browser (#20); chart advice (#21).
8. Later: HUD panels, on top of phase 2.

### Game facts checked in the 1.92.1 source

These are cited in `contexts.py` TIPS/ACTION_NOTES:
- The docking clearance key asks the **primary target** (`performDockingRequest:primeTarget`), so the station must be targeted first. Some stations don't require clearance (`requiresDockingClearance`).
- Pressing the hyperspace key during a countdown cancels it.
- `key_docking_music` shares `s` with decrease thrust; it's only read in `pollAutopilotControls`, i.e. while the docking computer is on.
- Properties: `player.alertCondition`, `player.dockingClearanceStatus`, `player.ship.withinStationAegis`, `player.ship.viewDirection`, `station.requiresDockingClearance`; for trading, `station.market`, `player.ship.manifest.list`, `systemInfo.samplePrice()`, `galaxyNumber`, `clock.seconds`.
- **In-game key remaps** are saved in `KeyConfigOverrides` with a **numeric `key`** and `shift`/`mod1`/`mod2` as `1`/`0` (e.g. `key = 34; mod1 = 1;` is Ctrl+`"`). Codes: < 256 = character; 256–266 F1–F11; 267–270 Right/Left/Down/Up; 271 Pause; 272 Print Screen; 303–309 Home/End/Insert/Delete/PgUp/PgDn/Backspace; 310–326 numpad (`src/SDL/MyOpenGLView.h`). The helper doesn't handle this yet: #26.
- The highlighted market row (`marketSelectedCommodity`) is **not** exposed to scripts.
- `shipEnteredStationAegis`/`shipExitedStationAegis` fire **before** `checkForAegis` updates the status, so `player.ship.withinStationAegis` still has the old value during those events.
- The market buys and sells with `key_gui_arrow_right`/`left` (Shift = all); `key_market_buy_one`/`buy_max`/`sell_*` are loaded but never read when trading.

### Event handlers

All of these are confirmed present in the 1.92.1 binary: `startUp`, `startUpComplete`, `shipEnteredStationAegis`, `shipExitedStationAegis`, `shipDockedWithStation`, `shipWillLaunchFromStation`, `shipLaunchedFromStation`, `alertConditionChanged`, `shipWillEnterWitchspace`, `shipWillExitWitchspace`, `shipExitedWitchspace`, `shipScoopedFuel`, `shipTargetAcquired`, `shipTargetLost`, `shipTargetDestroyed`, `guiScreenWillChange`, `guiScreenChanged`, `infoSystemChanged`, `playerBoughtCargo`, `playerSoldCargo`, `playerStartedJumpCountdown`, `playerCancelledJumpCountdown`, `playerJumpFailed`, `shipEnteredPlanetaryVicinity`, `shipExitedPlanetaryVicinity`, `playerStartedAutoPilot`, `playerCancelledAutoPilot`, `playerRequestedDockingClearance`, `playerDockingClearanceGranted`, `missionScreenOpportunity`. Also `shipDied(whom, damageType)`, checked in the source: the player fires it from `getDestroyedBy:` via `noteKilledBy:`, and after the game-over screen (Space, or 30 s) the last save reloads, which runs `startUp` again.

## Environment

- Oolite 1.92.1 AppImage: `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`
- Linux, MATE, X11. Intel integrated graphics.
- Game screen: DP-2, 3840x1080 at +0+0. Helper window screen: eDP-1, 1920x1080 at +960+1080 (the default: first non-primary monitor). Placement is configurable via `~/.config/oolite-helper/config.toml` ([config.example.toml](config.example.toml)) or CLI flags; see `helper/screen.py`.
- **Always launch the game with [scripts/launch-oolite.sh](scripts/launch-oolite.sh)** (the desktop icon points to it). Started directly, the AppImage's AppRun breaks: its bundled libsystemd stops the host's `mkdir`/`mktemp` working, so the log goes to stdout and settings go to `~/GNUstep`. The script uses `OO_DIRTYPE=legacy`, sets the `OO_*` folder variables and writes a `GNUstep.conf` (mode 600, or GNUstep ignores it).
- All game data lives in `~/Games/Oolite/GameData/`:
  - `Logs/Latest.log`: the log the helper follows
  - `AddOns/CtxKeys.oxp`: a symlink to [oxp/CtxKeys.oxp](oxp/CtxKeys.oxp), so edits in the repo are live on the next game start
  - `SavedGames/`, `Settings/` (GNUstep defaults, `OoliteDefaults.plist`), `Library/Caches/`
- Extracted AppImage (scratch only): `Resources/Config/keyconfig.plist`, `keyconfig2.plist`, `logcontrol.plist` under `usr/bin/`.

## Launching from Claude Code

Run these from the repo root. VS Code is a snap, so anything it starts (including Claude's shell) can't mount the AppImage over FUSE. Start the game and the helper as user systemd units instead, with the sandbox disabled:

```
systemd-run --user --unit=oolite-game --collect --setenv=DISPLAY=$DISPLAY --setenv=XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority} "$PWD/scripts/launch-oolite.sh"
systemd-run --user --unit=oolite-helper --collect --setenv=DISPLAY=$DISPLAY --setenv=XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority} "$PWD/.venv/bin/oolite-helper"
```

Stop them with `systemctl --user stop oolite-helper` (or `oolite-game`). To check the helper's display, run `scrot -a 960,1080,1920,1080 -o <file>`.

## Rules

- **Python runs from the project venv**, `.venv/` (gitignored, built from the system Python for Tkinter). Install with `.venv/bin/pip install -e ".[dev]"`, run with `.venv/bin/oolite-helper`, and add any dependencies to `pyproject.toml`.
- **The repo is on NTFS (`core.fileMode=false`)**, so git never records the executable bit. For a script that must be executable, run `git update-index --chmod=+x <file>`.

- **Key bindings come from the game's files, never from memory.** Extract the AppImage (`--appimage-extract`) into a scratch folder, not into this repo, then read `keyconfig*.plist` and any user overrides (check `Settings/OoliteDefaults.plist`).
- **Build in small, verified steps.** The game has to be run by Kieron, so ask them to run it and then check the log.
- Don't commit extracted AppImage contents, game logs or save files.

## Git workflow

- **Never commit to `main`.** It's protected for everyone, admins included: changes go in only through pull requests, with no force-pushes. Start each change on a branch from an up-to-date `main` (`feat/…`, `fix/…`, `docs/…`, `chore/…`), push it, and open a PR with `gh pr create`. Reference issues with `Closes #N`.
- Kieron merges PRs (0 approvals are required), or tells Claude to. After a merge: `git checkout main && git pull --ff-only && git fetch --prune`, then delete the local branch.
- Commits use the noreply address set in this repo's git config, so don't change `user.email`.
- **CI is required** (`.github/workflows/ci.yml`): 7 checks (Python 3.11/3.12/3.13, Lint, Add-on Node 20/22, Shell), and **strict**, so a PR must be up to date with `main`. Run the same checks locally before pushing (see CONTRIBUTING.md).
- If `gh pr merge` fails with "part of a stack", use `gh api -X PUT repos/stickleprojects/oolite-helper/pulls/N/merge-async -f merge_method=squash -f merge_action=direct_merge`, then poll `.../merge-async/<details.uuid>` until `merged`.

## Working with Copilot

Some issues are assigned to GitHub Copilot's coding agent (`.github/copilot-instructions.md` and `copilot-setup-steps.yml` set it up). Copilot credits are limited, so Claude does most new work.
- Assign through GraphQL `replaceActorsForAssignable` with the `copilot-swe-agent` bot id from `suggestedActors`. Assign a dependent issue only after **verifying** its blocker's PR shows MERGED, because Copilot branches from `main` immediately.
- Put scope guidance in the **issue** before assigning. Never `@copilot` on a PR still marked [WIP]: it creates a stacked sub-PR. Send one batched review per finished PR; push small fixes yourself.
- Review every Copilot PR **after merging `main` into it locally**, running all checks, and checking the API use against the 1.92.1 source. Copilot doesn't know `ruff.toml`, so `ruff check --fix` usually needs pushing to its branch.
