"""Persist market snapshots and the player's average commodity cost basis."""

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
        self.data.setdefault("cost_basis", {})
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
        if self.path.exists() and (
            previous_markets != self.data["markets"]
            or previous_market_events != self.data["market_events"]
            or previous_trade_events != self.data["trade_events"]
            or had_source_events
        ):
            self._save()

    def _load(self):
        """The saved data, or a fresh store if the file is missing or damaged.

        A damaged file is kept as markets.json.bad rather than overwritten.
        """
        empty = {"version": 1, "markets": [], "cost_basis": {}}
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return empty
        except (OSError, ValueError) as exc:
            return self._set_aside(empty, exc)
        list_keys = ("markets", "market_events", "trade_events")
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("cost_basis", {}), dict)
            or any(not isinstance(data.get(key, []), list) for key in list_keys)
        ):
            return self._set_aside(empty, "unexpected layout")
        return data

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
        if kind not in ("market", "bought", "sold"):
            return
        if kind == "market" and isinstance(message.get("market"), dict):
            self._record_market(message)
        elif kind in ("bought", "sold"):
            self._record_trade(message)

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
            "seen_at": self.now().astimezone(UTC).isoformat(),
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

    def _reconcile_manifest(self, manifest):
        if not isinstance(manifest, list):
            return
        held = {}
        for item in manifest:
            if not isinstance(item, dict):
                continue
            commodity = item.get("commodity", item.get("name"))
            quantity = item.get("quantity")
            if isinstance(commodity, str) and self._valid_number(quantity) and quantity > 0:
                held[commodity] = held.get(commodity, 0) + quantity
        for commodity, current in list(self.data["cost_basis"].items()):
            quantity = held.get(commodity, 0)
            if quantity <= 0:
                del self.data["cost_basis"][commodity]
            elif quantity < current["units"]:
                average = current["total_cost"] / current["units"]
                current["units"] = quantity
                current["total_cost"] = quantity * average
                current["average_price"] = average

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

        basis = self.data["cost_basis"]
        current = basis.get(commodity)
        if message["type"] == "bought":
            held = current["units"] if current else 0
            total_cost = current["total_cost"] if current else 0
            held += units
            total_cost += units * price
        else:
            if not current:
                self._remember_trade(event_key)
                return
            held = current["units"]
            total_cost = current["total_cost"]
            if held <= 0:
                self._remember_trade(event_key)
                return
            sold = min(units, held)
            held -= sold
            total_cost -= sold * (total_cost / current["units"])
            if held <= 1e-12:
                held = 0
                total_cost = 0

        basis[commodity] = {
            "units": held,
            "total_cost": total_cost,
            "average_price": total_cost / held if held else 0,
        }
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
