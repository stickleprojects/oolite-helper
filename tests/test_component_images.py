"""Pictures of every component in each of its named states (#82).

Skipped unless OOLITE_HELPER_SHOTS names a folder to write them to; needs
headless Chrome or Chromium:

    OOLITE_HELPER_SHOTS=/tmp/shots .venv/bin/python -m pytest tests/test_component_images.py

One test per component state, so a state that fails to draw is named.
Pictures go to $OOLITE_HELPER_SHOTS/<component>/<state>.png.
"""

import os
import tempfile
import threading
from pathlib import Path

import pytest

from helper import harness
from helper.settings import COMPONENTS

SHOTS = os.environ.get("OOLITE_HELPER_SHOTS")
CHROME = harness.find_chrome()
pytestmark = pytest.mark.skipif(
    not SHOTS or CHROME is None, reason="set OOLITE_HELPER_SHOTS (and have Chrome) for pictures"
)
STATES = [
    (component.name, state) for component in COMPONENTS.values() for state, _ in component.states
]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    snaps = harness.snapshots([], None, tmp_path_factory.mktemp("snaps"))  # just the blank one
    found = [harness.component_target(name) for name in COMPONENTS]
    made = harness.HarnessServer(("127.0.0.1", 0), snaps, found)
    threading.Thread(target=made.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="oolite-shots-chrome-") as profile:
        made.profile = profile
        yield made
    made.shutdown()
    made.server_close()


@pytest.mark.parametrize(("component", "state"), STATES, ids=[f"{c}:{s}" for c, s in STATES])
def test_a_picture_of_the_component_in_the_state(server, component, state):
    tid = f"component.{component}"
    values = dict(COMPONENTS[component].states)[state]
    path = Path(SHOTS) / component / f"{state.replace(' ', '-')}.png"
    assert harness.picture(server, CHROME, server.profile, tid, harness.BLANK, values, path)
    assert path.stat().st_size > 0
