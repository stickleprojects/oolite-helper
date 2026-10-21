import pytest

from helper.app import HelperWindow, should_quit_for_messages
from helper.markets import MarketStore
from helper.state import GameState


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
    w = HelperWindow.__new__(HelperWindow)  # no Tk: just the polling parts
    w.root = FakeRoot()
    w.status_label = FakeLabel()
    w.source = source
    w.state = GameState()
    w.market_store = MarketStore(tmp_path / "markets.json")
    w.shown_market_age = None
    w.first_poll = False
    w.quit_with_game = True
    w.keymap_error = None
    w.notice = None
    w.error = None
    w.last_message = ""
    w.render = lambda: w.status_label.config(text=w.status_text())
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
    assert w.state.context == "docked"
    assert w.status_label.text == '{"type": "ready", "docked": true}'


def test_one_bad_message_does_not_drop_the_rest(tmp_path):
    bad = {"type": "countdown", "kind": "standard", "seconds": "soon"}
    w = window(FakeSource([bad, {"type": "ready", "docked": True}]), tmp_path)
    w.tick()
    assert w.state.context == "docked"
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
