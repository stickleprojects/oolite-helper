# Oolite Key Helper

A small always-visible window that shows the Oolite keyboard shortcuts for what you're doing in the game right now: docked, flying, near a station, in combat, jumping, or on a menu screen.

> Status: planning. Nothing is built yet. See [PROMPT.md](PROMPT.md) for the full brief.

## How it works

```
Oolite ──(OXP world script)──▶ Latest.log ──(tail)──▶ Python helper window
          writes "CONTEXT: x"                          shows keys for x
```

- **`oxp/`** (planned): an Oolite add-on whose world script logs a `CONTEXT:` line whenever the game state changes (station aegis, docking, alert level, witchspace, target, GUI screen).
- **`helper/`** (planned): a Python app that follows `~/.Oolite/Logs/Latest.log`, works out the current context and displays the matching key list. It opens on a second screen and doesn't steal focus from the game.
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

To follow once the first version is built.
