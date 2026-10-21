import pytest

from helper.app import should_quit_for_messages


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
