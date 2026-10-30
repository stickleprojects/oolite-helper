"""The hold topic (#95): everything aboard, from the last hold message, with
each commodity split into the lots it was bought in (markets.MarketStore).

Goods are worth what the last market seen pays for them. Prices are
decicredits (10 = 1 credit), as the market sends them; contract fees are
credits, as the game keeps them (PlayerEntityContracts.m, 1.92.1).

A contract's "eta" is the time left when the hold was sent: the game sends
arrival time minus ship clock (PlayerEntity contractsListForScriptingFromArray:,
1.92.1). So time left is eta less the game time passed since that message.
"""

from datetime import datetime

from .markets import age_text

PEOPLE_FIELDS = ("name", "destination", "destinationName", "fee", "risk")
CONTRACT_FIELDS = ("commodity", "quantity", "destination", "destinationName", "fee")


def time_text(seconds):
    """Time left as the player reads it: "2d 3h", "5h 20m", "12m", or "late 1h"."""
    late = seconds < 0
    seconds = abs(int(seconds))
    days, hours, minutes = seconds // 86400, seconds // 3600 % 24, seconds // 60 % 60
    if days:
        text = f"{days}d {hours}h"
    elif hours:
        text = f"{hours}h {minutes}m"
    else:
        text = f"{minutes}m"
    return f"late {text}" if late else text


def _number(value):
    return isinstance(value, int | float) and not isinstance(value, bool)


def _from(lot):
    if lot.get("from") == "scooped":
        return "scooped"
    if lot.get("from") != "bought" or lot.get("system_name") is None:
        return None
    return {"galaxy": lot.get("galaxy"), "system": lot.get("system_id"), "name": lot["system_name"]}


def _good(commodity, name, unit, units, price, origin, worth_each):
    paid = None if price is None else units * price
    worth = None if worth_each is None else units * worth_each
    return {
        "commodity": commodity,
        "name": name,
        "units": units,
        "unit": unit,
        "paid_each": price,
        "paid": paid,
        "from": origin,
        "worth_each": worth_each,
        "worth": worth,
        "profit": None if paid is None or worth is None else worth - paid,
    }


def goods(message, lots, prices, name):
    """One row per lot, oldest first by commodity, for the goods the hold
    message lists (less what contracts carry). Units the lots don't account
    for get a row of unknown origin."""
    contracted = {}
    for contract in message.get("contracts") or ():
        if isinstance(contract, dict) and _number(contract.get("quantity")):
            commodity = contract.get("commodity")
            contracted[commodity] = contracted.get(commodity, 0) + contract["quantity"]
    rows = []
    for item in message.get("goods") or ():
        commodity = item.get("commodity") if isinstance(item, dict) else None
        quantity = item.get("quantity") if commodity else None
        if not _number(quantity):
            continue
        left = quantity - contracted.get(commodity, 0)
        entry = prices.get(commodity)
        worth_each = entry.get("price") if isinstance(entry, dict) else None
        worth_each = worth_each if _number(worth_each) else None
        title = name(commodity)
        unit = item.get("unit") or "t"
        for lot in lots.get(commodity, ()):
            units = min(left, lot["units"])
            if units <= 0:
                break
            rows.append(_good(commodity, title, unit, units, lot["price"], _from(lot), worth_each))
            left -= units
        if left > 0:
            rows.append(_good(commodity, title, unit, left, None, None, worth_each))
    return rows


def _timed(entry, fields, passed):
    row = {field: entry.get(field) for field in fields}
    eta = entry.get("eta")
    row["time_left"] = eta - passed if _number(eta) else None
    row["time_left_text"] = None if row["time_left"] is None else time_text(row["time_left"])
    row["late"] = row["time_left"] is not None and row["time_left"] < 0
    return row


def hold(message, game_clock, lots, market, now, name):
    """The hold topic, or None before the first hold message.

    game_clock: the game's clock now, as best known (GameState.game_clock_now);
    market: the newest remembered market, or None; now: a UTC datetime."""
    if not message:
        return None
    sent = message.get("gameClock")
    passed = game_clock - sent if _number(sent) and _number(game_clock) else 0
    prices = (market or {}).get("prices") or {}
    space = message.get("space") or {}
    worth_at = None
    if market:
        try:
            age = age_text(datetime.fromisoformat(market["seen_at"]), now)
        except (KeyError, TypeError, ValueError):
            age = None
        worth_at = {
            "system": market.get("system_name"),
            "station": market.get("station"),
            "age": age,
        }
    lists = {
        kind: [_timed(e, fields, passed) for e in message.get(kind) or () if isinstance(e, dict)]
        for kind, fields in (
            ("passengers", PEOPLE_FIELDS),
            ("parcels", PEOPLE_FIELDS),
            ("contracts", CONTRACT_FIELDS),
        )
    }
    for contract in lists["contracts"]:
        contract["name"] = name(contract["commodity"]) if contract["commodity"] else None
    return {
        "goods": goods(message, lots, prices, name),
        **lists,
        "space": {"used": space.get("used"), "capacity": space.get("capacity")},
        "worth_at": worth_at,
    }
