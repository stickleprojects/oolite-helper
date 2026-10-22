"""The real web host and WebKit sandbox (#59). Needs a display, GTK 3, WebKit2 4.1 and xauth:

    OOLITE_HELPER_LIVE_WEBHOST=1 .venv/bin/python -m pytest tests/test_webhost_live.py

Not run in CI (no display). Run it after WebKit upgrades: it checks that the
probe plugin is refused everything and that the web process's sandbox still
shows only what the #59 spike allowed.
"""

import os
import time

import pytest

from helper.webhost import WebHost, WebWindow, cache_dir

pytestmark = pytest.mark.skipif(
    not os.environ.get("OOLITE_HELPER_LIVE_WEBHOST"), reason="set OOLITE_HELPER_LIVE_WEBHOST=1"
)
PROBE = os.path.join(os.path.dirname(__file__), "fixtures", "plugins", "probe")
HOME = os.path.expanduser("~")


def descendants(pid):
    children = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/stat") as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
            except OSError:
                continue
            children.setdefault(ppid, []).append(int(entry))
    found, todo = [], [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def web_process(host_pid):
    for pid in descendants(host_pid):
        try:
            with open(f"/proc/{pid}/comm") as f:
                if f.read().strip().startswith("WebKitWebProc"):
                    return pid
        except OSError:
            continue
    return None


def mount_points(pid):
    with open(f"/proc/{pid}/mountinfo") as f:
        return {line.split()[4]: line.split()[5] for line in f}


@pytest.fixture(scope="module")
def run():
    host = WebHost()
    host.sync({"probe": WebWindow("probe", PROBE, rect=(0, 0, 320, 240))})
    host.publish("probe", "clock", {"seconds": 1})
    started = time.monotonic()
    events, loaded_after = [], None
    while time.monotonic() - started < 15:
        for event in host.poll():
            events.append(event)
            if event["ev"] == "loaded":
                loaded_after = time.monotonic() - started
        if any(e.get("msg", {}).get("text") == "probe navigate: tried" for e in events):
            break
        time.sleep(0.05)
    time.sleep(0.5)  # let the navigation attempt be refused
    pid = web_process(host.process.pid)
    mounts = mount_points(pid) if pid else None
    yield events, loaded_after, mounts
    host.close()


def test_the_page_loads_quickly(run):
    events, loaded_after, _ = run
    assert events[0]["ev"] == "ready"
    assert loaded_after is not None and loaded_after < 5


def test_the_sandbox_refuses_everything_the_probe_tries(run):
    events, _, _ = run
    results = dict(
        e["msg"]["text"].removeprefix("probe ").split(": ", 1)
        for e in events
        if e["ev"] == "page" and e["msg"]["text"].startswith("probe ")
    )
    probes = set(results) - {"done", "navigate"}
    assert len(probes) >= 11
    assert {name: r for name, r in results.items() if name in probes and "blocked" not in r} == {}
    assert not any(e["ev"] in ("error", "crashed") for e in events)


def test_the_web_process_sees_only_what_the_spike_allowed(run):
    _, _, mounts = run
    assert mounts is not None, "no WebKitWebProcess found under the host"
    # The real ~/.cache, ~/.Xauthority and the sound server stay out.
    for hole in (f"{HOME}/.cache", f"{HOME}/.Xauthority", f"/run/user/{os.getuid()}/pulse"):
        assert hole not in mounts, hole
    # Every bind under the home folder is read-only, apart from our own cache.
    writable = {
        point
        for point, options in mounts.items()
        if point.startswith(HOME + "/") and "rw" in options.split(",")
    }
    assert writable <= {cache_dir(), os.path.join(cache_dir(), "fontconfig")}
    # The only X cookie it has is the helper's untrusted one.
    assert any(point.endswith("oolite-helper/webhost.xauth") for point in mounts)
