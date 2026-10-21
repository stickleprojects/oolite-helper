"""Persist market snapshots and the player's average commodity cost basis."""

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile


PATH = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) \
    / "oolite-helper" / "markets.json"


class MarketStore:
    def __init__(self, path=PATH, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.data = {"version": 1, "markets": [], "cost_basis": {}}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as file:
                self.data = json.load(file)
        self.data.setdefault("markets", [])
        self.data.setdefault("cost_basis", {})
        self.data.setdefault("source_events", [])

    def apply(self, message):
        kind = message.get("type")
        if kind not in ("market", "bought", "sold"):
            return
        source_id = message.get("_source_id")
        if source_id and source_id in self.data["source_events"]:
            return
        changed = False
        if kind == "market" and isinstance(message.get("market"), dict):
            self._record_market(message)
            changed = True
        elif kind in ("bought", "sold"):
            changed = self._record_trade(message)
        if changed:
            if source_id:
                self.data["source_events"].append(source_id)
            self._save()

    def _record_market(self, message):
        self.data["markets"].append({
            "galaxy": message.get("galaxy"),
            "system_id": message.get("systemID"),
            "system_name": message.get("systemName"),
            "game_clock": message.get("gameClock"),
            "station": message.get("station"),
            "seen_at": self.now().astimezone(timezone.utc).isoformat(),
            "prices": message["market"],
        })

    def _record_trade(self, message):
        commodity = message.get("commodity")
        units = message.get("units")
        price = message.get("price")
        if not isinstance(commodity, str) or not commodity \
                or not self._valid_number(units) or units <= 0 \
                or not self._valid_number(price) or price < 0:
            return False

        basis = self.data["cost_basis"]
        current = basis.get(commodity)
        if message["type"] == "bought":
            held = current["units"] if current else 0
            total_cost = current["total_cost"] if current else 0
            held += units
            total_cost += units * price
        else:
            if not current:
                return False
            held = current["units"]
            total_cost = current["total_cost"]
            if held <= 0:
                return False
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
        return True

    @staticmethod
    def _valid_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) \
            and math.isfinite(value)

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
    def price_age(self):
        if not self.data["markets"]:
            return None
        try:
            seen = datetime.fromisoformat(self.data["markets"][-1]["seen_at"])
            now = self.now().astimezone(timezone.utc)
            seconds = max(0, int((now - seen).total_seconds()))
        except (KeyError, TypeError, ValueError):
            return None
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
