"""Rows for the Trade tab: each commodity's price here and the best price in fuel range.

Prices are Oolite decicredits (10 = 1 credit). "Here" is the docked station's live
market, or else the remembered market for the current system. The best price in
range is a remembered real price where we have one, else the game's estimate
(SystemInfo.samplePrice), and each row says which.
"""

from dataclasses import dataclass
from datetime import datetime

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

    @property
    def margin(self):
        if self.here is None or self.best is None:
            return None
        return self.best - self.here


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
        remembered = _latest_market(markets, state.galaxy, system.get("id"))
        estimates = system.get("samplePrices") or {}
        prices = {}
        for commodity, price in estimates.items():
            prices[commodity] = (price, "est.")
        if remembered:
            note = _age(remembered, now)
            for commodity, entry in (remembered.get("prices") or {}).items():
                price = entry.get("price") if isinstance(entry, dict) else None
                if isinstance(price, (int, float)):
                    prices[commodity] = (price, note)
        for commodity, (price, note) in prices.items():
            if not isinstance(price, (int, float)):
                continue
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
