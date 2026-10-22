# Oolite Key Helper

A second-screen helper for the space game [Oolite](https://oolite.space/). It shows the keyboard shortcuts for whatever you're doing in the game at that moment, and updates as you play.

- **Docked**: station screens, and market, chart or planet-info keys on those screens
- **Flying**: flight, views, targeting, travel and screen keys
- **Near a station**: docking keys, your clearance status (none, requested, granted, timing out, not required) and docking tips
- **Red alert**: combat and escape keys
- **Jump countdown**: seconds left and how to cancel
- **Docking clearance badge** near a station: green "Cleared to dock", amber "Waiting for clearance", flashing amber "Clearance expiring: press Shift+L to extend" (your key), red "No clearance" or "Clearance refused"
- **Where you are**: the system name beside the heading, with a green "✓ your jump target" when it's where your last jump was aimed (or "aimed for …" in red if a jump landed elsewhere)
- **Drive status chips** while flying: **TORUS ✓/✗** and **JUMP ✓/✗**, with what is holding each, updated every second
- **Torus drive locked**: what's holding the mass lock (a ship on the scanner, or the planet)
- **Too close to jump**: a warning while a station or big ship is near enough to block a hyperspace jump, with how far to fly; a failed jump says why
- **Menu screens in flight**: the keys for that screen

The keys come from **your own game settings**: the game's built-in key config, your keyboard layout, and any keys you've changed in Oolite's Keyboard Configuration screen. If you remap something, the helper shows the new key.

![Near a station: the game on the left, the helper on the right. The station has put the docking request in a queue, and the helper shows "Clearance: requested" with the docking keys.](docs/near-station.png)

*Above: waiting for docking clearance (the station has put you at queue position 11). The game is on the left and the helper's second screen is on the right.*

| | |
|---|---|
| ![Jump countdown](docs/countdown.png) **Jump countdown**: time left, and how to cancel | ![Galactic chart](docs/chart.png) **Chart in flight**: chart keys and screen switching |
| ![Docked, status screen](docs/docked.png) **Docked**: station screens and menu keys | ![Market screen](docs/market.png) **Market**: buying and selling keys |

> Status: working and in daily use on Linux with Oolite 1.92.1. All screenshots are from real play.

## How it works

```
Oolite + CtxKeys.oxp ──JSON lines──▶ Latest.log ──follow──▶ helper window (Python/Tk)
  (game events)                                              (keys for the current context)
```

1. **[oxp/CtxKeys.oxp](oxp/CtxKeys.oxp)** is an Oolite add-on. Its world script listens for game events (docking, station aegis, alert level, docking clearance, jump countdowns, screen and view changes, and trade/chart events). It writes each event to the game log as a JSON line, e.g. `[ctxkeys]: {"type":"aegis","inside":true,...}`.
2. **[helper/](helper/)** follows `Latest.log`, works out the current context and draws the matching key list. The window has no title bar, sits on a second screen and never takes focus from the game.
3. On startup the helper reads the key bindings and the game's own key descriptions from the AppImage. It caches them until the AppImage changes, then applies your layout and key changes from the game's settings.

Any add-on can write `[ctxkeys]` lines to the log, so a misbehaving add-on could make the helper show the wrong context. The impact is cosmetic.

### Messages

Each add-on line in the log looks like `HH:MM:SS.mmm [ctxkeys]: {json}`, and every message has a `type`.

| Type | Sent when | Fields |
|---|---|---|
| `hello` | A game starts or is loaded (`startUp`), including the reload after death | `version` |
| `ready` | The game has finished loading (`startUpComplete`) | `docked`, `view`, `alert` |
| `gui` | The screen changes | `to`, `from` (`GUI_SCREEN_*`) |
| `view` | The view direction changes | `to`, `from` (`VIEW_*`) |
| `docked` | The ship docks | `station` |
| `launching` | A launch starts | `station` |
| `aegis` | Entering or leaving a station's aegis; also after launching, after a jump, and at startup in flight | `inside`, `station`, `requiresClearance`, `clearance` |
| `clearance` | Docking clearance is requested, granted, expires, is cancelled or refused, or changes while you're in the aegis (checked once a second) | `status` (`DOCKING_CLEARANCE_STATUS_*`), `event` (`requested`, `granted`, `expired`, `cancelled`, `refused`, `changed`) |
| `autopilot` | The docking computer is switched on or off | `on` |
| `alert` | The alert condition changes | `level` (0 docked, 1 green, 2 yellow, 3 red) |
| `countdown` | A jump countdown starts | `kind` (`standard`, `galactic`), `seconds` |
| `countdown_end` | A countdown is cancelled, a jump fails, or the jump starts | `reason` (`cancelled`, `jumped`, or the game's failure reason), `cause` (when jumped) |
| `jump_blocker` | In flight, checked each second: the nearest ship that would block a jump changes | `by` (its name, or `null` when clear), `clearAt` (metres beyond which it stops blocking) |
| `mass_lock` | In flight, checked each second: what locks the torus drive changes | `by` (a ship's name, `planet`, `sun`, or `null` when free) |
| `arrived` | The ship leaves witchspace | `system`, `alert` |
| `market` | Docking, startup while docked, or opening the market screen while docked | `galaxy`, `systemID`, `systemName`, `gameClock`, `station`, `market`, `credits`, `cargoSpace`, `fuel`, `manifest` |
| `bought`, `sold` | Cargo is bought or sold | `galaxy`, `systemID`, `systemName`, `gameClock`, `commodity`, `units`, `price` (per unit) |
| `systems` | Startup, docking, arrival, and fuel scooping that changes which systems are in range | `galaxy`, `fuel`, `systems` (each with `id`, `name`, `distance`, `economy`, `government`, `techLevel`, `samplePrices`) |
| `chart_target` | Startup, arrival, and a new system selected on the chart | `infoSystem`, `targetSystem`, `currentSystem`, `system` (as in `systems`), `originMarket`, `manifest` |
| `died` | The player's ship is destroyed | `cause` (damage type), `by` (killer's name, or `null`) |

The helper adds two messages of its own: `session` when it opens a new log file (each game start), and `closed` when the log shows the game has exited.

Notes on the fields:
- `market` and `originMarket` are the station's market keyed by commodity: `price`, `quantity`, `quantity_unit`, and numeric `legality_export`/`legality_import`. `originMarket` is the current system's main station.
- `cargoSpace` is `available` and `capacity`; `manifest` is the game's cargo list (`name`, `unit`, `quantity`, `displayName`).
- Prices, including `samplePrices` and cargo-event prices, use Oolite's decicredit scale (10 decicredits = 1 credit). Distances and fuel are in light-years. `techLevel` is the game's 0-based value; the game shows it plus one.
- The game interfaces used are [`station.market`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSStation.m), [`System.infoForSystem()`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSSystem.m), [`SystemInfo.samplePrice()` and `distanceToSystem()`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Scripting/OOJSSystemInfo.m), and the cargo events in [`PlayerEntity.m`](https://github.com/OoliteProject/oolite/blob/1.92.1/src/Core/Entities/PlayerEntity.m).

What the helper does with the trade data:
- It saves every market it sees, with the time it saw it, to `~/.local/share/oolite-helper/markets.json` (or `$XDG_DATA_HOME/oolite-helper/markets.json`), and shows the age of the latest remembered prices.
- Purchases and sales update a weighted-average cost per commodity. A sale reduces the quantity and the remaining cost at that average.
- On either chart, it shows the selected system's economy, government and tech level, estimates the sale margins for your cargo and the purchase margins here (skipping goods that are out of stock and marking illegal ones), and lists the nearest agricultural and industrial systems in fuel range.

Example message lines:

```json
{"type":"market","galaxy":0,"systemID":7,"systemName":"Lave","gameClock":123456,"station":"Lave Station","market":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0}},"credits":1200.5,"cargoSpace":{"available":18,"capacity":35},"fuel":7,"manifest":[{"name":"food","unit":"tonnes","quantity":2,"displayName":"Food"}]}
{"type":"bought","galaxy":0,"systemID":7,"systemName":"Lave","gameClock":123458,"commodity":"food","units":2,"price":42}
{"type":"sold","galaxy":0,"systemID":7,"systemName":"Lave","gameClock":123460,"commodity":"computers","units":1,"price":735}
{"type":"systems","galaxy":0,"fuel":7,"systems":[{"id":8,"name":"Zaonce","distance":6.5,"economy":8,"government":9,"techLevel":10,"samplePrices":{"food":48,"computers":738}}]}
{"type":"chart_target","infoSystem":8,"targetSystem":9,"currentSystem":7,"system":{"id":8,"name":"Zaonce","distance":6.5,"economy":3,"government":5,"techLevel":10,"samplePrices":{"food":48,"computers":738}},"originMarket":{"food":{"price":42,"quantity":8,"quantity_unit":0,"legality_export":0,"legality_import":0}},"manifest":[{"name":"food","unit":"tonnes","quantity":2,"displayName":"Food"}]}
{"type":"died","cause":"energy damage","by":"Krait"}
```

A later version may receive the same messages over Oolite's debug console connection instead of the log. That would allow live data for a fuller HUD, as [oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge) does.

## Requirements

- Linux with X11 (developed on MATE)
- Oolite 1.92.1 Linux AppImage
- Python 3.11+ with Tkinter (`sudo apt install python3-tk` on Debian/Ubuntu)
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
.venv/bin/oolite-helper [--stay] [window options]
```

`--stay` keeps the window open when the game exits. Right-click the window to close it.

Left-click the tabs under the heading to switch views. Clicking the helper doesn't take keyboard focus from the game, so you can carry on flying.
- **Keys** shows the keys for what you're doing now.
- **All keys** shows every key, grouped as on the game's keyboard configuration screen; click a group to show it.
- **Trade** lists every commodity with its price here, the best price within fuel range (a remembered real price with its age, or the game's estimate marked "est."), where that is, and the margin. Click a column heading to sort by it, and again to reverse. Illegal goods are in red; goods out of stock here are marked "(none)". In flight, "Here" is the remembered market for the system you're in.

  Click a commodity to open it: every system in fuel range with its price, margin, distance, economy and government (⚠ for Anarchy and Feudal, the dangerous ones). Click a system to choose where to sell. The quantity buttons (−10, −1, +1, +10, Max) are capped by what's on sale, your credits and, for goods sold in tons, free cargo space; the line beside them says which limit applies. Below that are the cost, cargo used and expected profit, and the keys to press in the game, using your own key settings. The helper never presses keys for you.

Docked on the market screen, **Keys** also shows a **Trade here** panel: your hold: what you paid, today's price here and the best place in range to sell it, prices against the last market you saw, what your hold and the best buys are worth at your jump destination, and the best buys for any system in range, ranked by total profit (margin × the units you can afford and fit). Illegal goods are in red; ⚠ marks Anarchy and Feudal systems.

Red alert, a jump countdown or the ship being destroyed always switch to **Keys**, and your chosen tab comes back afterwards.

### Demo mode (no Oolite needed)

The fake game writes one of the scripted timelines to a log file. In separate terminals, run:

```bash
python -m tests.fakegame scenarios/docking.yaml --log /tmp/fake.log --speed 2
.venv/bin/oolite-helper --log /tmp/fake.log --stay
```

The helper follows the scenario just as it follows Oolite's log; `--speed` changes the timeline speed. Try `jump`, `combat`, `menus`, `restart` or `quit` instead of `docking`. The scenario files are JSON-compatible YAML so the fake game needs no extra Python dependencies. The game does not need to be running, but the helper still reads key bindings and descriptions from the installed Oolite AppImage.

### Where the window goes

By default the helper fills the first monitor that **isn't** your primary one, e.g. a laptop screen next to the monitor you play on. To change that, copy [config.example.toml](config.example.toml) to `~/.config/oolite-helper/config.toml`:

```toml
[window]
screen = "DP-1"      # from `oolite-helper --list-screens`
width = "33%"        # pixels or % of that screen
height = "100%"
anchor = "right"     # top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right
margin = 0
font_scale = 0.9
```

That example gives a strip down the right-hand third of a big monitor. The number of key columns (one to three) follows the window width. In a single column, the last sections may run off the bottom of a short window; they're ordered most important first.

`layout = "compact"` shrinks the text and spacing to 60% and allows up to 6 key columns, so more panels fit; `font_scale` adjusts either layout further.

Each setting has a matching command-line option that overrides the file: `--screen`, `--width`, `--height`, `--anchor`, `--margin`, `--layout`, `--font-scale`. Use `--geometry WxH+X+Y` for exact placement.

```bash
.venv/bin/oolite-helper --list-screens
.venv/bin/oolite-helper --screen DP-1 --width 40% --anchor right
```

### Why the launcher?

On some systems, notably Ubuntu 26.04, whose default Rust coreutils link against `libsystemd`, the 1.92.1 AppImage's own start-up script fails: its bundled, older `libsystemd` breaks the host's `mkdir` and `mktemp`. Reported upstream as [OoliteProject/oolite#769](https://github.com/OoliteProject/oolite/issues/769). Oolite then logs to stdout (no `Latest.log`) and puts its settings in `~/GNUstep`. The launcher works around this. It runs the AppImage in "legacy" mode, sets Oolite's `OO_*` folder variables, and writes a GNUstep config, so everything (log, add-ons, saves, settings) lives in `GameData/` next to the AppImage.

## Project layout

| Path | What |
|---|---|
| `oxp/CtxKeys.oxp/` | The Oolite add-on (world script + manifest) |
| `helper/app.py` | The window |
| `helper/sources.py` | Follows `Latest.log`, including log rotation at game start |
| `helper/state.py` | Turns messages into game state and a context |
| `helper/markets.py` | Persists observed markets and commodity cost basis |
| `helper/contexts.py` | Which actions to show per context, and tips |
| `helper/keys.py`, `helper/plist.py` | Reads Oolite's key config and descriptions |
| `helper/screen.py`, `helper/config.py` | Window placement and the config file |
| `scripts/launch-oolite.sh` | Game launcher that fixes the data folders and starts the helper |

## Contributing

Issues and pull requests are welcome. `main` is protected, so every change, including the maintainer's, goes in through a pull request:

1. Fork the repo (or branch, if you have access) from an up-to-date `main`.
2. Make your change on a branch, e.g. `fix/separator`.
3. Open a pull request against `main` and describe what changed and how you tested it.

Every pull request runs CI (pytest on Python 3.11–3.13, ruff, the add-on tests on Node 20 and 22, and shellcheck), and the checks must pass before merging. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run them locally.

## License

[MIT](LICENSE)

## Credits

- [Oolite](https://oolite.space/) and its contributors. Key descriptions shown in the helper come from the game's own files.
- [oolite-mqtt-bridge](https://github.com/maikschulz/oolite-mqtt-bridge), for the idea of getting game state out through an add-on.
