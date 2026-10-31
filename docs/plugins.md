# Writing a plugin

A plugin is a small web page (HTML, CSS and JavaScript) that the helper shows in a window of its own, docked to the game or anywhere on a monitor, like the helper's other widgets. It reads the game's state through a few named **topics**, and can change the helper's shared selections (the tab, the open commodity) with whitelisted **actions**.

Pages run in WebKit's sandbox, in a separate process: no network, no files outside the plugin's folder, no access to the rest of your desktop. See [architecture.md](architecture.md) for how that's enforced.

The example in [examples/plugins/keys/](../examples/plugins/keys/) is the Keys tab rebuilt as a plugin. It's a good starting point.

## Installing and showing a plugin

Put the plugin's folder in `~/.config/oolite-helper/plugins/` (or symlink it there while developing), then add a widget for it to `~/.config/oolite-helper/config.toml`:

```toml
[[widgets]]
components = ["keys"]  # the plugin's name; a plugin is alone in its widget
screen = "eDP-1"       # free on a monitor, or dock = "game:right" etc.
x = 0
y = 0
width = 900
height = 1000
layout = "large"       # sets --oo-scale in the theme ("compact" is the default)
```

Plugins are found when the helper starts. A broken one is named in the helper's status line with the reason; the others carry on.

## plugin.toml

```toml
name = "keys"                    # must match the folder; lower case, digits and -, up to 40
version = "1.0.0"
api = 1                          # the plugin API version it was written for
description = "The keys for what you're doing now"   # optional
topics = ["context", "key_sections"]   # what it reads (below)
keys = ["key_jumpdrive"]         # optional: these actions' keys, as the "keys" topic
actions = ["ui/choose_tab"]      # optional: what it may send (below)
width = 900                      # default size, until the page calls oolite.resize()
height = 600
entry = "index.html"             # optional
```

## The page

The helper adds an `oolite` object to the page before its scripts run:

| | |
|---|---|
| `oolite.api` | `1` |
| `oolite.on(topic, fn)` | calls `fn(value)` now if the topic has a value, and whenever it changes. Returns a function that stops it. |
| `oolite.dispatch(action)` | sends an action listed in `actions`. Anything else is refused and logged. |
| `oolite.resize(width, height)` | asks for a new size (16–4000 px). Docked widgets keep the game's width or height on the docked side. |
| `oolite.show(shown)` | `false` hides the window while the page has nothing to show (e.g. drive lamps while docked); `true` shows it again. Pages start shown. Only a widget with `hide_empty = true` hides: by default widgets stay shown, so a page should say why it's empty rather than draw nothing. |
| `oolite.log(text)` | writes a line to the helper's log, for debugging. |

The helper also serves two files to every plugin:
- `_oolite/theme.css`: its colours and fonts (below). Link it before your own stylesheet.
- `_oolite/dev.js`: empty in the helper. Include it before your scripts: a browser preview can use it to provide a fake `oolite` object.

```html
<link rel="stylesheet" href="_oolite/theme.css">
<script src="_oolite/dev.js"></script>
<script src="app.js"></script>
```

**What the sandbox refuses**, so don't rely on it: inline `<script>` and `on...=` attributes (put scripts in files), `eval` and `new Function`, `fetch`/XMLHttpRequest/WebSockets (even to your own files: data comes only through `oolite.on`), images, fonts or scripts from anywhere but your folder (`data:` and `blob:` images are fine), pop-ups, navigating away, and right-click menus. Inline `style` attributes are allowed.

**Clicks never take keyboard focus from the game**, but there's no keyboard input either: don't use text fields.

## Topics

Plain JSON. **Constants for logic, text for showing:** anything meant to be read by the player (`text`, `keys`, `description`, `name`) comes with constants beside it (`kind`, `status`, `action`, `bindings`, `commodity`). Decide things by the constants and show the text, so your plugin keeps working if the text is ever in another language. Prices are decicredits (10 = 1 credit).

| Topic | Value |
|---|---|
| `context` | what the player is doing: "docked", "flying", "near station", "red alert", "jump countdown", "menu", "ship destroyed", "waiting for game" or "game not running" |
| `alert` | "docked", "green", "yellow" or "red"; null before the game says |
| `location` | {"system": name or null, "reached_target": true if the last jump arrived where it was aimed, "aimed_at": the intended system when a jump went elsewhere, or null} |
| `screen` | {"gui": the game screen, e.g. "GUI_SCREEN_STATUS", "view": e.g. "VIEW_FORWARD"} |
| `details` | short notes: [{"kind": "countdown", "galactic": false, "seconds": 9, "text": "Jump in 9s"}, {"kind": "docking_computer", "text": "Docking computer on"}, {"kind": "jump_failed", "reason": ..., "text": ...}, {"kind": "destroyed", "by": ..., "cause": ..., "text": ...}] |
| `drive` | while flying: {"torus": {"ok": bool, "by": ...}, "jump": {"ok": bool, "by": ...}}, else null; by is what blocks it (a ship's name, or "planet" or "sun"), or null |
| `mass_lock` | what locks the torus drive: a ship's name, or "planet" or "sun"; null if nothing |
| `radar` | what's on the scanner while flying, nearest first: [{"name": "Krait", "kind": "ship" (or "police", "military", "thargoid", "missile", "station", "buoy", "rock", "cargo", "mine"), "role": e.g. "pirate", "distance_km": 4.2, "bounty": credits, "doing": "attacking you", "attacking <name>", "fleeing" or null, "hostile": bool (targeting you), "colour": "#ff4000" its scanner colour, "flash": the colour it flashes to every 0.25 s, or null}]; [] when nothing is there |
| `hold` | everything aboard, or null before the game says: {"goods": one per lot, oldest first: [{"commodity": "food", "name": "Food", "units": 12, "unit": "t", "paid_each": decicredits or null (scooped or unknown), "paid", "from": {"galaxy", "system": id, "name"}, "scooped" or null (unknown), "worth_each": decicredits at the last market seen or null if it doesn't list it, "worth", "profit": worth - paid or null}], "passengers" and "parcels": [{"name", "destination": system id, "destinationName", "fee": credits, "risk", "time_left": seconds (below 0 = late) or null, "time_left_text": "2d 3h", "late": bool}], "contracts": [{"commodity", "name", "quantity", "destination", "destinationName", "fee", "time_left", "time_left_text", "late"}], "space": {"used": t, "capacity": t}, "worth_at": {"system", "station", "age": "5m ago"} or null} |
| `jump_blocker` | {"by": the ship or station in the way, "clear_at": metres away it stops blocking}, or null |
| `clearance` | near a station: {"status": "none", "requested", "granted", "timing_out", "not_required" or "refused", "text": "Cleared to dock", "colour": "green", "amber" or "red", "flashes": bool}, else null |
| `tip` | the tip lines under the tabs: ["Waiting for clearance. ...", ...] |
| `key_sections` | what the Keys tab shows now: [{"title": "Flight", "keys": [{"action": "key_roll_left", "bindings": [{"key": "arrowLeft", "shift": false, "ctrl": false, "alt": false}], "keys": "←", "description": "Roll left", "available": false if the ship lacks the equipment it needs (grey it out)}, ...]}, ...]; unbound actions are left out, and unavailable ones too if the player set missing_equipment = "hide" |
| `all_keys` | every key, by the game's groups: [{"group": "header-screen-access", "title": ..., "keys": [the same entries as key_sections, unbound ones too]}, ...] |
| `tabs` | {"shown": "keys", "all" or "trade", "chosen": the player's choice, "urgent": true while an emergency shows Keys whatever was chosen, "tabs": [{"id", "text"}, ...]} |
| `selection` | {"commodity": open in the trade detail or null, "destination": system id or null (null = the best price), "quantity": units or null (null = the most you can buy)} |
| `market_age` | {"seen_at": ISO time of the newest remembered prices, "text": "5m ago"}, or null |
| `trade_rows` | one per commodity: [{"commodity": "food", "name": "Food", "unit": "t", "illegal", "stock", "here": {"price": decicredits or null, "note": "" or how old, "live"}, "best": {"price", "note", "estimate"}, "where": {"name", "distance": ly}, "margin": decicredits or null}, ...]; prices are decicredits (10 = 1 credit) |
| `trade_detail` | the open commodity, or null: {"commodity", "name", "row": as in trade_rows, "offers": [{"system_id", "name", "price", "note", "estimate", "distance", "economy", "economy_name", "government", "government_name", "dangerous", "illegal"}, ...], "chosen": system id, "limit": {"most", "reason": "on_sale", "credits", "cargo_space" or "not_sold_here", "text"}, "quantity", "steps": [text]} |
| `market_advice` | Trade here, while docked: [{"heading", "lines": [{"text", "warning"}]}, ...] |
| `equipment` | what's fitted: {"items": [{"key": "EQ_ECM", "name": "E.C.M. System", "description": the game's own text, "count": 1, "ok": false if damaged}, ...], "missiles": {"pylons": how many, or null before the game says, "loaded": [{"key": "EQ_MISSILE", "name": "Missile", "count": 2}, ...]}} |
| `status` | the status line: {"kind": "error", "warning", "notice", "message" or null, "text"} |
| `last_message` | the last message from the game, as raw JSON text, for debugging; null before one |
| `keys` | the actions in your manifest's `keys`: {action: {"action", "bindings", "keys", "description"}} |

A key entry is `{"action": "key_roll_left", "bindings": [{"key": "arrowLeft", "shift": false, "ctrl": false, "alt": false}], "keys": "←", "description": "Roll left"}`. `bindings` uses the game's own key names (`keyconfig2.plist`), after your remaps; `keys` is how the helper shows them.

## Actions

The same actions the helper's components send. They change the helper's **shared** selections, so its own window follows your plugin's clicks, and the other way round.

| Action | Fields |
|---|---|
| `ui/choose_tab` | `tab`: a component that can be a tab: `"keys"`, `"all_keys"` or `"trade_table"` |
| `ui/open_commodity` | `commodity`: a commodity key such as `"food"`, or `null` to go back to the list |
| `ui/choose_destination` | `system`: a system id (0–255) from `trade_detail.offers`, or `null` for the best price |
| `ui/change_quantity` | `quantity`: units (0 or more), or `null` for the most you can buy |

Other fields, other values or actions not in your manifest are refused.

## The theme

`_oolite/theme.css` sets the page's background, text colour and font, and these variables:

| Variable | |
|---|---|
| `--oo-bg`, `--oo-panel` | background, and panels on it |
| `--oo-fg`, `--oo-dim` | text, and secondary text |
| `--oo-edge` | the window edge it draws around every widget |
| `--oo-accent`, `--oo-green`, `--oo-red` | keys and highlights; good; bad |
| `--oo-sans`, `--oo-mono` | fonts |
| `--oo-scale` | the widget's layout scale (`large` 1, `compact` 0.6, times its `font_scale`) |

The helper's components size text in points times the scale, so `font-size: calc(20pt * var(--oo-scale))` matches their key lists.

## Developing

- Preview a plugin in an ordinary browser with a fake game scenario:
  ```bash
  .venv/bin/python -m helper.preview examples/plugins/keys --scenario scenarios/trade.yaml
  ```
  Open the printed URL. `--speed` changes the scenario timeline, `--loop` repeats
  it, `--port` selects the local port (default 8565), and `--layout` selects the
  theme scale (`compact` by default). The preview serves only on `127.0.0.1`.
  Its CSP is slightly less strict than the helper's: the preview allows
  same-origin connections for its event stream and message endpoint.
- Run the helper with the fake game (see CONTRIBUTING.md) and your plugin in a widget: every topic is live, and `oolite.log` lines appear in the helper's output.
- `.venv/bin/python -m helper.webhost <folder>` opens just the page, with only a ticking `clock` topic: handy for layout.
