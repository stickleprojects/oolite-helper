# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A context-aware keyboard-shortcut helper for the space game Oolite. Two parts:

1. **OXP add-on** (JavaScript world script): listens for game events and writes marker lines such as `log("ctxkeys", "CONTEXT: near_station")` to Oolite's log. Add-on scripts can't write files or use the network, so the log is the only channel out.
2. **Python helper window**: follows `Latest.log` (including when it is recreated at game start), tracks the current context and shows the matching key list in a large font on the laptop screen, without taking focus from the game.

The full brief is in [PROMPT.md](PROMPT.md). Read it before making design changes.

## Environment

- Oolite 1.92.1 AppImage: `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`
- Linux, MATE, X11. Intel integrated graphics.
- Game screen: DP-2, 3840x1080 at +0+0. Helper window screen: eDP-1, 1920x1080 at +960+1080.
- Oolite user data (log, AddOns) does not exist until the game has been run once. Expected under `~/.Oolite/`, but check.

## Rules

- **Key bindings come from the game's files, never from memory.** Extract the AppImage (`--appimage-extract`) into a scratch folder, not into this repo, then read `keyconfig*.plist` and any user overrides.
- **Check event handler names against the 1.92 scripting API** before relying on them (`shipEnteredStationAegis`, `guiScreenChanged`, `alertConditionChanged` and so on).
- **Build in small, verified steps:** (1) confirm an add-on log line appears in `Latest.log`, perhaps after a logcontrol change; (2) the window that follows the log; (3) the key lists.
- Don't commit extracted AppImage contents, game logs or save files.
