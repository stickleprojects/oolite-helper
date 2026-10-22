import pytest

from helper.model import TOPICS, UI, Model


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def flying():
    model = Model(clock=Clock())
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    return model


def test_a_watcher_is_called_now_and_then_only_when_its_value_changes():
    model = flying()
    seen = []
    model.subscribe("jump_blocker", seen.append)
    assert seen == [None]
    model.notify()
    assert seen == [None]  # nothing changed
    model.dispatch({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    model.dispatch({"type": "alert", "level": 2})  # something it doesn't show
    model.notify()
    assert seen == [None, {"by": "Coriolis Station", "clearAt": 6747, "type": "jump_blocker"}]
    model.dispatch({"type": "alert", "level": 1})
    model.notify()
    assert len(seen) == 2


def test_two_panels_on_one_topic_are_both_told_and_it_is_computed_once(monkeypatch):
    model = flying()
    calls = []
    selector, every = TOPICS["jump_blocker"]
    monkeypatch.setitem(TOPICS, "jump_blocker", (lambda m: calls.append(1) or selector(m), every))
    first, second = [], []
    model.subscribe("jump_blocker", first.append, initial=False)
    model.subscribe("jump_blocker", second.append, initial=False)
    model.dispatch({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    model.notify()
    assert len(first) == len(second) == 1
    assert len(calls) == 1  # memoised for the pass
    model.notify()
    assert len(calls) == 1  # and kept until the state changes


def test_a_combined_selector_redraws_once_from_a_consistent_snapshot():
    model = flying()
    model.dispatch({"type": "systems", "systems": [{"id": 8, "name": "Qutiri"}]})
    model.dispatch({"type": "chart_target", "targetSystem": 8, "currentSystem": 154})
    model.dispatch({"type": "countdown", "kind": "standard", "seconds": 15})
    drawn = []
    model.watch(lambda m: (m.topic("jump_blocker"), m.topic("location")), drawn.append)
    # Arriving changes the location and clears the blocker in one batch.
    model.dispatch({"type": "jump_blocker", "by": None, "clearAt": None})
    model.dispatch({"type": "arrived", "system": "Qutiri", "alert": 1})
    model.dispatch({"type": "chart_target", "targetSystem": 8, "currentSystem": 8})
    model.notify()
    assert drawn[-1] == (None, ("Qutiri", True, None))
    assert len(drawn) == 2  # the initial draw, then one redraw


def test_a_failing_view_is_reported_and_the_others_still_update():
    model = flying()
    errors, seen = [], []
    model.on_error = lambda exc, where: errors.append(str(exc))

    def broken(value):
        raise RuntimeError("draw failed")

    model.subscribe("mass_lock", broken, initial=False)
    model.subscribe("mass_lock", seen.append, initial=False)
    model.dispatch({"type": "mass_lock", "by": "planet"})
    model.notify()
    assert errors == ["draw failed"]
    assert seen == ["planet"]
    model.notify()  # the failed one is retried, the good one isn't redrawn
    assert errors == ["draw failed", "draw failed"]
    assert seen == ["planet"]


def test_cancel_stops_notifications():
    model = flying()
    seen = []
    subscription = model.subscribe("mass_lock", seen.append, initial=False)
    subscription.cancel()
    model.dispatch({"type": "mass_lock", "by": "planet"})
    model.notify()
    assert seen == []


def test_clock_topics_change_with_time_without_any_message():
    model = flying()
    ticks = []
    model.subscribe("clock", ticks.append)
    model.clock.now = 0.4
    model.notify()
    model.clock.now = 0.6
    model.notify()
    assert ticks == [0, 1]


def test_ui_actions_go_through_the_same_dispatch_and_notify():
    model = flying()
    seen = []
    model.subscribe("ui", seen.append, initial=False)
    model.dispatch({"type": "ui/open_commodity", "commodity": "furs"})
    model.dispatch({"type": "ui/change_quantity", "quantity": 3})
    model.notify()
    assert seen == [UI(commodity="furs", quantity=3)]
    model.dispatch({"type": "ui/open_commodity", "commodity": "gold"})
    assert model.ui == UI(commodity="gold")  # a new commodity resets its choices
    with pytest.raises(ValueError):
        model.dispatch({"type": "ui/unknown"})


def test_urgent_contexts_show_keys_then_the_chosen_tab_returns():
    model = flying()
    model.dispatch({"type": "ui/choose_tab", "tab": "all"})
    assert model.topic("tab") == "all"
    model.dispatch({"type": "alert", "level": 3})
    assert model.topic("tab") == "keys"
    model.dispatch({"type": "alert", "level": 1})
    assert model.topic("tab") == "all"
    model.dispatch({"type": "died", "cause": "energy damage", "by": None})
    assert model.topic("tab") == "keys"


def test_unknown_topic_names_fail_when_subscribing():
    with pytest.raises(KeyError):
        flying().subscribe("no_such_topic", print)


def test_trade_here_is_offered_whenever_docked_on_any_screen(tmp_path):
    from helper.markets import MarketStore

    model = Model(markets=MarketStore(tmp_path / "markets.json"), clock=Clock())
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    assert model.topic("market_advice") == ()
    model.dispatch({"type": "docked"})
    model.dispatch({"type": "gui", "to": "GUI_SCREEN_STATUS"})
    model.dispatch(
        {
            "type": "market",
            "galaxy": 0,
            "systemID": 7,
            "market": {"food": {"price": 40, "quantity": 5}},
            "manifest": [{"commodity": "food", "quantity": 2}],
        }
    )
    groups = dict(model.topic("market_advice"))
    assert groups["Your hold"][0].startswith("Food ×2: 4.0 here")


def test_missing_equipment_keys_are_greyed_by_default_or_hidden():
    def flying(setting):
        model = Model(missing_equipment=setting)
        model.dispatch({"type": "ready", "docked": False, "alert": 3})
        model.dispatch(
            {"type": "equipment", "items": [], "missiles": {"capacity": 0, "loaded": []}}
        )
        return [a for _, actions in model.topic("sections") for a in actions], model

    shown, model = flying("grey")
    assert "key_ecm" in shown and "key_ecm" in model.topic("missing")
    shown, model = flying("hide")
    assert "key_ecm" not in shown and "key_launch_missile" not in shown
    assert "key_fire_lasers" in shown
