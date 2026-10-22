import json
import threading
import urllib.error
import urllib.request

import pytest

from helper.markets import MarketStore
from helper.model import Model
from helper.plugins import read_manifest
from helper.preview import PreviewServer
from tests.fakegame import load_scenario

MANIFEST = """\
name = "demo"
version = "1.0.0"
api = 1
topics = ["context", "alert"]
keys = ["key_jumpdrive"]
actions = ["ui/choose_tab"]
width = 200
height = 60
"""


@pytest.fixture
def preview(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    (root / "plugin.toml").write_text(MANIFEST)
    (root / "index.html").write_text("<p>demo</p>")
    manifest = read_manifest(root)
    model = Model(markets=MarketStore(tmp_path / "markets.json"))
    server = PreviewServer(("127.0.0.1", 0), manifest, model)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    yield server, root
    server.shutdown()
    server.server_close()
    thread.join()


def get(server, path):
    return urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{path}", timeout=3)


def test_plugin_files_are_served_and_escapes_are_refused(preview):
    server, root = preview
    with get(server, "/") as response:
        assert response.read() == b"<p>demo</p>"

    secret = root.parent / "secret.txt"
    secret.write_text("outside")
    (root / "leak.txt").symlink_to(secret)
    for path in ("/%2e%2e%2fsecret.txt", "/leak.txt"):
        with pytest.raises(urllib.error.HTTPError) as error:
            get(server, path)
        assert error.value.code == 404


def test_theme_and_preview_csp_are_served(preview):
    server, _ = preview
    with get(server, "/_oolite/theme.css") as response:
        assert response.headers["Content-Type"].startswith("text/css")
        assert b"--oo-bg:" in response.read()
    with get(server, "/_oolite/dev.js") as response:
        script = response.read().decode()
    assert "if (window.oolite) return" in script
    assert 'new EventSource("/_oolite/events")' in script
    assert 'fetch("/_oolite/message"' in script
    with get(server, "/index.html") as response:
        policy = response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in policy
    assert "script-src 'self'" in policy
    assert "connect-src 'self'" in policy


def test_sse_sends_manifest_topics_and_scenario_values(preview, tmp_path):
    server, _ = preview
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(
        json.dumps(
            [
                {"after": 0, "msg": {"type": "ready", "docked": False, "alert": 1}},
            ]
        )
    )
    with get(server, "/_oolite/events") as response:
        response.fp.raw._sock.settimeout(3)
        server.start_scenario(load_scenario(scenario))
        frames = []
        while not any('"value":"flying"' in frame for frame in frames):
            line = response.readline().decode()
            if line.startswith("data: "):
                frames.append(line[6:].strip())
    events = [json.loads(frame) for frame in frames]
    assert {event["topic"] for event in events} >= {"context", "alert", "keys"}
    assert any(event == {"topic": "context", "value": "flying"} for event in events)


def test_dispatch_is_checked_against_manifest(preview):
    server, _ = preview

    def post(action):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/_oolite/message",
            data=json.dumps({"type": "dispatch", "action": action}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=3)

    with post({"type": "ui/choose_tab", "tab": "trade"}) as response:
        assert response.status == 204
    assert server.model.ui.tab == "trade"

    with pytest.raises(urllib.error.HTTPError) as error:
        post({"type": "ui/change_quantity", "quantity": 4})
    assert error.value.code == 403
    assert server.model.ui.quantity is None
