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

  `_emit` should prefer `debugConsole` when it exists and fall back to `log()`.

### Steps

1. ✅ Launcher fix and data folders (see Environment).
2. ⏳ Minimal add-on: confirm that `[ctxkeys]` lines appear in `Latest.log`.
3. Helper window that follows the log. It should read messages through an interface that a TCP source can implement later.
4. Key lists generated from `keyconfig*.plist` and any user overrides.
5. The full set of contexts: docked, flying, near station, red alert, hyperspace/galactic jump, menu screens.
6. Later: the HUD panels, on top of phase 2.

### Event handlers

All of these are confirmed present in the 1.92.1 binary: `startUp`, `startUpComplete`, `shipEnteredStationAegis`, `shipExitedStationAegis`, `shipDockedWithStation`, `shipWillLaunchFromStation`, `shipLaunchedFromStation`, `alertConditionChanged`, `shipWillEnterWitchspace`, `shipWillExitWitchspace`, `shipExitedWitchspace`, `shipTargetAcquired`, `shipTargetLost`, `shipTargetDestroyed`, `guiScreenWillChange`, `guiScreenChanged`, `playerStartedJumpCountdown`, `playerCancelledJumpCountdown`, `playerJumpFailed`, `shipEnteredPlanetaryVicinity`, `shipExitedPlanetaryVicinity`, `playerStartedAutoPilot`, `playerCancelledAutoPilot`, `playerRequestedDockingClearance`, `playerDockingClearanceGranted`, `missionScreenOpportunity`.

## Environment

- Oolite 1.92.1 AppImage: `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`
- Linux, MATE, X11. Intel integrated graphics.
- Game screen: DP-2, 3840x1080 at +0+0. Helper window screen: eDP-1, 1920x1080 at +960+1080.
- **Always launch the game with [scripts/launch-oolite.sh](scripts/launch-oolite.sh)** (the desktop icon points to it). Started directly, the AppImage's AppRun breaks: its bundled libsystemd stops the host's `mkdir`/`mktemp` working, so the log goes to stdout and settings go to `~/GNUstep`. The script uses `OO_DIRTYPE=legacy`, sets the `OO_*` folder variables and writes a `GNUstep.conf` (mode 600, or GNUstep ignores it).
- All game data lives in `~/Games/Oolite/GameData/`:
  - `Logs/Latest.log`: the log the helper follows
  - `AddOns/CtxKeys.oxp`: a symlink to [oxp/CtxKeys.oxp](oxp/CtxKeys.oxp), so edits in the repo are live on the next game start
  - `SavedGames/`, `Settings/` (GNUstep defaults, `OoliteDefaults.plist`), `Library/Caches/`
- Extracted AppImage (scratch only): `Resources/Config/keyconfig.plist`, `keyconfig2.plist`, `logcontrol.plist` under `usr/bin/`.

## Rules

- **Key bindings come from the game's files, never from memory.** Extract the AppImage (`--appimage-extract`) into a scratch folder, not into this repo, then read `keyconfig*.plist` and any user overrides (check `Settings/OoliteDefaults.plist`).
- **Build in small, verified steps.** The game has to be run by Kieron, so ask them to run it and then check the log.
- Don't commit extracted AppImage contents, game logs or save files.
