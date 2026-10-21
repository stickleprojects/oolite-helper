# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A context-aware keyboard-shortcut helper for the space game Oolite. Two parts:

1. **OXP add-on** (JavaScript world script): listens for game events and writes marker lines such as `log("ctxkeys", "CONTEXT: near_station")` to Oolite's log. Add-on scripts can't write files or use the network, so the log is the only channel out.
2. **Python helper window**: follows `Latest.log` (including when it is recreated at game start), tracks the current context and shows the matching key list in a large font on the laptop screen, without taking focus from the game.

The full brief is in [PROMPT.md](PROMPT.md). Read it before making design changes.

## Future direction

If the key helper works out, it may grow into a fuller HUD with extra game info (for example ship status, target details or system data). Design so that's easy to add:

- Log messages are tagged JSON lines, e.g. `CTXKEYS {"type":"context","value":"near_station"}`, so new message types can be added without changing the parser.
- The window is made of panels. The key list is just the first one.
- The log only suits event-driven or low-rate updates (around once a second at most), because every message stays in `Latest.log`.

## Environment

- Oolite 1.92.1 AppImage: `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`
- Linux, MATE, X11. Intel integrated graphics.
- Game screen: DP-2, 3840x1080 at +0+0. Helper window screen: eDP-1, 1920x1080 at +960+1080.
- **Always launch the game with [scripts/launch-oolite.sh](scripts/launch-oolite.sh)** (the desktop icon points to it). Started directly, the AppImage's AppRun breaks: its bundled libsystemd stops the host's `mkdir`/`mktemp` working, so the log goes to stdout and settings go to `~/GNUstep`. The script uses `OO_DIRTYPE=legacy`, sets the `OO_*` folder variables and writes a `GNUstep.conf` (mode 600, or GNUstep ignores it).
- All game data lives in `~/Games/Oolite/GameData/`:
  - `Logs/Latest.log`: the log the helper follows
  - `AddOns/`: where our OXP goes
  - `SavedGames/`, `Settings/` (GNUstep defaults, `OoliteDefaults.plist`), `Library/Caches/`
- Extracted AppImage (scratch only): `Resources/Config/keyconfig.plist`, `keyconfig2.plist`, `logcontrol.plist` under `usr/bin/`.

## Rules

- **Key bindings come from the game's files, never from memory.** Extract the AppImage (`--appimage-extract`) into a scratch folder, not into this repo, then read `keyconfig*.plist` and any user overrides.
- **Check event handler names against the 1.92 scripting API** before relying on them (`shipEnteredStationAegis`, `guiScreenChanged`, `alertConditionChanged` and so on).
- **Build in small, verified steps:** (1) confirm an add-on log line appears in `Latest.log`, perhaps after a logcontrol change; (2) the window that follows the log; (3) the key lists.
- Don't commit extracted AppImage contents, game logs or save files.
