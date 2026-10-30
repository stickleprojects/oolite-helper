"""The store: all helper state, and change notification for the components (#53).

Redux-style. Messages from the add-on and UI actions ("ui/...") are both
dispatched here; GameState, MarketStore and the UI reducer below apply them.
Components never change the state: they watch selectors (pure functions of the
model) and are told when a selector's value changes.

    model.subscribe("jump_blocker", draw)                  # a named topic
    model.watch(lambda m: (m.topic("jump_blocker"),        # or any selector,
                           m.topic("location")), draw)     # e.g. two topics combined

One subscription per thing a component redraws: combine topics inside one selector
rather than subscribing twice, so the component redraws once from a consistent
snapshot.

notify() runs after each batch of messages and on every clock tick. Each
watcher's selector is evaluated and its callback runs only when the value
changed (compared with ==), so reducers must replace values, not edit them in
place. Named topics are memoised: computed once per pass however many components
use them, and kept between passes until the state changes (or their time
bucket ends, for topics that depend on the clock).
"""

import time
from dataclasses import dataclass, replace

from . import hold, radar
from .browser import buy_limit, commodity_offers, commodity_rows, held, market_advice, trade_steps
from .contexts import ACTION_NOTES, clearance_badge, indicators, missing, sections, tip
from .keys import commodity_fallback
from .layout import reduce_layout
from .state import GameState

# Contexts that switch the tab back to Keys whatever tab is chosen; the chosen
# tab comes back when they end.
URGENT = ("red alert", "jump countdown", "ship destroyed")


@dataclass(frozen=True)
class UI:
    """Selections that more than one component (or widget, #50) may care about."""

    tab: str = "keys"  # the tab the player chose
    commodity: str | None = None  # commodity open in the trade detail
    destination: int | None = None  # system chosen there; None = the best price
    quantity: int | None = None  # units chosen there; None = the most you can buy


def reduce_ui(ui, action):
    """The UI reducer: a new UI for a "ui/..." action."""
    kind = action["type"]
    if kind == "ui/choose_tab":
        return replace(ui, tab=action["tab"])
    if kind == "ui/open_commodity":
        return replace(ui, commodity=action.get("commodity"), destination=None, quantity=None)
    if kind == "ui/choose_destination":
        return replace(ui, destination=action.get("system"))
    if kind == "ui/change_quantity":
        return replace(ui, quantity=action.get("quantity"))
    raise ValueError(f"unknown UI action {kind!r}")


class Subscription:
    """A watcher; cancel() stops its notifications."""

    def __init__(self, model, selector, callback):
        self.model = model
        self.selector = selector
        self.callback = callback
        self.value = _UNSET

    def cancel(self):
        if self in self.model._watchers:
            self.model._watchers.remove(self)


_UNSET = object()


class Model:
    def __init__(
        self,
        state=None,
        markets=None,
        keymap=None,
        clock=time.monotonic,
        missing_equipment="grey",
        layout=(),
    ):
        self.state = state if state is not None else GameState()
        # Keys for equipment the ship hasn't got: "grey" shows them dimmed, "hide" leaves them out.
        self.missing_equipment = missing_equipment
        self.markets = markets  # MarketStore (remembered markets and cost basis), or None
        self.keymap = keymap
        self.clock = clock
        self.ui = UI()
        self.layout = tuple(layout)  # layout.Panel for each widget (#50)
        # The game window, from gamewindow.GameWindow: ((x, y, w, h) or None,
        # frame borders (left, right, top, bottom), whether it's the active window).
        self.game_window = (None, (0, 0, 0, 0), False)
        self.status = {}  # app status for the status line: error, notice, last message
        self.version = 0  # bumped on every change; memoised topics key on it
        self.on_error = None  # called as on_error(exc, where) when a component fails
        self._watchers = []
        self._cache = {}  # topic -> (key, value)

    # -- changing state --------------------------------------------------

    def dispatch(self, action):
        """Apply a game message, a "ui/..." or "layout/..." action, or a "window/game" update.

        Call notify() after a batch.
        """
        kind = str(action.get("type", ""))
        if kind.startswith("ui/"):
            self.ui = reduce_ui(self.ui, action)
        elif kind.startswith("layout/"):
            self.layout = reduce_layout(self.layout, action)
        elif kind == "window/game":
            geometry = action.get("geometry")
            self.game_window = (
                tuple(geometry) if geometry else None,
                tuple(action.get("frame") or (0, 0, 0, 0)),
                bool(action.get("active")),
            )
        else:
            if self.markets is not None:
                self.markets.apply(action)
            self.state.apply(action)
        self.version += 1

    def set_status(self, **fields):
        self.status = {**self.status, **fields}
        self.version += 1

    # -- reading state ---------------------------------------------------

    def topic(self, name):
        """A named topic's current value, memoised (see TOPICS)."""
        selector, every = TOPICS[name]
        return self.memo(name, every, selector)

    def memo(self, name, every, selector):
        """selector(model), computed once per state change (and per `every`
        seconds; every=0: each call). Topics and plugin topics use it."""
        if every == 0:
            return selector(self)
        bucket = None if every is None else int(self.clock() / every)
        key = (self.version, bucket)
        cached = self._cache.get(name)
        if cached is not None and cached[0] == key:
            return cached[1]
        value = selector(self)
        self._cache[name] = (key, value)
        return value

    def commodity_name(self, key):
        return self.keymap.commodity(key) if self.keymap else commodity_fallback(key)

    def keys(self, action):
        return self.keymap.keys(action) if self.keymap else ""

    def bindings(self, action):
        return self.keymap.bindings_of(action) if self.keymap else []

    def describe(self, action):
        """An action as the game describes it, plus our note on when it works, if any."""
        if self.keymap:
            text = self.keymap.describe(action)
        else:
            text = action.removeprefix("key_").replace("_", " ")
        note = ACTION_NOTES.get(action)
        return f"{text} ({note})" if note else text

    # -- notification ----------------------------------------------------

    def watch(self, selector, callback, initial=True):
        """Call callback(value) whenever selector(model) changes.

        With initial=True the callback also runs now, with the current value.
        """
        subscription = Subscription(self, selector, callback)
        self._watchers.append(subscription)
        if initial:
            self._check(subscription)
        return subscription

    def subscribe(self, name, callback, initial=True):
        TOPICS[name]  # unknown names fail here, not at the first notify
        return self.watch(lambda model: model.topic(name), callback, initial)

    def notify(self):
        """Tell each watcher whose value changed. A failing component doesn't stop the others."""
        for subscription in list(self._watchers):
            self._check(subscription)

    def _check(self, subscription):
        try:
            value = subscription.selector(self)
            if value == subscription.value:
                return
            subscription.value = value
            subscription.callback(value)
        except Exception as exc:
            subscription.value = _UNSET  # try again on the next pass
            if self.on_error is None:
                raise
            self.on_error(exc, subscription.callback)


# -- topics --------------------------------------------------------------
# name -> (selector, every). every=None: depends only on the state, cached
# until it changes. every=N: also depends on the clock, recomputed every N
# seconds. every=0: recomputed on every pass.


def _markets(model):
    store = model.markets
    if store is None:
        return [], {}, None
    return store.data["markets"], store.cost_basis, store.now()


def _trade_rows(model):
    markets, _, now = _markets(model)
    return tuple(commodity_rows(model.state, markets, now)) if now else ()


def _market_advice(model):
    state = model.state
    if not state.docked:
        return ()
    markets, basis, now = _markets(model)
    if now is None:
        return ()
    groups = market_advice(state, markets, basis, now, model.commodity_name)
    return tuple((heading, tuple(lines)) for heading, lines in groups)


def _trade_detail(model):
    """Everything the trade detail shows for the open commodity, or None."""
    commodity = model.ui.commodity
    markets, _, now = _markets(model)
    if commodity is None or now is None:
        return None
    state = model.state
    row = next((r for r in model.topic("trade_rows") if r.commodity == commodity), None)
    offers = tuple(commodity_offers(state, markets, now, commodity))
    offer = next((o for o in offers if o.system_id == model.ui.destination), None)
    offer = offer or (offers[0] if offers else None)
    limit = buy_limit(state, markets, now, commodity)
    quantity = limit.most if model.ui.quantity is None else model.ui.quantity
    quantity = max(0, min(quantity, limit.most))
    steps = trade_steps(
        model.keys,
        model.commodity_name(commodity),
        quantity,
        limit.most,
        offer,
        state,
        held(state, commodity),
    )
    return (commodity, row, offers, offer, limit, quantity, tuple(steps))


def _hold(model):
    store = model.markets
    lots, market, now = {}, None, None
    if store is not None:
        lots, now = store.data["lots"], store.now()
        market = max(store.data["markets"], key=lambda m: m.get("seen_at") or "", default=None)
    state = model.state
    return hold.hold(state.hold, state.game_clock_now, lots, market, now, model.commodity_name)


def _sections(model):
    """The Keys tab's (title, actions), without missing equipment's keys if set to hide."""
    hide = model.missing_equipment == "hide" and model.topic("missing")
    return tuple(
        (title, tuple(a for a in actions if not (hide and a in hide)))
        for title, actions in sections(model.state)
    )


def _visible_tab(model):
    return "keys" if model.state.context in URGENT else model.ui.tab


TOPICS = {
    "context": (lambda m: m.state.context, None),
    "location": (lambda m: m.state.where, None),
    "screen": (lambda m: (m.state.gui, m.state.view), None),
    "details": (lambda m: tuple(m.state.details), 0),  # a countdown ticks
    "market_age": (lambda m: m.markets.price_age if m.markets else None, 30),
    "tip": (lambda m: tip(m.state, m.keymap), None),
    "mass_lock": (lambda m: m.state.mass_lock, None),
    "radar": (lambda m: radar.blips(m.state.radar), None),
    "hold": (_hold, 30),  # contracts' time left counts down
    "jump_blocker": (lambda m: dict(m.state.jump_blocker or {}) or None, None),
    "indicators": (lambda m: tuple(indicators(m.state)), None),
    "clearance": (lambda m: clearance_badge(m.state, m.keymap), None),
    "clock": (lambda m: int(m.clock() * 2), 0),  # half seconds, for blinking
    "tab": (_visible_tab, None),
    "missing": (lambda m: missing(m.state), None),
    "sections": (_sections, None),
    "trade_rows": (_trade_rows, 60),  # price ages are shown in minutes
    "trade_detail": (_trade_detail, 60),
    "market_advice": (_market_advice, 60),
    "equipment": (lambda m: (tuple(m.state.equipment or ()), m.state.missiles), None),
    "ui": (lambda m: m.ui, None),
    "status": (lambda m: dict(m.status), None),
    "game_window": (lambda m: m.game_window, None),
    "layout": (lambda m: m.layout, None),
}
