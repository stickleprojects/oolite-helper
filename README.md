# Oolite Key Helper

A small always-visible window that shows the Oolite keyboard shortcuts for what you're doing in the game right now: docked, flying, near a station, in combat, jumping, or on a menu screen.

> Status: early development. The launcher and the first add-on are in place; the helper window is next. The plan is in [CLAUDE.md](CLAUDE.md).

## How it works

```
Oolite ──(OXP world script)──▶ Latest.log ──(tail)──▶ Python helper window
          JSON messages          (later: debug console TCP)   shows keys for context
```

- **[oxp/CtxKeys.oxp](oxp/CtxKeys.oxp)**: an Oolite add-on whose world script sends a JSON message whenever the game state changes (station aegis, docking, alert level, witchspace, target, GUI screen).
- **`helper/`** (planned): a Python app that follows `Latest.log`, works out the current context and displays the matching key list. It opens on a second screen and doesn't steal focus from the game.
- **Later**: switching to Oolite's test build lets the helper receive messages over the debug console TCP protocol instead. That allows live data for a fuller HUD, in the way [oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge) does.
- The key lists are generated from the game's own `keyconfig*.plist` files and any user overrides, so they match your real bindings.

## Contexts

| Context | Example keys shown |
|---|---|
| Docked | trading, shipyard, launch |
| Flying | normal flight controls |
| Near station | docking clearance, docking computer |
| Red alert | weapons, targeting, missiles |
| Hyperspace / galactic jump | jump controls |
| Menu screens | keys for the current screen |

## Requirements

- Oolite 1.92.1 (tested with the Linux AppImage)
- Python 3 with Tkinter or GTK
- An X11 desktop (developed on MATE)

## Install and run

1. Start Oolite with [scripts/launch-oolite.sh](scripts/launch-oolite.sh). This works around the AppImage's broken data folder setup, and keeps all game data in `GameData/` next to the AppImage.
2. Link the add-on into the game:
   ```
   ln -s "$PWD/oxp/CtxKeys.oxp" ~/Games/Oolite/GameData/AddOns/CtxKeys.oxp
   ```
3. Set up the helper in a venv (once). Tkinter comes from the system Python (`sudo apt install python3-tk` if it's missing):
   ```
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```
4. Run the helper, before or after starting the game:
   ```
   .venv/bin/oolite-helper
   ```
   It opens full-size on the laptop screen (`--geometry 1920x1080+960+1080` by default) and never takes focus from the game. Right-click it to close.
