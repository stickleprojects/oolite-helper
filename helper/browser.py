"""Rows for the Trade tab: each commodity's price here and the best price in fuel range.

Prices are Oolite decicredits (10 = 1 credit). "Here" is the docked station's live
market, or else the remembered market for the current system. The best price in
range is a remembered real price where we have one, else the game's estimate
(SystemInfo.samplePrice), and each row says which.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from .markets import age_text
from .trade import is_illegal


@dataclass(frozen=True)
class Row:
    commodity: str
    here: int | None  # price here, decicredits
    here_note: str  # "" for the live market, else how old the remembered price is
    stock: int | None  # units on sale here
    illegal: bool  # illegal to trade here
    best: int | None  # best price within fuel range
    best_note: str  # "est." for an estimate, else how old the remembered price is
    where: str  # system with the best price
    distance: float | None
    unit: str = "t"  # mass unit the commodity is sold in

    @property
    def margin(self):
        if self.here is None or self.best is None:
            return None
        return self.best - self.here


@dataclass(frozen=True)
class Offer:
    """One system's price for a commodity."""

    system_id: int | None
    name: str
    price: int  # decicredits
    note: str  # "est." for an estimate, else how old the remembered price is
    distance: float | None
    economy: int | None
    government: int | None
    illegal: bool | None  # None when only an estimate is known

    @property
    def dangerous(self):
        return self.government in DANGEROUS


class Limit(NamedTuple):
    most: int
    reason: str  # "on sale", "credits", "cargo space" or "not sold here"


UNITS = {"0": "t", "1": "kg", "2": "g"}
DANGEROUS = (0, 1)  # Anarchy, Feudal

SORT_KEYS = {
    "commodity": lambda row: row.commodity,
    "here": lambda row: row.here,
    "best": lambda row: row.best,
    "where": lambda row: row.distance,
    "margin": lambda row: row.margin,
}


def commodity_rows(state, markets, now):
    """One Row per commodity seen here or estimated anywhere in range."""
    here_market, here_note = _here_market(state, markets, now)
    best = {}  # commodity -> (price, note, system name, distance)
    for system in state.systems or []:
        for commodity, (price, note, _) in _system_prices(system, markets, state, now).items():
            current = best.get(commodity)
            if current is None or price > current[0]:
                best[commodity] = (price, note, system.get("name", "?"), system.get("distance"))

    rows = []
    for commodity in sorted(set(here_market) | set(best)):
        entry = here_market.get(commodity)
        entry = entry if isinstance(entry, dict) else {}
        price = entry.get("price")
        best_price, best_note, where, distance = best.get(commodity, (None, "", "", None))
        rows.append(
            Row(
                commodity=commodity,
                here=price if isinstance(price, (int, float)) else None,
                here_note=here_note if entry else "",
                stock=entry.get("quantity"),
                illegal=is_illegal(entry),
                best=best_price,
                best_note=best_note,
                where=where,
                distance=distance,
                unit=unit(entry),
            )
        )
    return rows


def sort_rows(rows, key="margin", descending=True):
    """Rows ordered by a column; rows with no value for it always go last."""
    value = SORT_KEYS[key]
    known = [row for row in rows if value(row) is not None]
    unknown = [row for row in rows if value(row) is None]
    known.sort(key=value, reverse=descending)
    return known + unknown


def commodity_offers(state, markets, now, commodity):
    """Every system in range with its price for one commodity, best price first."""
    offers = []
    for system in state.systems or []:
        found = _system_prices(system, markets, state, now).get(commodity)
        if found is None:
            continue
        price, note, entry = found
        offers.append(
            Offer(
                system_id=system.get("id"),
                name=system.get("name", "?"),
                price=price,
                note=note,
                distance=system.get("distance"),
                economy=system.get("economy"),
                government=system.get("government"),
                illegal=is_illegal(entry) if entry is not None else None,
            )
        )
    offers.sort(key=lambda offer: (-offer.price, offer.distance or 0))
    return offers


def buy_limit(state, markets, now, commodity):
    """The most units the player can buy here, and what limits it.

    Follows tryBuyingCommodity:all: (PlayerEntity.m, 1.92.1): what's on sale,
    then what the credits cover, then free cargo space for goods sold in tons.
    Goods in kg and g go in the safe and aren't limited by cargo space.
    """
    entry = _here_market(state, markets, now)[0].get(commodity)
    if not isinstance(entry, dict) or not entry.get("price"):
        return Limit(0, "not sold here")
    most, reason = int(entry.get("quantity") or 0), "on sale"
    if isinstance(state.credits, (int, float)):
        # player.credits is in credits; prices are decicredits.
        affordable = int(round(state.credits * 10)) // entry["price"]
        if affordable < most:
            most, reason = affordable, "credits"
    space = (state.cargo_space or {}).get("available")
    if unit(entry) == "t" and isinstance(space, (int, float)) and space < most:
        most, reason = int(space), "cargo space"
    return Limit(max(0, most), reason)


def unit(entry):
    """The mass unit a market entry is sold in: "t", "kg" or "g"."""
    return UNITS.get(str(entry.get("quantity_unit", "0")), "t") if isinstance(entry, dict) else "t"


def held(state, commodity):
    """Units of a commodity in the player's hold, from the last manifest."""
    return sum(
        item.get("quantity") or 0
        for item in state.manifest or []
        if isinstance(item, dict) and item.get("commodity") == commodity
    )


def trade_steps(keys, name, quantity, most, offer, state, holding=0):
    """What to press in the game to make the trade, using the player's own keys.

    Buying and selling read the GUI arrow keys, Shift for all (PlayerEntityControls.m,
    1.92.1); key_market_buy_one and friends are loaded but never checked there.
    Steps already done (bought, destination targeted, launched) are left out.
    """
    right = _first(keys("key_gui_arrow_right"))
    left = _first(keys("key_gui_arrow_left"))
    move = f"{_first(keys('key_gui_arrow_up'))} / {_first(keys('key_gui_arrow_down'))}"
    market = keys("key_gui_market")
    docked = bool(state.docked)
    steps = []
    if holding:
        steps.append(f"You hold {holding} {name}.")
    if quantity > 0:
        more = " more" if holding else ""
        buy = (
            f"Shift+{right} buys the most you can ({quantity}{more})"
            if quantity == most
            else f"{right} ×{quantity}{more}"
        )
        if not docked:
            steps.append("Dock at a station: you can only buy while docked.")
        steps.append(f"Market {market} → {move} to {name} → {buy}")
    elif not holding:
        steps.append(f"Nothing to buy: {name} isn't affordable or on sale here.")
        return steps
    if offer is None:
        return steps
    if offer.system_id != state.current_system:
        if offer.system_id != state.target_system:
            steps.append(
                f"Chart {keys('key_gui_chart_screens')} → move the cursor to {offer.name} "
                "(on the galactic chart you can type its name)"
            )
        launch = f"Launch {keys('key_launch_ship')}, fly" if docked else "Fly"
        steps.append(
            f"{launch} until the station is off the scanner (closer, it blocks the jump), "
            f"then {keys('key_hyperspace')} jumps to {offer.name} after a countdown "
            "(press it again to cancel)"
        )
        steps.append(
            f"At {offer.name}: target the station ({keys('key_ident_system')} with it ahead, "
            f"or {keys('key_next_target')}), {keys('key_docking_clearance_request')} for "
            f"clearance, {keys('key_autopilot')} for the docking computer"
        )
    steps.append(f"Docked at {offer.name}: Market {market} → {name} → Shift+{left} sells all")
    return steps


def market_advice(state, markets, cost_basis, now, name, places=3):
    """The docked market panel: [(heading, [line, ...]), ...].

    Profit on the hold at today's prices, prices against the last market seen,
    the hold and best buys at the jump destination, and the best buys for any
    system in range ranked by total profit (margin x units you can buy).
    """
    here = state.market if state.docked and isinstance(state.market, dict) else None
    if here is None:
        return []

    def price_here(commodity):
        entry = here.get(commodity)
        return entry.get("price") if isinstance(entry, dict) else None

    groups = []
    hold = []
    for item in state.manifest or []:
        commodity, quantity = item.get("commodity"), item.get("quantity") or 0
        price = price_here(commodity)
        if not quantity or price is None:
            continue
        basis = (cost_basis or {}).get(commodity) or {}
        paid = basis.get("average_price") or None
        # What you'd make, against what you paid where known, else today's price here.
        base = paid if paid else price
        line = f"{name(commodity)} ×{quantity}"
        line += (
            f": paid {_cr(paid)}, sells for {_cr(price)} here" if paid else f": {_cr(price)} here"
        )
        if paid and price != paid:
            line += f" ({_signed((price - paid) * quantity)} cr)"
        best = next(
            (o for o in commodity_offers(state, markets, now, commodity) if o.price > base), None
        )
        if best is not None:
            line += (
                f". Best: {_system_text(best)} at {_cr(best.price)} ({best.note}), "
                f"{_signed((best.price - base) * quantity)} cr"
            )
        else:
            line += ". Nowhere in range pays more"
        hold.append(line)
    if hold:
        groups.append(("Your hold", hold))

    last = _last_other_market(markets, state)
    if last:
        changes = []
        for commodity, entry in (last.get("prices") or {}).items():
            then = entry.get("price") if isinstance(entry, dict) else None
            now_price = price_here(commodity)
            if isinstance(then, (int, float)) and now_price is not None and then != now_price:
                changes.append((now_price - then, commodity))
        changes.sort()
        cheaper = [f"{name(c)} {_signed(d)}" for d, c in changes[:places] if d < 0]
        dearer = [f"{name(c)} {_signed(d)}" for d, c in reversed(changes[-places:]) if d > 0]
        where = f"{last.get('system_name') or 'last market'} ({_age(last, now)})"
        lines = []
        if cheaper:
            lines.append("Cheaper here: " + ", ".join(cheaper))
        if dearer:
            lines.append("Dearer here: " + ", ".join(dearer))
        if lines:
            groups.append((f"Against {where}", lines))

    offers = {}  # commodity -> [Offer, ...]
    for commodity in here:
        offers[commodity] = commodity_offers(state, markets, now, commodity)

    target = state.target_system
    if target is not None and target != state.current_system:
        lines = []
        destination = None
        for commodity in sorted(here):
            offer = next((o for o in offers[commodity] if o.system_id == target), None)
            price = price_here(commodity)
            if offer is None or price is None:
                continue
            destination = offer
            holding = held(state, commodity)
            if holding:
                lines.append(
                    f"Sell {name(commodity)} ×{holding} at {_cr(offer.price)} "
                    f"({offer.note}): {_signed((offer.price - price) * holding)} cr vs here"
                )
        buys = _ranked_buys(state, markets, now, here, offers, name, only=target)
        lines += [f"Buy {line}" for line in buys[:places]]
        if destination is not None and lines:
            groups.append((f"For {_system_text(destination)}", lines))

    # Buys whose best price is at the destination are already listed above.
    skip = target if target != state.current_system else None
    best = _ranked_buys(state, markets, now, here, offers, name, skip=skip)
    if best:
        groups.append(("Best buys you can still afford and fit", best[:places]))
    return groups


def _ranked_buys(state, markets, now, here, offers, name, only=None, skip=None):
    """Lines for profitable buys here, best total profit first."""
    ranked = []
    for commodity, entry in here.items():
        if not isinstance(entry, dict) or not entry.get("price"):
            continue
        choices = [o for o in offers[commodity] if only is None or o.system_id == only]
        if not choices:
            continue
        offer = choices[0]
        if skip is not None and offer.system_id == skip:
            continue
        margin = offer.price - entry["price"]
        most = buy_limit(state, markets, now, commodity).most
        if margin <= 0 or most <= 0:
            continue
        illegal = "  illegal" if is_illegal(entry) else ""
        where = "" if only is not None else f" → {_system_text(offer)}"
        ranked.append(
            (
                margin * most,
                f"{name(commodity)}{illegal}: {_signed(margin)}/{unit(entry)} × {most} = "
                f"{_signed(margin * most)} cr ({offer.note}){where}",
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [line for _, line in ranked]


def _system_text(offer):
    distance = f" {offer.distance:.1f} ly" if offer.distance is not None else ""
    danger = " ⚠" if offer.dangerous else ""
    return f"{offer.name}{distance}{danger}"


def _last_other_market(markets, state):
    """The most recently seen market anywhere but this station."""
    here = (state.galaxy, state.current_system, state.market_station)
    others = [m for m in markets if (m.get("galaxy"), m.get("system_id"), m.get("station")) != here]
    return max(others, key=lambda m: m.get("seen_at") or "", default=None)


def _cr(decicredits):
    return f"{decicredits / 10:.1f}"


def _signed(decicredits):
    return f"{decicredits / 10:+.1f}"


def _first(keys_text):
    return keys_text.split(" / ")[0] if keys_text else "(unbound)"


def _system_prices(system, markets, state, now):
    """commodity -> (price, note, market entry or None) for one system in range.

    A remembered real price wins over the game's estimate.
    """
    prices = {}
    for commodity, price in (system.get("samplePrices") or {}).items():
        if isinstance(price, (int, float)):
            prices[commodity] = (price, "est.", None)
    remembered = _latest_market(markets, state.galaxy, system.get("id"))
    if remembered:
        note = _age(remembered, now)
        for commodity, entry in (remembered.get("prices") or {}).items():
            price = entry.get("price") if isinstance(entry, dict) else None
            if isinstance(price, (int, float)):
                prices[commodity] = (price, note, entry)
    return prices


def _here_market(state, markets, now):
    if state.docked and isinstance(state.market, dict):
        return state.market, ""
    remembered = _latest_market(markets, state.galaxy, state.current_system)
    if remembered:
        return remembered.get("prices") or {}, _age(remembered, now)
    return {}, ""


def _latest_market(markets, galaxy, system_id):
    if galaxy is None or system_id is None:
        return None
    seen = [
        market
        for market in markets
        if market.get("galaxy") == galaxy and market.get("system_id") == system_id
    ]
    return max(seen, key=lambda market: market.get("seen_at") or "", default=None)


def _age(market, now):
    try:
        return age_text(datetime.fromisoformat(market["seen_at"]), now)
    except (KeyError, TypeError, ValueError):
        return "remembered"
