# Oolite Key Helper

A second-screen helper for the space game [Oolite](https://oolite.space/). It shows the keyboard shortcuts for whatever you're doing in the game at that moment, and updates as you play.

- **Docked**: station screens, and market, chart or planet-info keys on those screens
- **Flying**: flight, views, targeting, travel and screen keys
- **Near a station**: docking keys, your clearance status (none, requested, granted, timing out, not required) and docking tips
- **Red alert**: combat and escape keys
- **Jump countdown**: seconds left and how to cancel
- **Menu screens in flight**: the keys for that screen

The keys come from **your own game settings**: the game's built-in key config, your keyboard layout, and any keys you've changed in Oolite's Keyboard Configuration screen. If you remap something, the helper shows the new key.

> Status: working and in daily use on Linux with Oolite 1.92.1. Screenshots are coming ([#2](https://github.com/stickleprojects/oolite-helper/issues/2)).

## How it works

```
Oolite + CtxKeys.oxp ──JSON lines──▶ Latest.log ──follow──▶ helper window (Python/Tk)
  (game events)                                              (keys for the current context)
```

1. **[oxp/CtxKeys.oxp](oxp/CtxKeys.oxp)** is an Oolite add-on. Its world script listens for game events (docking, station aegis, alert level, docking clearance, jump countdowns, screen and view changes). It writes each event to the game log as a JSON line, e.g. `[ctxkeys]: {"type":"aegis","inside":true,...}`.
2. **[helper/](helper/)** follows `Latest.log`, works out the current context and draws the matching key list. The window has no title bar, sits on a second screen and never takes focus from the game.
3. On startup the helper reads the key bindings and the game's own key descriptions from the AppImage. It caches them until the AppImage changes, then applies your layout and key changes from the game's settings.

A later version may receive the same messages over Oolite's debug console connection instead of the log. That would allow live data for a fuller HUD, as [oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge) does.

## Requirements

- Linux with X11 (developed on MATE)
- Oolite 1.92.1 Linux AppImage
- Python 3.10+ with Tkinter (`sudo apt install python3-tk` on Debian/Ubuntu)
- A second screen, or room for the window somewhere

## Setup

```bash
git clone https://github.com/stickleprojects/oolite-helper.git
cd oolite-helper

# 1. Python venv for the helper
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. Install the add-on into the game's AddOns folder (a symlink, so updates are live)
mkdir -p ~/Games/Oolite/GameData/AddOns
ln -s "$PWD/oxp/CtxKeys.oxp" ~/Games/Oolite/GameData/AddOns/CtxKeys.oxp
```

The paths above assume the AppImage is at `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`. If yours is elsewhere, set these variables (both the launcher and the helper read them):

| Variable | Default |
|---|---|
| `OOLITE_APPIMAGE` | `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage` |
| `OOLITE_GAMEDATA` | `GameData/` next to the AppImage |

## Running

Start the game with the launcher:

```bash
scripts/launch-oolite.sh
```

It starts the helper too, and the helper closes itself when the game exits. Point your desktop shortcut at this script. Set `OOLITE_NO_HELPER=1` to start only the game.

To run the helper on its own:

```bash
.venv/bin/oolite-helper [--geometry WxH+X+Y] [--stay]
```

- `--geometry`: window size and position. The default, `1920x1080+960+1080`, is a 1920x1080 screen below a 3840-wide main screen. Use `xrandr` to find your screen's position.
- `--stay`: keep the window open when the game exits.
- Right-click the window to close it.

### Why the launcher?

On some systems the 1.92.1 AppImage's own start-up script fails: its bundled `libsystemd` breaks the host's `mkdir` and `mktemp`. Oolite then logs to stdout (no `Latest.log`) and puts its settings in `~/GNUstep`. The launcher works around this. It runs the AppImage in "legacy" mode, sets Oolite's `OO_*` folder variables, and writes a GNUstep config, so everything (log, add-ons, saves, settings) lives in `GameData/` next to the AppImage.

## Project layout

| Path | What |
|---|---|
| `oxp/CtxKeys.oxp/` | The Oolite add-on (world script + manifest) |
| `helper/app.py` | The window |
| `helper/sources.py` | Follows `Latest.log`, including log rotation at game start |
| `helper/state.py` | Turns messages into game state and a context |
| `helper/contexts.py` | Which actions to show per context, and tips |
| `helper/keys.py`, `helper/plist.py` | Reads Oolite's key config and descriptions |
| `scripts/launch-oolite.sh` | Game launcher that fixes the data folders and starts the helper |

## Credits

- [Oolite](https://oolite.space/) and its contributors. Key descriptions shown in the helper come from the game's own files.
- [oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge), for the idea of getting game state out through an add-on.
