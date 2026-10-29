import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from helper.contexts import clearance_badge, tip
from helper.markets import MarketStore
from helper.sources import LogSource
from helper.state import GameState
from tests.fakegame import LogWriter, load_scenario, run_scenario

ROOT = Path(__file__).resolve().parents[1]


class FakeKeymap:
    def keys(self, action):
        return "K"


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.keymap = FakeKeymap()

    def test_docking_messages_update_context_clearance_badge_and_tips(self):
        state = GameState()
        expected = [
            ("docked", None, ""),
            ("flying", None, ""),
            (
                "near station",
                "No clearance",
                "K asks your current target, so target the station first (K with it ahead, or K).",
            ),
            (
                "near station",
                "Waiting for clearance",
                "Waiting for clearance. Pressing K again cancels the request.",
            ),
            (
                "near station",
                "Cleared to dock",
                "Cleared to dock. Pressing K again cancels clearance.",
            ),
            (
                "near station",
                "Clearance expiring: press K to extend",
                "Clearance is about to expire: press K now to extend it.",
            ),
            (
                "near station",
                "No clearance",
                "K asks your current target, so target the station first (K with it ahead, or K).",
            ),
            ("docked", None, ""),
        ]
        steps = load_scenario(ROOT / "scenarios" / "docking.yaml")
        self.assertEqual(len(steps), len(expected))
        for step, (context, badge, expected_tip) in zip(steps, expected, strict=True):
            state.apply(step["msg"])
            self.assertEqual(state.context, context)
            shown = clearance_badge(state, self.keymap)
            self.assertEqual(shown and shown[0], badge)
            self.assertEqual(tip(state, self.keymap), expected_tip)

    def test_jump_messages_update_context_details_and_tip(self):
        state = GameState()
        expected_contexts = [
            "flying",
            "menu",
            "flying",
            "jump countdown",
            "flying",
            "jump countdown",
            "flying",
            "flying",
        ]
        steps = load_scenario(ROOT / "scenarios" / "jump.yaml")
        self.assertEqual(len(steps), len(expected_contexts))
        with patch("helper.state.time.monotonic", return_value=100):
            for step, context in zip(steps, expected_contexts, strict=True):
                state.apply(step["msg"])
                self.assertEqual(state.context, context)
                if context == "jump countdown":
                    countdown = step["msg"]
                    expected_detail = (
                        "Galactic jump in 20s" if countdown["kind"] == "galactic" else "Jump in 15s"
                    )
                    self.assertEqual(state.details[0], expected_detail)
                    self.assertEqual(
                        tip(state, self.keymap), "Press K again to cancel the countdown."
                    )
                else:
                    self.assertEqual(state.details, [])
                    self.assertEqual(tip(state, self.keymap), "")

    def test_trade_scenario_updates_market_system_and_chart_state(self):
        state = GameState()
        for step in load_scenario(ROOT / "scenarios" / "trade.yaml"):
            state.apply(step["msg"])

        self.assertEqual(state.market_station, "Lave Station")
        self.assertEqual(state.market["food"]["price"], 42)
        self.assertEqual(state.credits, 1200.5)
        self.assertEqual(state.cargo_space, {"available": 18, "capacity": 35})
        self.assertEqual(state.manifest[0]["commodity"], "food")
        self.assertEqual(state.last_trade["type"], "sold")
        self.assertEqual(state.last_trade["units"], 1)
        self.assertEqual([system["name"] for system in state.systems], ["Zaonce"])
        self.assertEqual(state.fuel, 7)
        self.assertEqual(state.info_system, 8)
        self.assertEqual(state.target_system, 9)
        self.assertEqual(state.chart_system["name"], "Zaonce")
        self.assertEqual(state.current_system, 7)
        self.assertEqual(state.origin_market["food"]["price"], 42)

    def test_chart_advice_estimates_trades_and_nearest_economies(self):
        state = GameState()
        state.apply({"type": "gui", "to": "GUI_SCREEN_LONG_RANGE_CHART"})
        state.apply(
            {
                "type": "systems",
                "fuel": 7,
                "systems": [
                    {"name": "Near Ag", "distance": 2.2, "economy": 5},
                    {"name": "Far Ag", "distance": 6.0, "economy": 4},
                    {"name": "Near Industrial", "distance": 3.1, "economy": 1},
                    {"name": "Out of range", "distance": 7.1, "economy": 0},
                ],
            }
        )
        state.apply(
            {
                "type": "chart_target",
                "infoSystem": 42,
                "targetSystem": 42,
                "system": {
                    "id": 42,
                    "name": "Target",
                    "distance": 5.5,
                    "economy": 5,
                    "government": 6,
                    "techLevel": 12,
                    "samplePrices": {"food": 900, "computers": 730},
                },
                "currentSystem": 7,
                "originMarket": {
                    "food": {"price": 700, "quantity": 5},
                    "computers": {"price": 700, "quantity": 5},
                },
                "manifest": [
                    {"commodity": "food", "displayName": "Food", "quantity": 2},
                    {"commodity": "computers", "displayName": "Computers", "quantity": 1},
                ],
            }
        )

        expected = (
            "Target — 5.5 ly\n"
            "Rich agricultural · Democracy · Tech level 13\n"
            "Sell from hold: Food ×2 (90.0 cr/unit, +20.0 vs here), "
            "Computers ×1 (73.0 cr/unit, +3.0 vs here)\n"
            "Buy here: Food (+20.0 cr/unit), Computers (+3.0 cr/unit)\n"
            "Nearest agricultural: Near Ag (2.2 ly)\n"
            "Nearest industrial: Near Industrial (3.1 ly)"
        )
        self.assertEqual(tip(state, self.keymap), expected)

    def test_trade_scenario_persists_markets_and_cost_basis(self):
        now = datetime(2026, 10, 21, 7, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "markets.json"
            store = MarketStore(path, now=lambda: now)
            messages = [
                step["msg"]
                for step in load_scenario(ROOT / "scenarios" / "trade.yaml")
                if "msg" in step
            ]
            for _ in range(2):
                for message in messages:
                    store.apply(message)

            stored = MarketStore(path, now=lambda: now + timedelta(hours=2))
            self.assertEqual(len(stored.data["markets"]), 1)
            market = stored.data["markets"][0]
            self.assertEqual(
                (
                    market["galaxy"],
                    market["system_id"],
                    market["system_name"],
                    market["game_clock"],
                    market["station"],
                ),
                (0, 7, "Lave", 123466, "Lave Station"),
            )
            self.assertEqual(market["prices"]["food"]["quantity"], 6)
            self.assertEqual(
                stored.cost_basis["food"],  # the oldest lot sold first: 1 @ 42 and 2 @ 50 left
                {"units": 3, "total_cost": 142, "average_price": 142 / 3},
            )
            self.assertEqual(stored.price_age, "2h ago")

    def test_trade_dedupe_uses_game_event_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MarketStore(Path(directory) / "markets.json")
            first = {
                "type": "bought",
                "galaxy": 0,
                "systemID": 7,
                "gameClock": 10,
                "commodity": "food",
                "units": 2,
                "price": 42,
            }
            store.apply(first)
            store.apply(first)
            self.assertEqual(store.cost_basis["food"]["units"], 2)

            # A truncated log can restart line numbering, but a new game-clock event
            # remains distinct because deduplication uses the event payload itself.
            store.apply({**first, "gameClock": 11})
            self.assertEqual(store.cost_basis["food"]["units"], 4)

    def test_market_and_trade_storage_remain_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MarketStore(Path(directory) / "markets.json")
            for clock in range(600):
                store.apply(
                    {
                        "type": "market",
                        "galaxy": 0,
                        "systemID": 7,
                        "systemName": "Lave",
                        "gameClock": clock,
                        "station": "Lave Station",
                        "market": {"food": {"price": 42, "quantity": clock}},
                    }
                )
                store.apply(
                    {
                        "type": "bought",
                        "galaxy": 0,
                        "systemID": 7,
                        "gameClock": clock,
                        "commodity": "food",
                        "units": 1,
                        "price": 42,
                    }
                )

            self.assertEqual(len(store.data["markets"]), 1)
            self.assertEqual(store.data["markets"][0]["game_clock"], 599)
            self.assertEqual(len(store.data["market_events"]), 500)
            self.assertEqual(len(store.data["trade_events"]), 500)
            self.assertEqual(store.cost_basis["food"]["units"], 600)
            reopened = MarketStore(Path(directory) / "markets.json")
            self.assertEqual(len(reopened.data["markets"]), 1)
            self.assertEqual(len(reopened.data["market_events"]), 500)
            self.assertEqual(len(reopened.data["trade_events"]), 500)

    def test_truncated_log_new_trade_is_not_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Latest.log"
            market_path = Path(directory) / "markets.json"
            first = {
                "type": "bought",
                "galaxy": 0,
                "systemID": 7,
                "gameClock": 10,
                "commodity": "food",
                "units": 2,
                "price": 42,
            }
            second = {**first, "gameClock": 11}
            path.write_text(
                f"12:00:00.000 [ctxkeys]: {json.dumps(first)}\n" + "x" * 200,
                encoding="utf-8",
            )
            source = LogSource(path)
            store = MarketStore(market_path)
            try:
                for message in source.poll():
                    store.apply(message)
                path.write_text(f"12:00:00.000 [ctxkeys]: {json.dumps(second)}\n", encoding="utf-8")
                for message in source.poll():
                    store.apply(message)
            finally:
                source._file.close()

            self.assertEqual(store.cost_basis["food"]["units"], 4)

    def test_market_manifest_reconciles_saved_cost_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "markets.json"
            path.write_text(
                json.dumps(
                    {
                        "markets": [],
                        "cost_basis": {
                            "food": {"units": 5, "total_cost": 500, "average_price": 100},
                            "computers": {"units": 2, "total_cost": 40, "average_price": 20},
                        },
                    }
                ),
                encoding="utf-8",
            )
            store = MarketStore(path)
            store.apply(
                {
                    "type": "market",
                    "galaxy": 0,
                    "systemID": 7,
                    "gameClock": 20,
                    "station": "Lave Station",
                    "market": {"food": {"price": 42}},
                    "manifest": [{"commodity": "food", "quantity": 3}],
                }
            )

            self.assertEqual(
                store.cost_basis,
                {
                    "food": {"units": 3, "total_cost": 300, "average_price": 100},
                },
            )

    def test_every_scenario_step_uses_helper_message_contract(self):
        expected_contexts = {
            "combat": ["flying", "flying", "red alert", "flying"],
            "menus": ["flying", "menu", "menu", "flying", "flying"],
            "restart": ["flying", "red alert", "docked", "docked"],
            "quit": ["flying"],
        }
        for scenario in sorted((ROOT / "scenarios").glob("*.yaml")):
            if scenario.stem not in expected_contexts:
                continue
            state = GameState()
            context_steps = iter(expected_contexts[scenario.stem])
            for step in load_scenario(scenario):
                if "msg" in step:
                    state.apply(step["msg"])
                    self.assertEqual(state.context, next(context_steps), scenario.name)
                    self.assertEqual(state.details, [], scenario.name)
                    self.assertEqual(tip(state, self.keymap), "", scenario.name)
            with self.assertRaises(StopIteration):
                next(context_steps)

    def test_writer_emits_log_lines_rotates_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "Latest.log"
            writer = LogWriter(log_path)
            source = LogSource(log_path)

            writer.emit({"type": "ready", "docked": False, "alert": 1})
            messages = source.poll()
            self.addCleanup(lambda: source._file and source._file.close())
            self.assertEqual([msg["type"] for msg in messages], ["session", "ready"])

            writer.rotate()
            writer.emit({"type": "ready", "docked": True, "alert": 0})
            messages = source.poll()
            self.assertEqual([msg["type"] for msg in messages], ["session", "ready"])

            writer.close()
            self.assertEqual(source.poll(), [{"type": "closed"}])
            writer.stop()
            text = log_path.read_text(encoding="utf-8")
            self.assertIn("[ctxkeys]: {", text)
            self.assertIn("Closing log at ", text)

    def test_run_scenario_handles_close_step_and_rejects_bad_speed(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "Latest.log"
            run_scenario(
                [
                    {"after": 0, "msg": {"type": "ready", "docked": False, "alert": 1}},
                    {"after": 0, "close": True},
                ],
                log_path,
            )
            self.assertIn("Closing log at ", log_path.read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                run_scenario([], log_path, speed=0)


if __name__ == "__main__":
    unittest.main()
