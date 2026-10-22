import pytest

from helper.app import HelperWindow, should_quit_for_messages
from helper.markets import MarketStore
from helper.model import Model
from helper.plugins import PluginPanels
from helper.views.header import Status


@pytest.mark.parametrize(
    ("messages", "first_poll", "quit_with_game", "expected"),
    [
        ([{"type": "closed"}], True, True, False),
        ([{"type": "closed"}], False, True, True),
        ([{"type": "session"}, {"type": "closed"}], False, True, False),
        ([{"type": "closed"}], False, False, False),
        ([{"type": "ready"}], False, True, False),
    ],
)
def test_close_decision_handles_old_logs_live_close_and_rotation_race(
    messages, first_poll, quit_with_game, expected
):
    assert should_quit_for_messages(messages, first_poll, quit_with_game) is expected


class FakeRoot:
    def __init__(self):
        self.scheduled = []
        self.destroyed = False

    def after(self, ms, callback):
        self.scheduled.append(callback)

    def destroy(self):
        self.destroyed = True


class FakeLabel:
    text = ""

    def config(self, text, **kwargs):
        self.text = text


class FakeSource:
    def __init__(self, *batches):
        self.batches = list(batches)

    def poll(self):
        batch = self.batches.pop(0)
        if isinstance(batch, Exception):
            raise batch
        return batch


def window(source, tmp_path):
    """The polling parts of the window, with a status line but no Tk."""
    w = HelperWindow.__new__(HelperWindow)
    w.root = FakeRoot()
    w.source = source
    w.first_poll = False
    w.quit_with_game = True
    w.ticks, w.game_window = 0, None  # no widgets
    w.model = Model(markets=MarketStore(tmp_path / "markets.json"))
    w.model.on_error = lambda exc, where: w.report(exc)
    w.plugins = PluginPanels(w.model, [], {})  # no plugins
    w.status_label = FakeLabel()
    Status(w.model, None, w.status_label)
    return w


def test_polling_continues_after_an_unexpected_error(tmp_path, capsys):
    w = window(
        FakeSource(PermissionError("Latest.log"), [{"type": "ready", "docked": True}]), tmp_path
    )
    w.tick()
    assert w.root.scheduled == [w.tick]  # still polling
    assert w.status_label.text == "Error (still running): PermissionError: Latest.log"
    assert "PermissionError" in capsys.readouterr().err

    w.tick()
    assert len(w.root.scheduled) == 2
    assert w.model.state.context == "docked"
    assert w.status_label.text == '{"type": "ready", "docked": true}'


def test_one_bad_message_does_not_drop_the_rest(tmp_path):
    bad = {"type": "countdown", "kind": "standard", "seconds": "soon"}
    w = window(FakeSource([bad, {"type": "ready", "docked": True}]), tmp_path)
    w.tick()
    assert w.model.state.context == "docked"
    assert w.root.scheduled == [w.tick]


def test_same_error_is_printed_once(tmp_path, capsys):
    w = window(FakeSource(OSError("gone"), OSError("gone")), tmp_path)
    w.tick()
    w.tick()
    assert capsys.readouterr().err.count("oolite-helper: OSError: gone") == 1


def test_closing_game_stops_polling(tmp_path):
    w = window(FakeSource([{"type": "closed"}]), tmp_path)
    w.tick()
    assert w.root.destroyed and w.root.scheduled == []


def test_a_failing_view_shows_in_the_status_line_and_polling_goes_on(tmp_path, capsys):
    w = window(FakeSource([{"type": "mass_lock", "by": "planet"}]), tmp_path)

    def broken(value):
        raise RuntimeError("draw failed")

    w.model.subscribe("mass_lock", broken, initial=False)
    w.tick()
    w.model.notify()
    assert w.root.scheduled == [w.tick]
    assert w.status_label.text == "Error (still running): RuntimeError: draw failed"


def test_trade_detail_picks_the_best_offer_and_caps_the_quantity(tmp_path):
    model = Model(markets=MarketStore(tmp_path / "markets.json"))
    for msg in (
        {"type": "ready", "docked": True},
        {
            "type": "market",
            "galaxy": 0,
            "systemID": 7,
            "credits": 1000,
            "cargoSpace": {"available": 20, "capacity": 20},
            "market": {"furs": {"price": 700, "quantity": 5}},
        },
        {
            "type": "systems",
            "galaxy": 0,
            "fuel": 7,
            "systems": [
                {"id": 8, "name": "Zaonce", "distance": 6.5, "samplePrices": {"furs": 800}},
                {"id": 9, "name": "Diso", "distance": 3.0, "samplePrices": {"furs": 750}},
            ],
        },
        {"type": "ui/open_commodity", "commodity": "furs"},
        {"type": "ui/change_quantity", "quantity": 99},
    ):
        model.dispatch(msg)
    commodity, row, offers, offer, limit, quantity, steps = model.topic("trade_detail")
    assert (commodity, offer.name, quantity, limit.most) == ("furs", "Zaonce", 5, 5)
    model.dispatch({"type": "ui/choose_destination", "system": 9})
    assert model.topic("trade_detail")[3].name == "Diso"
