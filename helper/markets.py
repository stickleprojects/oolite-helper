"""Persist market snapshots and what the player bought: each purchase (lot).

Lots (#95): each commodity in the hold is a list of lots, oldest first:
{"units", "price", "galaxy", "system_id", "system_name", "game_clock",
"seen_at", "from"}. "from" is "bought", "scooped" (units that appeared in the
hold with no purchase, price None) or "unknown" (held before the helper knew,
or a version 1 file's average). Selling, dumping or losing cargo uses up the
oldest lot first. The average price per commodity (cost_basis) comes from the
priced lots, as version 1 kept it.
"""

import json
import math
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PATH = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "oolite-helper"
    / "markets.json"
)
MAX_TRADE_EVENTS = 500
MAX_MARKET_EVENTS = 500
MAX_HOLD_EVENTS = 500


class MarketStore:
    def __init__(self, path=PATH, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(UTC))
        self.load_error = None  # shown in the status line when the saved file was unusable
        self.data = self._load()
        previous_markets = self.data.get("markets", [])
        previous_market_events = self.data.get("market_events", [])
        previous_trade_events = self.data.get("trade_events", [])
        had_source_events = "source_events" in self.data
        self.data.setdefault("markets", [])
        migrated = self._migrate()
        self.data.pop("source_events", None)
        self.data["market_events"] = self.data.get("market_events", [])[-MAX_MARKET_EVENTS:]
        self.data["markets"] = list(
            {
                self._market_location(market): market
                for market in self.data["markets"]
                if isinstance(market, dict)
            }.values()
        )
        self.data["trade_events"] = self.data.get("trade_events", [])[-MAX_TRADE_EVENTS:]
        self.data["hold_events"] = self.data.get("hold_events", [])[-MAX_HOLD_EVENTS:]
        if self.path.exists() and (
            previous_markets != self.data["markets"]
            or previous_market_events != self.data["market_events"]
            or previous_trade_events != self.data["trade_events"]
            or had_source_events
            or migrated
        ):
            self._save()

    def _load(self):
        """The saved data, or a fresh store if the file is missing or damaged.

        A damaged file is kept as markets.json.bad rather than overwritten.
        """
        empty = {"version": 2, "markets": [], "lots": {}}
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return empty
        except (OSError, ValueError) as exc:
            return self._set_aside(empty, exc)
        list_keys = ("markets", "market_events", "trade_events", "hold_events")
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("cost_basis", {}), dict)
            or not isinstance(data.get("lots", {}), dict)
            or any(not isinstance(data.get(key, []), list) for key in list_keys)
        ):
            return self._set_aside(empty, "unexpected layout")
        return data

    def _migrate(self):
        """Version 1 kept one average per commodity: read it as one lot of
        unknown origin. True if the data changed."""
        if "lots" in self.data and "cost_basis" not in self.data:
            return False
        lots = self.data.setdefault("lots", {})
        for commodity, basis in (self.data.pop("cost_basis", None) or {}).items():
            units = basis.get("units") if isinstance(basis, dict) else None
            if commodity not in lots and self._valid_number(units) and units > 0:
                price = basis.get("average_price")
                lots[commodity] = [self._lot(units, price if self._valid_number(price) else None)]
        self.data["version"] = 2
        return True

    @staticmethod
    def _lot(units, price, where=None, origin="unknown", seen_at=None):
        where = where or {}
        return {
            "units": units,
            "price": price,
            "galaxy": where.get("galaxy"),
            "system_id": where.get("systemID"),
            "system_name": where.get("systemName"),
            "game_clock": where.get("gameClock"),
            "seen_at": seen_at,
            "from": origin,
        }

    def _use_up(self, commodity, units):
        """Take units of a commodity out of its lots, oldest first."""
        lots = self.data["lots"].get(commodity, [])
        while units > 1e-9 and lots:
            taken = min(units, lots[0]["units"])
            lots[0]["units"] -= taken
            units -= taken
            if lots[0]["units"] <= 1e-9:
                lots.pop(0)
        if not lots:
            self.data["lots"].pop(commodity, None)

    def held_lots(self, commodity):
        """The units of a commodity the lots account for."""
        return sum(lot["units"] for lot in self.data["lots"].get(commodity, []))

    @property
    def cost_basis(self):
        """{commodity: {"units", "total_cost", "average_price"}} from the priced lots."""
        basis = {}
        for commodity, lots in self.data["lots"].items():
            priced = [lot for lot in lots if lot["price"] is not None]
            units = sum(lot["units"] for lot in priced)
            if units <= 0:
                continue
            total = sum(lot["units"] * lot["price"] for lot in priced)
            basis[commodity] = {"units": units, "total_cost": total, "average_price": total / units}
        return basis

    def _set_aside(self, empty, reason):
        bad = self.path.with_name(self.path.name + ".bad")
        try:
            os.replace(self.path, bad)
        except OSError:
            bad = None
        kept = f" (kept as {bad.name})" if bad else ""
        self.load_error = f"Saved market data was unreadable{kept}; starting fresh: {reason}"
        return empty

    def apply(self, message):
        kind = message.get("type")
        if kind == "market" and isinstance(message.get("market"), dict):
            self._record_market(message)
        elif kind in ("bought", "sold"):
            self._record_trade(message)
        elif kind == "hold":
            self._record_hold(message)

    def _record_market(self, message):
        identity = self._market_identity(message)
        if identity is None:
            return
        event_key = json.dumps(identity, separators=(",", ":"), ensure_ascii=False)
        if event_key in self.data["market_events"]:
            return
        location = identity[:3]
        existing = next(
            (
                market
                for market in self.data["markets"]
                if self._market_location(market) == location
            ),
            None,
        )
        snapshot = {
            "galaxy": message.get("galaxy"),
            "system_id": message.get("systemID"),
            "system_name": message.get("systemName"),
            "game_clock": message.get("gameClock"),
            "station": message.get("station"),
            "seen_at": self._now_text(),
            "prices": message["market"],
        }
        if existing:
            existing.update(snapshot)
        else:
            self.data["markets"].append(snapshot)
        self.data["market_events"].append(event_key)
        self.data["market_events"] = self.data["market_events"][-MAX_MARKET_EVENTS:]
        self._reconcile_manifest(message.get("manifest"))
        self._save()

    @staticmethod
    def _market_identity(message):
        values = (
            message.get("galaxy"),
            message.get("systemID"),
            message.get("station"),
            message.get("gameClock"),
        )
        return values if all(value is not None for value in values) else None

    @staticmethod
    def _market_location(market):
        return market.get("galaxy"), market.get("system_id"), market.get("station")

    def _held(self, manifest):
        """{commodity: units} in a manifest; None if it isn't one."""
        if not isinstance(manifest, list):
            return None
        held = {}
        for item in manifest:
            if not isinstance(item, dict):
                continue
            commodity = item.get("commodity", item.get("name"))
            quantity = item.get("quantity")
            if isinstance(commodity, str) and self._valid_number(quantity) and quantity > 0:
                held[commodity] = held.get(commodity, 0) + quantity
        return held

    def _reconcile_manifest(self, manifest, add=None):
        """Use up lots the hold no longer has, oldest first. With add (a lot's
        "from"), also add an unpriced lot for units the lots don't account for.
        True if the lots changed."""
        held = self._held(manifest)
        if held is None:
            return False
        before = json.dumps(self.data["lots"], sort_keys=True)
        for commodity in list(self.data["lots"]):
            extra = self.held_lots(commodity) - held.get(commodity, 0)
            if extra > 1e-9:
                self._use_up(commodity, extra)
        if add:
            for commodity, units in held.items():
                missing = units - self.held_lots(commodity)
                if missing > 1e-9:
                    lot = self._lot(missing, None, origin=add, seen_at=self._now_text())
                    self.data["lots"].setdefault(commodity, []).append(lot)
        return json.dumps(self.data["lots"], sort_keys=True) != before

    def _record_hold(self, message):
        """A hold message (#95): the goods aboard, less the cargo that belongs
        to contracts (it's in the manifest too, but wasn't bought).

        Each is applied once: the helper reads Latest.log from the start when it
        starts, and replaying an old hold against today's lots would use up the
        wrong ones (as trades, which _trade_identity keeps from repeating)."""
        goods = self._held(message.get("goods"))
        if goods is None:
            return
        event_key = json.dumps(
            [message.get(key) for key in ("cause", "gameClock", "goods", "contracts")],
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )
        if event_key in self.data["hold_events"]:
            return
        self.data["hold_events"].append(event_key)
        self.data["hold_events"] = self.data["hold_events"][-MAX_HOLD_EVENTS:]
        for contract in message.get("contracts") or ():
            commodity = contract.get("commodity") if isinstance(contract, dict) else None
            if commodity in goods and self._valid_number(contract.get("quantity")):
                goods[commodity] = max(0, goods[commodity] - contract["quantity"])
        manifest = [{"commodity": c, "quantity": q} for c, q in goods.items() if q > 0]
        origin = "scooped" if message.get("cause") == "scooped" else "unknown"
        self._reconcile_manifest(manifest, add=origin)
        self._save()

    def _now_text(self):
        return self.now().astimezone(UTC).isoformat()

    def _record_trade(self, message):
        commodity = message.get("commodity")
        units = message.get("units")
        price = message.get("price")
        event_key = self._trade_identity(message)
        if (
            not isinstance(commodity, str)
            or not commodity
            or not self._valid_number(units)
            or units <= 0
            or not self._valid_number(price)
            or price < 0
            or event_key is None
        ):
            return
        if event_key in self.data["trade_events"]:
            return

        if message["type"] == "bought":
            lot = self._lot(units, price, message, "bought", self._now_text())
            self.data["lots"].setdefault(commodity, []).append(lot)
        else:
            self._use_up(commodity, units)
        self._remember_trade(event_key)

    @staticmethod
    def _trade_identity(message):
        values = (
            message.get("type"),
            message.get("galaxy"),
            message.get("systemID"),
            message.get("gameClock"),
            message.get("commodity"),
            message.get("units"),
            message.get("price"),
        )
        if any(value is None for value in values):
            return None
        return json.dumps(values, separators=(",", ":"), ensure_ascii=False)

    def _remember_trade(self, event_key):
        self.data["trade_events"].append(event_key)
        self.data["trade_events"] = self.data["trade_events"][-MAX_TRADE_EVENTS:]
        self._save()

    @staticmethod
    def _valid_number(value):
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=2, ensure_ascii=False)
                file.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @property
    def price_seen(self):
        """When the newest remembered prices were seen, or None."""
        if not self.data["markets"]:
            return None
        try:
            return max(datetime.fromisoformat(market["seen_at"]) for market in self.data["markets"])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def price_age(self):
        seen = self.price_seen
        return None if seen is None else age_text(seen, self.now())


def age_text(seen, now):
    """How long ago a datetime was, e.g. "just now", "5m ago", "2h ago", "3d ago"."""
    seconds = max(0, int((now.astimezone(UTC) - seen).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"
