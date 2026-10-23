"""What plugins can read, send and style with (#59): the public plugin API.

Version 1 (`api = 1` in plugin.toml). Everything here is plain JSON in the
documented shapes, mapped from the model, so the model's internals can change
without breaking plugins. Add topics and actions freely; changing a shape
needs a new API version.

Constants for logic, text for showing: anything meant to be read by the
player ("text", "keys", "description", "name") comes with constants beside it
("kind", "status", "action", "bindings", "commodity"), so a plugin never has
to parse display text, and keeps working if the text is ever in another
language (Oolite has language add-ons; the helper's own words are English).

The topics are enough to rebuild the whole laptop window as a plugin.
"""

import re

from .contexts import ALL_KEY_GROUPS
from .model import URGENT
from .tk.components.chips import TABS
from .tk.components.header import status_line
from .tk.components.style import ACCENT, BG, DIM, FG, GREEN, LAYOUTS, MONO, PANEL, RED, SANS
from .trade import ECONOMIES, GOVERNMENTS

API = 1
ALERTS = {0: "docked", 1: "green", 2: "yellow", 3: "red"}
TAB_IDS = tuple(name for name, _ in TABS)

# -- topics ------------------------------------------------------------------


def key_info(model, action):
    """An action's keys: constants (action, bindings) and the Keys tab's text (keys, description).

    keys is "" and bindings [] if it's unbound.
    """
    return {
        "action": action,
        "bindings": model.bindings(action),
        "keys": model.keys(action),
        "description": model.describe(action),
    }


def _location(model):
    system, reached, aimed_at = model.topic("location")
    return {"system": system, "reached_target": reached, "aimed_at": aimed_at}


def _drive(model):
    lamps = {
        label.lower(): {"ok": ok, "by": by or None} for label, ok, by in model.topic("indicators")
    }
    return lamps or None


def _jump_blocker(model):
    blocker = model.topic("jump_blocker")
    return {"by": blocker["by"], "clear_at": blocker.get("clearAt")} if blocker else None


def _clearance(model):
    badge = model.topic("clearance")
    if badge is None:
        return None
    text, colour, flashes = badge
    state = model.state
    if state.requires_clearance is False:
        status = "not_required"
    elif state.clearance_refused:
        status = "refused"
    else:
        status = (state.clearance or "DOCKING_CLEARANCE_STATUS_NONE").removeprefix(
            "DOCKING_CLEARANCE_STATUS_"
        )
        status = status.lower()
    return {"status": status, "text": text, "colour": colour, "flashes": flashes}


def _details(model):
    return [
        {"kind": kind, **fields, "text": text} for kind, fields, text in model.state.detail_items
    ]


def _screen(model):
    gui, view = model.topic("screen")
    return {"gui": gui, "view": view}


def _key_sections(model):
    missing = model.topic("missing")
    return [
        {
            "title": title,
            "keys": [
                {**key_info(model, a), "available": a not in missing}
                for a in actions
                if model.keys(a)
            ],
        }
        for title, actions in model.topic("sections")
    ]


def _all_keys(model):
    return [
        {"group": group, "title": model.describe(group), "keys": [key_info(model, a) for a in keys]}
        for group, keys in ALL_KEY_GROUPS
    ]


def _tip(model):
    return [line for line in model.topic("tip").split("\n") if line]


def _tabs(model):
    shown = model.topic("tab")
    return {
        "shown": shown,
        "chosen": model.ui.tab,
        "urgent": model.state.context in URGENT,  # shown is "keys" whatever was chosen
        "tabs": [{"id": name, "text": title} for name, title in TABS],
    }


def _selection(model):
    ui = model.ui
    return {"commodity": ui.commodity, "destination": ui.destination, "quantity": ui.quantity}


def _market_age(model):
    seen = model.markets.price_seen if model.markets else None
    if seen is None:
        return None
    return {"seen_at": seen.isoformat(), "text": model.topic("market_age")}


def _price(price, note, estimate=None):
    out = {"price": price, "note": note}
    if estimate is not None:
        out["estimate"] = estimate
    return out


def _row(model, row):
    return {
        "commodity": row.commodity,
        "name": model.commodity_name(row.commodity),
        "unit": row.unit,
        "illegal": row.illegal,
        "stock": row.stock,
        "here": {
            **_price(row.here, row.here_note),
            "live": row.here is not None and not row.here_note,
        },
        "best": _price(row.best, row.best_note, row.best_note == "est."),
        "where": {"name": row.where or None, "distance": row.distance},
        "margin": row.margin,
    }


def _named(names, index):
    return names[index] if isinstance(index, int) and 0 <= index < len(names) else None


def _offer(offer):
    return {
        "system_id": offer.system_id,
        "name": offer.name,
        **_price(offer.price, offer.note, offer.note == "est."),
        "distance": offer.distance,
        "economy": offer.economy,
        "economy_name": _named(ECONOMIES, offer.economy),
        "government": offer.government,
        "government_name": _named(GOVERNMENTS, offer.government),
        "dangerous": offer.dangerous,
        "illegal": offer.illegal,
    }


def _trade_rows(model):
    return [_row(model, row) for row in model.topic("trade_rows")]


def _trade_detail(model):
    detail = model.topic("trade_detail")
    if detail is None:
        return None
    commodity, row, offers, offer, limit, quantity, steps = detail
    return {
        "commodity": commodity,
        "name": model.commodity_name(commodity),
        "row": _row(model, row) if row else None,
        "offers": [_offer(o) for o in offers],
        "chosen": offer.system_id if offer else None,
        "limit": {
            "most": limit.most,
            "reason": limit.reason.replace(" ", "_"),
            "text": limit.reason,
        },
        "quantity": quantity,
        "steps": list(steps),
    }


def _market_advice(model):
    return [
        {
            "heading": heading,
            # warning: the line is about something illegal here (shown in red)
            "lines": [{"text": line, "warning": "illegal" in line} for line in lines],
        }
        for heading, lines in model.topic("market_advice")
    ]


def _equipment(model):
    items, missiles = model.topic("equipment")
    missiles = missiles or {}
    return {
        "items": [
            {
                "key": item.get("key"),
                "name": item.get("name"),
                "description": item.get("description"),
                "count": item.get("count", 1),
                "ok": item.get("status") != "EQUIPMENT_DAMAGED",
            }
            for item in items
        ],
        "missiles": {
            "pylons": missiles.get("capacity"),
            "loaded": [
                {"key": m.get("key"), "name": m.get("name"), "count": m.get("count", 1)}
                for m in missiles.get("loaded") or []
            ],
        },
    }


def _status(model):
    kind, text = status_line(model.topic("status"))
    return {"kind": kind, "text": text}


# name -> (selector giving JSON, every, what it is). every is as for the
# model's topics: None = changes only with the state, N = also every N
# seconds, 0 = every pass. Values are memoised the same way.
TOPICS = {
    "context": (
        lambda m: m.topic("context"),
        None,
        'what the player is doing: "docked", "flying", "near station", "red alert", '
        '"jump countdown", "menu", "ship destroyed", "waiting for game" or "game not running"',
    ),
    "alert": (
        lambda m: ALERTS.get(m.state.alert),
        None,
        '"docked", "green", "yellow" or "red"; null before the game says',
    ),
    "location": (
        _location,
        None,
        '{"system": name or null, "reached_target": true if the last jump arrived where '
        'it was aimed, "aimed_at": the intended system when a jump went elsewhere, or null}',
    ),
    "screen": (
        _screen,
        None,
        '{"gui": the game screen, e.g. "GUI_SCREEN_STATUS", "view": e.g. "VIEW_FORWARD"}',
    ),
    "details": (
        _details,
        0,
        'short notes: [{"kind": "countdown", "galactic": false, "seconds": 9, '
        '"text": "Jump in 9s"}, {"kind": "docking_computer", "text": "Docking computer on"}, '
        '{"kind": "jump_failed", "reason": ..., "text": ...}, '
        '{"kind": "destroyed", "by": ..., "cause": ..., "text": ...}]',
    ),
    "drive": (
        _drive,
        None,
        'while flying: {"torus": {"ok": bool, "by": ...}, "jump": {"ok": bool, "by": ...}}, '
        'else null; by is what blocks it (a ship\'s name, or "planet" or "sun"), or null',
    ),
    "mass_lock": (
        lambda m: m.topic("mass_lock"),
        None,
        'what locks the torus drive: a ship\'s name, or "planet" or "sun"; null if nothing',
    ),
    "jump_blocker": (
        _jump_blocker,
        None,
        '{"by": the ship or station in the way, "clear_at": metres away it stops blocking}, '
        "or null",
    ),
    "clearance": (
        _clearance,
        None,
        'near a station: {"status": "none", "requested", "granted", "timing_out", '
        '"not_required" or "refused", "text": "Cleared to dock", "colour": "green", "amber" '
        'or "red", "flashes": bool}, else null',
    ),
    "tip": (_tip, None, 'the tip lines under the tabs: ["Waiting for clearance. ...", ...]'),
    "key_sections": (
        _key_sections,
        None,
        'what the Keys tab shows now: [{"title": "Flight", "keys": [{"action": "key_roll_left", '
        '"bindings": [{"key": "arrowLeft", "shift": false, "ctrl": false, "alt": false}], '
        '"keys": "←", "description": "Roll left", "available": false if the ship lacks the '
        "equipment it needs (grey it out)}, ...]}, ...]; unbound actions are left out, and "
        'unavailable ones too if the player set missing_equipment = "hide"',
    ),
    "all_keys": (
        _all_keys,
        None,
        'every key, by the game\'s groups: [{"group": "header-screen-access", "title": ..., '
        '"keys": [the same entries as key_sections, unbound ones too]}, ...]',
    ),
    "tabs": (
        _tabs,
        None,
        '{"shown": "keys", "all" or "trade", "chosen": the player\'s choice, "urgent": true '
        'while an emergency shows Keys whatever was chosen, "tabs": [{"id", "text"}, ...]}',
    ),
    "selection": (
        _selection,
        None,
        '{"commodity": open in the trade detail or null, "destination": system id or null '
        '(null = the best price), "quantity": units or null (null = the most you can buy)}',
    ),
    "market_age": (
        _market_age,
        30,
        '{"seen_at": ISO time of the newest remembered prices, "text": "5m ago"}, or null',
    ),
    "trade_rows": (
        _trade_rows,
        60,
        'one per commodity: [{"commodity": "food", "name": "Food", "unit": "t", "illegal", '
        '"stock", "here": {"price": decicredits or null, "note": "" or how old, "live"}, '
        '"best": {"price", "note", "estimate"}, "where": {"name", "distance": ly}, '
        '"margin": decicredits or null}, ...]; prices are decicredits (10 = 1 credit)',
    ),
    "trade_detail": (
        _trade_detail,
        60,
        'the open commodity, or null: {"commodity", "name", "row": as in trade_rows, '
        '"offers": [{"system_id", "name", "price", "note", "estimate", "distance", '
        '"economy", "economy_name", "government", "government_name", "dangerous", '
        '"illegal"}, ...], "chosen": system id, "limit": {"most", "reason": "on_sale", '
        '"credits", "cargo_space" or "not_sold_here", "text"}, "quantity", "steps": [text]}',
    ),
    "market_advice": (
        _market_advice,
        60,
        'Trade here, while docked: [{"heading", "lines": [{"text", "warning"}]}, ...]',
    ),
    "equipment": (
        _equipment,
        None,
        'what\'s fitted: {"items": [{"key": "EQ_ECM", "name": "E.C.M. System", '
        '"description": the game\'s own text, "count": 1, "ok": false if damaged}, ...], '
        '"missiles": {"pylons": how many, or null before the game says, "loaded": [{"key": '
        '"EQ_MISSILE", "name": "Missile", "count": 2}, ...]}}',
    ),
    "status": (
        _status,
        None,
        'the status line: {"kind": "error", "warning", "notice", "message" or null, "text"}',
    ),
}
# Not in TOPICS: "keys", the actions a plugin lists in its manifest, as
# {action: key_info}. Key names and wording come from the game's files and the
# player's settings, like everywhere else.
KEYS_TOPIC = "keys"
KEY_ACTION = re.compile(r"key_[a-z0-9_]{1,60}")


def topic_value(model, name):
    """A plugin topic's value, memoised like the model's own topics."""
    select, every, _ = TOPICS[name]
    return model.memo(f"plugin:{name}", every, select)


# -- actions -----------------------------------------------------------------
# What a plugin may send with oolite.dispatch(), if its manifest lists it in
# `actions`. The same "ui/..." actions the built-in components send; they change the
# shared UI state, so the laptop window follows a plugin's choices and back.

COMMODITY = re.compile(r"[a-z][a-z0-9_]{0,39}")


def _whole(low, high):
    return lambda v: isinstance(v, int) and not isinstance(v, bool) and low <= v <= high


ACTIONS = {
    "ui/choose_tab": {"tab": lambda v: v in TAB_IDS},
    "ui/open_commodity": {
        "commodity": lambda v: v is None or (isinstance(v, str) and bool(COMMODITY.fullmatch(v)))
    },
    "ui/choose_destination": {"system": lambda v: v is None or _whole(0, 255)(v)},
    "ui/change_quantity": {"quantity": lambda v: v is None or _whole(0, 1_000_000)(v)},
}


def check_action(action, allowed):
    """The action, rebuilt from its checked fields, if allowed has its type; else None."""
    kind = action.get("type")
    if kind not in allowed or kind not in ACTIONS:
        return None
    fields = ACTIONS[kind]
    if set(action) - {"type"} - set(fields):
        return None
    if not all(check(action.get(name)) for name, check in fields.items()):
        return None
    return {"type": kind, **{name: action.get(name) for name in fields}}


# -- the stylesheet ----------------------------------------------------------
# Served to every plugin as _oolite/theme.css. Sizes: the Tk components use points
# times the layout's scale, so calc(20pt * var(--oo-scale)) matches them.

DEV_JS = (
    "// In the web host, window.oolite comes from the helper and this file is empty.\n"
    "// In a browser preview, this file provides a fake oolite object.\n"
)


def theme_css(layout="compact", font_scale=1.0):
    scale = LAYOUTS[layout][0] * font_scale
    return f"""/* The helper's look, for plugins (#59). Use the variables; they follow its theme. */
:root {{
  --oo-bg: {BG};
  --oo-panel: {PANEL};
  --oo-fg: {FG};
  --oo-accent: {ACCENT};
  --oo-red: {RED};
  --oo-green: {GREEN};
  --oo-dim: {DIM};
  --oo-sans: "{SANS}", sans-serif;
  --oo-mono: "{MONO}", monospace;
  --oo-scale: {scale:g};
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0;
  background: var(--oo-bg);
  color: var(--oo-fg);
  font-family: var(--oo-sans);
  font-size: calc(18pt * var(--oo-scale));
}}
body {{ overflow: hidden; cursor: default; user-select: none; }}
"""
