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

## Where things live
- `helper/state.py`: `GameState`, the reducer for game messages, plus derived properties (`context`, `details`, `where`).
- `helper/markets.py`: remembered markets and cost basis (persisted).
- `helper/browser.py`, `trade.py`, `contexts.py`: pure functions that the topics call (trade rows, advice, key sections, tips).
- `helper/model.py`: the store, topics and notification.
- `helper/views/`: `header.py` (heading, location, details, tip, status), `chips.py` (tabs, drive chips, clearance badge), `body.py` (key panels, All keys, trade table and detail, Trade here).
- `helper/app.py`: the window layout, polling the log and the command line.
