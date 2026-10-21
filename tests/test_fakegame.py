import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helper.contexts import tip
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

    def test_docking_messages_update_context_details_and_tips(self):
        state = GameState()
        expected = [
            ("docked", [], ""),
            ("flying", [], ""),
            ("near station", ["Clearance: none"],
             "K asks your current target, so target the station first (K with it ahead, or K)."),
            ("near station", ["Clearance: requested"],
             "Waiting for clearance. Pressing K again cancels the request."),
            ("near station", ["Clearance: granted"],
             "Cleared to dock. Pressing K again cancels clearance."),
            ("near station", ["Clearance: timing out"],
             "Clearance is about to expire: press K now to extend it."),
            ("near station", ["Clearance: none"],
             "K asks your current target, so target the station first (K with it ahead, or K)."),
            ("docked", [], ""),
        ]
        steps = load_scenario(ROOT / "scenarios" / "docking.yaml")
        self.assertEqual(len(steps), len(expected))
        for step, (context, details, expected_tip) in zip(steps, expected):
            state.apply(step["msg"])
            self.assertEqual(state.context, context)
            self.assertEqual(state.details, details)
            self.assertEqual(tip(state, self.keymap), expected_tip)

    def test_jump_messages_update_context_details_and_tip(self):
        state = GameState()
        expected_contexts = [
            "flying", "menu", "flying", "jump countdown",
            "flying", "jump countdown", "flying", "flying",
        ]
        steps = load_scenario(ROOT / "scenarios" / "jump.yaml")
        self.assertEqual(len(steps), len(expected_contexts))
        with patch("helper.state.time.monotonic", return_value=100):
            for step, context in zip(steps, expected_contexts):
                state.apply(step["msg"])
                self.assertEqual(state.context, context)
                if context == "jump countdown":
                    countdown = step["msg"]
                    expected_detail = ("Galactic jump in 20s" if countdown["kind"] == "galactic"
                                       else "Jump in 15s")
                    self.assertEqual(state.details[0], expected_detail)
                    self.assertEqual(tip(state, self.keymap),
                                     "Press K again to cancel the countdown.")
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
        self.assertEqual(state.manifest[0]["name"], "food")
        self.assertEqual(state.last_trade["type"], "sold")
        self.assertEqual(state.last_trade["units"], 1)
        self.assertEqual([system["name"] for system in state.systems], ["Zaonce"])
        self.assertEqual(state.fuel, 7)
        self.assertEqual(state.info_system, 8)
        self.assertEqual(state.target_system, 9)
        self.assertEqual(state.chart_system["name"], "Zaonce")
        self.assertEqual(state.origin_prices, {"food": 42, "computers": 735})

    def test_chart_advice_estimates_trades_and_nearest_economies(self):
        state = GameState()
        state.apply({"type": "gui", "to": "GUI_SCREEN_LONG_RANGE_CHART"})
        state.apply({
            "type": "systems",
            "fuel": 7,
            "systems": [
                {"name": "Near Ag", "distance": 2.2, "economy": 5},
                {"name": "Far Ag", "distance": 6.0, "economy": 4},
                {"name": "Near Industrial", "distance": 3.1, "economy": 1},
                {"name": "Out of range", "distance": 7.1, "economy": 0},
            ],
        })
        state.apply({
            "type": "chart_target",
            "infoSystem": 42,
            "targetSystem": 42,
            "system": {
                "id": 42, "name": "Target", "distance": 5.5, "economy": 5,
                "government": 6, "techLevel": 12,
                "samplePrices": {"food": 900, "computers": 730},
            },
            "originPrices": {"food": 700, "computers": 700},
            "manifest": [
                {"name": "food", "displayName": "Food", "quantity": 2},
                {"name": "computers", "displayName": "Computers", "quantity": 1},
            ],
        })

        expected = (
            "Target — 5.5 ly\n"
            "Rich agricultural · Democracy · Tech level 12\n"
            "Sell from hold: Food ×2 (90.0 cr/unit, +20.0 vs here), "
            "Computers ×1 (73.0 cr/unit, +3.0 vs here)\n"
            "Buy here: Food (+20.0 cr/unit), Computers (+3.0 cr/unit)\n"
            "Nearest agricultural: Near Ag (2.2 ly)\n"
            "Nearest industrial: Near Industrial (3.1 ly)"
        )
        self.assertEqual(tip(state, self.keymap), expected)

    def test_every_scenario_step_uses_helper_message_contract(self):
        expected_contexts = {
            "combat": ["flying", "red alert", "flying"],
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
            run_scenario([
                {"after": 0, "msg": {"type": "ready", "docked": False, "alert": 1}},
                {"after": 0, "close": True},
            ], log_path)
            self.assertIn("Closing log at ", log_path.read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                run_scenario([], log_path, speed=0)


if __name__ == "__main__":
    unittest.main()
