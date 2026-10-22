# How the helper is built

Data flows one way, Redux-style (#53):

```
Oolite + CtxKeys.oxp ──messages──▶ LogSource ──▶ Model.dispatch ──▶ GameState / MarketStore
                                                       ▲                    │
                          clicks: "ui/..." actions ────┘                    ▼
                                                                Model.notify (each 200 ms)
                                                                            │
                                         selectors (named topics) ◀─────────┘
                                                    │ value changed?
                                                    ▼
                                              View.draw(value)
```

| Redux / React | Here |
|---|---|
| Action | A message from the add-on (`{"type": "mass_lock", "by": "planet"}`), or a UI action (`{"type": "ui/open_commodity", "commodity": "furs"}`) |
| Reducer | `GameState.apply`, `MarketStore.apply`, `reduce_ui` |
| Store | `Model` ([helper/model.py](../helper/model.py)) |
| Selector | A pure function `model -> value`; named ones are `TOPICS` |
| Component | A `View` ([helper/views/](../helper/views/)): `select(model)` plus `draw(value)` |

## The model
- `model.dispatch(action)` applies one action. The window dispatches each batch of game messages, then calls `model.notify()` once. It also calls `notify()` on every 200 ms tick, so clock-driven values (countdowns, blinking) move on their own.
- `model.watch(selector, callback)` calls `callback(value)` now and then whenever `selector(model)` returns something different (compared with `==`). `model.subscribe("topic", callback)` does the same for a named topic. Both return a handle with `cancel()`.
- **Named topics** (`TOPICS` in `model.py`) are shared and memoised. Each one is computed once per notify pass however many views use it, and kept between passes until the state changes. Topics that depend on the clock give a period (`every`), e.g. 60 s for price ages shown in minutes.
- **Reducers replace values; they never edit them in place.** Otherwise `==` can't see the change.
- **Errors are isolated.** A selector or draw that raises is reported in the status line (once per distinct error) and retried on the next pass, and the other views carry on.
- **UI state:** selections that several views (or #50's widgets) might share live in the model's `UI` slice and change only through `ui/...` actions: the tab, the open commodity, the chosen destination and quantity. A view's purely local choices (the trade table's sort order, the All keys group) stay in the view, which calls `self.refresh()` after changing one.

## Writing a visualisation
```python
from helper.views import View


class JumpAndLocation(View):
    def __init__(self, model, style, label):
        self.label = label  # build widgets first,
        super().__init__(model, style)  # then subscribe (this draws once)

    def select(self, model):
        # One subscription for everything this redraws: combine topics here.
        return (model.topic("jump_blocker"), model.topic("location"))

    def draw(self, value):
        blocker, (system, reached, aimed_at) = value
        ...
```

Rules:
- **One subscription per thing you redraw.** Combine topics in one selector, so a change to both (an arrival changes the location *and* clears the blocker) redraws once from a consistent snapshot. Use separate views only for parts that redraw independently.
- **Read through topics** where one exists. If you need a new fact, add a topic to `TOPICS` (with a test), so other views can share it.
- **Never change state in a view.** Dispatch a `ui/...` action, and add it to `reduce_ui` if it's new.
- **Never take keyboard focus from the game**: left-click only, no text fields, no `focus_set()` (verified on #20).
- **Keys and descriptions come from the game's files**, through `model.keys(action)`, `model.keymap` and `model.commodity_name(key)`.
- **Use `Style`** (`style.font`, `style.px`, the colours in `views/style.py`) so the view follows the large and compact layouts.

## Plugins: web views in a separate process (#59)
Plugin visualisations are HTML and JavaScript pages, run in WebKit's sandbox by a separate **web host** process ([helper/webhost/host.py](../helper/webhost/host.py)), because Tk and GTK don't share a main loop. The helper drives it with JSON lines over a pipe; the protocol is in [helper/webhost/\_\_init\_\_.py](../helper/webhost/__init__.py).

```
helper (Tk)                                  web host (GTK, system Python)
  Model ──topics──▶ WebHost.publish ──pipe──▶ window per plugin ──▶ WebKit web process
  layout ─────────▶ WebHost.sync    ──pipe──▶ open / place / close    (bubblewrap sandbox)
  status ◀───────── WebHost.poll    ◀──pipe── loaded / page / error / crashed
```

- **The page's whole API is the `oolite` object**: `oolite.on(topic, fn)`, `oolite.resize(w, h)`, `oolite.log(text)`. It gets only the topics the helper sends it, and it can't dispatch actions.
- **Lockdown:** the `plugin://<name>/` scheme serves only that plugin's folder, with a strict CSP (no network, no `eval`, no inline scripts); other navigation, pop-ups, downloads and developer tools are refused. Each window has its own ephemeral web context.
- **The host's environment closes the holes the #59 spike found** (`sandbox_env`): its own cache folder, an *untrusted* X cookie (no XTEST, RECORD, XInput or GLX), and no sound server. If the untrusted cookie can't be made, plugins don't start: it never falls back to the trusted one. `tests/test_webhost_live.py` checks the web process's mounts; run it after WebKit upgrades.
- **Failures stay contained:** a page that fails or crashes is closed and reported (`failed`), the others carry on, and a host that dies is restarted with backoff and its windows replayed.
- **Discovery and topics** ([helper/plugins.py](../helper/plugins.py)): at startup the helper reads each `~/.config/oolite-helper/plugins/<name>/plugin.toml` (name, version, `api`, topics, default size). A plugin is used like a view, alone in a widget: `views = ["jump-lamp"]`, placed by the same `place()` as built-in widgets. It gets only the topics it lists, from `plugins.TOPICS`: **a public API of plain JSON shapes**, mapped from the model's topics, so the model's internals can change without breaking plugins. Add topics freely; changing a shape needs a new `api` version. Key bindings come two ways, both resolved from the game's files and the player's remaps through `model.keys()`/`model.describe()` (the same text as the Keys tab): the `key_sections` topic (what the Keys tab shows now) and `keys = [...]` in `plugin.toml` for specific actions (the `keys` topic). A broken plugin or a page that fails shows in the status line; the rest carry on.
- **Developing a plugin:** `.venv/bin/python -m helper.webhost <plugin folder> --at X,Y` opens it on its own, with a ticking `clock` topic.

## Layouts and the admin panel (planned)
A player-facing admin panel should eventually let the player swap layouts, add panels and reopen closed ones, by clicking. It isn't built yet, but the pieces are shaped for it:

- **Windows are declarative.** `WebHost.sync({id: WebWindow})` (and later the Tk widgets too) takes the full set of windows that should exist, and opens, moves and closes to match. A layout change is just a new set; nothing calls "open" or "close" imperatively.
- **Panel ids are stable** (`"radar"`, `"trade_here"`, or ids from the layout), so a closed panel can be reopened where it was, and failures are kept per id (`WebHost.retry(id)` is the "reopen" button).
- **Next, the layout moves into the model:** a `layout` slice (the panels, each with a stable id, its views or plugin, where it docks and whether it's open) changed only by `layout/...` actions such as `layout/switch`, `layout/open_panel`, `layout/close_panel`, `layout/move_panel`. A watcher turns `model.topic("layout")` plus `game_window` into the `sync()` call. `config.toml` stays the player's hand-written defaults; layout changes made in the panel are saved to a helper-owned file beside it, never by rewriting `config.toml`.
- **The admin panel is a built-in Tk view, never a plugin.** Plugins can only ask about themselves (`resize`; perhaps "close me" later). Discovered plugins and their status (loaded, failed, crashed) become a `plugins` topic the panel can list.
- **It's opened by a click, not a key** (the game keeps keyboard focus), and #50's edit mode (move, resize, close) belongs in it.

## Where things live
- `helper/state.py`: `GameState`, the reducer for game messages, plus derived properties (`context`, `details`, `where`).
- `helper/markets.py`: remembered markets and cost basis (persisted).
- `helper/browser.py`, `trade.py`, `contexts.py`: pure functions that the topics call (trade rows, advice, key sections, tips).
- `helper/model.py`: the store, topics and notification.
- `helper/views/`: `header.py` (heading, location, details, tip, status), `chips.py` (tabs, drive chips, clearance badge), `body.py` (key panels, All keys, trade table and detail, Trade here).
- `helper/app.py`: the window layout, polling the log and the command line.
- `helper/widgets.py`, `gamewindow.py`: views in their own windows, docked to the game (#50).
- `helper/plugins.py`: plugin discovery, `plugin.toml`, the topics plugins can read, and their windows (#59).
- `helper/webhost/`: plugin web views (#59): the client (`__init__.py`), the host process (`host.py`) and a dev runner (`__main__.py`).
