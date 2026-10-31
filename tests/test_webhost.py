import os
import sys
import time

import pytest

from helper import webhost
from helper.webhost import WebFrame, WebHost, WebWindow, host, sandbox_env, untrusted_cookie

FAKE = [sys.executable, os.path.join(os.path.dirname(__file__), "fakewebhost.py")]
PROBE = os.path.join(os.path.dirname(__file__), "fixtures", "plugins", "probe")


# -- the host's pure functions ---------------------------------------------


def test_plugin_urls_resolve_only_inside_the_plugins_own_folder(tmp_path):
    (tmp_path / "radar").mkdir()
    (tmp_path / "radar" / "index.html").write_text("<p>")
    (tmp_path / "secret.txt").write_text("no")
    root = str(tmp_path / "radar")
    assert host.resolve(root, "radar", "plugin://radar/") == os.path.join(root, "index.html")
    assert host.resolve(root, "radar", "plugin://radar/index.html?x=1#y").endswith("index.html")
    for uri in (
        "plugin://radar/../secret.txt",
        "plugin://radar/%2e%2e/secret.txt",
        "plugin://radar/missing.js",
        "plugin://other/index.html",  # another plugin's name
        "file:///etc/passwd",
        "plugin://radar/index.html%00.js",
    ):
        assert host.resolve(root, "radar", uri) is None, uri


def test_symlinks_out_of_the_plugin_folder_are_refused(tmp_path):
    (tmp_path / "radar").mkdir()
    (tmp_path / "secret.txt").write_text("no")
    (tmp_path / "radar" / "link.txt").symlink_to(tmp_path / "secret.txt")
    assert host.resolve(str(tmp_path / "radar"), "radar", "plugin://radar/link.txt") is None


def test_the_csp_allows_only_the_plugins_own_files_and_no_connections():
    policy = host.csp("radar")
    assert "default-src 'none'" in policy
    assert "script-src plugin://radar;" in policy  # no 'unsafe-inline' or 'unsafe-eval'
    assert "connect-src 'none'" in policy


def test_pages_may_only_navigate_within_their_plugin():
    assert host.allowed_navigation("radar", "plugin://radar/other.html")
    assert not host.allowed_navigation("radar", "plugin://other/index.html")
    assert not host.allowed_navigation("radar", "https://example.com/")


def test_page_messages_are_whitelisted_and_clamped():
    assert host.page_message('{"type": "resize", "width": 10, "height": 99999}') == {
        "type": "resize",
        "width": host.SIZE_LIMITS[0],
        "height": host.SIZE_LIMITS[1],
    }
    assert host.page_message('{"type": "log", "text": "%s"}' % ("x" * 1000))["text"] == "x" * 500
    assert host.page_message('{"type": "show", "shown": false}') == {"type": "show", "shown": False}
    for bad in (
        '{"type": "show", "shown": 0}',
        "not json",
        "[1]",
        '{"type": "dispatch", "action": "ui/choose_tab"}',
        '{"type": "dispatch", "action": {"type": "%s"}}' % ("x" * 3000),
        '{"type": "navigate", "to": "https://example.com/"}',
        '{"type": "resize", "width": "1", "height": 2}',
        '{"type": "resize", "width": true, "height": 2}',
        '{"type": "log", "text": 5}',
    ):
        assert host.page_message(bad) is None, bad


def test_dispatches_pass_through_the_host_for_the_helper_to_check():
    action = {"type": "ui/choose_tab", "tab": "trade_table"}
    raw = '{"type": "dispatch", "action": {"type": "ui/choose_tab", "tab": "trade_table"}}'
    assert host.page_message(raw) == {"type": "dispatch", "action": action}


def test_helper_files_are_served_only_under_the_plugins_own_oolite_folder():
    assert host.extra_name("radar", "plugin://radar/_oolite/theme.css") == "theme.css"
    assert host.extra_name("radar", "plugin://radar/%5Foolite/theme.css") == "theme.css"
    assert host.extra_name("radar", "plugin://other/_oolite/theme.css") is None
    assert host.extra_name("radar", "plugin://radar/theme.css") is None


def test_topic_values_reach_the_page_as_json_literals():
    assert host.receive_script("clock", {"a": "</script>"}) == (
        '__oolite_receive("clock", {"a": "</script>"})'
    )


# -- the sandbox environment -----------------------------------------------


def test_the_host_environment_closes_the_holes_the_spike_found():
    env = sandbox_env(
        {"HOME": "/home/p", "DISPLAY": ":0", "XAUTHORITY": "/home/p/.Xauthority", "SECRET": "x"},
        "/run/user/1/oolite-helper/webhost.xauth",
        "/home/p/.cache/oolite-helper/webhost",
    )
    assert env["XAUTHORITY"] == "/run/user/1/oolite-helper/webhost.xauth"
    assert env["XDG_CACHE_HOME"] == "/home/p/.cache/oolite-helper/webhost"
    assert env["PULSE_SERVER"] == "unix:/nonexistent/pulse"
    assert "SECRET" not in env
    assert env["DISPLAY"] == ":0"


def test_untrusted_cookie_asks_xauth_for_an_untrusted_one(tmp_path):
    path = tmp_path / "cookie"
    path.write_text("old")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert not path.exists()  # the old one is removed first, or xauth merges
        path.write_text("new")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    assert untrusted_cookie(str(path), ":0", run) is None
    args = calls[0]
    assert args[args.index("generate") :] == ["generate", ":0", ".", "untrusted", "timeout", "60"]


def test_untrusted_cookie_explains_a_failure(tmp_path):
    def run(args, **kwargs):
        return type("Result", (), {"returncode": 1, "stderr": "no SECURITY extension"})()

    assert "no SECURITY extension" in untrusted_cookie(str(tmp_path / "c"), ":0", run)


def test_no_display_means_no_host(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="no DISPLAY"):
        webhost.default_env()


# -- the client, against the fake host -------------------------------------


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def run_until(host, done, timeout=5):
    """Poll until done(events so far) is true; returns the events."""
    events = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        events.extend(host.poll())
        if done(events):
            return events
        time.sleep(0.01)
    raise AssertionError(f"timed out; events: {events}")


def sent(events):
    """The commands the fake host received, as (op, id) pairs."""
    return [(e["cmd"]["op"], e["cmd"].get("id")) for e in events if e["ev"] == "got"]


@pytest.fixture
def fake_host():
    made = WebHost(command=FAKE, make_env=lambda: dict(os.environ), clock=Clock())
    yield made
    made.close()


def test_windows_open_when_the_host_is_ready_with_their_place_and_topics(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE, rect=(1, 2, 3, 4))})
    fake_host.publish("a", "clock", {"seconds": 1})
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 3)
    assert sent(events) == [("open", "a"), ("topic", "a"), ("place", "a")]
    opened = next(e["cmd"] for e in events if e["ev"] == "got")
    assert (opened["plugin"], opened["root"], opened["background"]) == ("probe", PROBE, "#101418")
    assert opened["extras"] == {}


def test_unchanged_topics_and_places_are_not_resent(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE, rect=(1, 2, 3, 4))})
    run_until(fake_host, lambda ev: len(sent(ev)) == 2)
    fake_host.publish("a", "clock", 1)
    fake_host.publish("a", "clock", 1)
    fake_host.sync({"a": WebWindow("probe", PROBE, rect=(1, 2, 3, 4))})
    fake_host.sync({"a": WebWindow("probe", PROBE, rect=None)})
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 2)
    time.sleep(0.1)
    events += fake_host.poll()
    assert [e["cmd"] for e in events if e["ev"] == "got"] == [
        {"op": "topic", "id": "a", "name": "clock", "value": 1},
        {"op": "place", "id": "a", "rect": None},
    ]


def test_sync_closes_removed_windows_and_reopens_changed_ones(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE), "b": WebWindow("probe", PROBE)})
    run_until(fake_host, lambda ev: len(sent(ev)) == 4)
    fake_host.sync({"a": WebWindow("probe", PROBE, entry="other.html")})
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 4)
    assert sorted(sent(events)) == [("close", "a"), ("close", "b"), ("open", "a"), ("place", "a")]


FRAME = WebFrame("Trading", (10, 20, 640, 720), ("#0055aa", "#ffffff"), 24)


def test_a_frame_opens_before_the_views_that_go_into_it(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE, frame="f", index=1)}, {"f": FRAME})
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 4)
    assert sent(events) == [("frame", "f"), ("place", "f"), ("open", "a"), ("place", "a")]
    opened = [e["cmd"] for e in events if e["ev"] == "got"][2]
    assert (opened["frame"], opened["index"]) == ("f", 1)


def test_a_frame_closes_after_the_views_in_it(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE, frame="f")}, {"f": FRAME})
    run_until(fake_host, lambda ev: len(sent(ev)) == 4)
    fake_host.sync({})
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 2)
    assert sent(events) == [("close", "a"), ("close", "f")]


def test_a_failed_window_stays_closed_until_retried(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE)})
    run_until(fake_host, lambda ev: any(e["ev"] == "loaded" for e in ev))
    fake_host._handle({"ev": "crashed", "id": "a", "reason": "crashed"})  # as the host reports it
    assert fake_host.failed == {"a": "crashed"}
    events = run_until(fake_host, lambda ev: ("close", "a") in sent(ev))
    fake_host.sync({"a": WebWindow("probe", PROBE)})  # the same window: still failed
    time.sleep(0.1)
    assert ("open", "a") not in sent(events + fake_host.poll())
    fake_host.retry("a")
    run_until(fake_host, lambda ev: ("open", "a") in sent(ev))


def test_a_dead_host_is_restarted_and_its_windows_replayed(fake_host):
    fake_host.sync({"a": WebWindow("probe", PROBE, rect=(1, 2, 3, 4))})
    fake_host.publish("a", "clock", 7)
    run_until(fake_host, lambda ev: len(sent(ev)) == 3)
    fake_host.process.kill()
    events = run_until(fake_host, lambda ev: any(e["ev"] == "host_exited" for e in ev))
    time.sleep(0.1)
    assert fake_host.poll() == []  # waiting out the restart delay
    fake_host.clock.now += webhost.RESTART_DELAYS[0]
    events = run_until(fake_host, lambda ev: len(sent(ev)) == 3)
    assert sent(events) == [("open", "a"), ("topic", "a"), ("place", "a")]


def test_a_host_speaking_another_protocol_is_stopped(monkeypatch):
    monkeypatch.setenv("FAKE_WEBHOST_PROTOCOL", "1")
    made = WebHost(command=FAKE, make_env=lambda: dict(os.environ), clock=Clock())
    events = run_until(made, lambda ev: any(e["ev"] == "host_exited" for e in ev))
    assert "protocol 1" in events[-1]["message"]
    assert made.process is None


def test_a_host_that_cant_be_made_safe_isnt_started():
    def refuse():
        raise RuntimeError("xauth couldn't make an untrusted cookie")

    clock = Clock()
    made = WebHost(command=FAKE, make_env=refuse, clock=clock)
    (event,) = made.poll()
    assert event["ev"] == "unavailable" and "untrusted cookie" in event["message"]
    assert made.process is None and made.poll() == []  # not again until the delay
    clock.now += webhost.RESTART_DELAYS[0]
    assert made.poll()[0]["ev"] == "unavailable"
