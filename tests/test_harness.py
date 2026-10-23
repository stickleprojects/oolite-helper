import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from helper import harness
from helper.widgets import COMPONENTS

SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture(scope="module")
def snaps(tmp_path_factory):
    return harness.snapshots([SCENARIOS / "docking.yaml"], None, tmp_path_factory.mktemp("h"))


def test_snapshots_start_where_the_scenario_starts(snaps):
    assert snaps[0].context == "docked"


def test_a_snapshot_is_kept_for_each_context_the_scenario_passes_through(snaps):
    assert "near station" in [snap.context for snap in snaps]


def test_one_snapshot_per_stretch_of_one_context(snaps):
    contexts = [snap.context for snap in snaps]
    assert all(a != b for a, b in zip(contexts, contexts[1:], strict=False))


def test_a_snapshot_is_named_by_its_scenario_and_step(snaps):
    assert [snap.id for snap in snaps] == [f"docking.{snap.step}" for snap in snaps]


def config_with_a_strip(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[[widgets]]\nid = "strip"\ncomponents = ["clearance", "drive"]\n')
    return config


def test_every_component_is_a_target_on_its_own():
    ids = [target.id for target in harness.targets(None, plugins={})]
    assert ids == [f"component.{name}" for name in COMPONENTS]


def test_the_configs_widgets_come_after_the_components(tmp_path):
    found = harness.targets(config_with_a_strip(tmp_path), plugins={})
    assert found[-1].id == "widget.strip"


def test_a_widget_target_reads_only_its_components_topics(tmp_path):
    found = harness.targets(config_with_a_strip(tmp_path), plugins={})
    assert found[-1].manifest.topics == ("clearance", "drive")


@pytest.fixture
def server(snaps):
    found = harness.targets(None, plugins={})
    made = harness.HarnessServer(("127.0.0.1", 0), snaps, found)
    threading.Thread(target=made.serve_forever, daemon=True).start()
    yield made
    made.shutdown()
    made.server_close()


def get(server, path):
    with urllib.request.urlopen(server.url + path, timeout=5) as response:
        return response.status, response.headers, response.read()


def post(server, path, body):
    request = urllib.request.Request(
        server.url + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def drive_page(snaps):
    return f"s/{snaps[0].id}/component.drive/"


def test_the_index_links_each_target_at_the_chosen_snapshot(server, snaps):
    page = get(server, f"?snap={snaps[1].id}")[2].decode()
    assert f"/s/{snaps[1].id}/component.keys/_oolite/widget.html" in page


def test_the_index_has_a_frame_per_target(server, snaps):
    page = get(server, "")[2].decode()
    assert page.count("<iframe") == len(COMPONENTS)


def test_a_targets_page_loads_its_components(server, snaps):
    page = get(server, drive_page(snaps) + "_oolite/widget.html")[2]
    assert b"../components/drive/drive.js" in page


def test_pages_get_the_plugin_policy(server, snaps):
    headers = get(server, drive_page(snaps) + "_oolite/widget.html")[1]
    assert "script-src 'self'" in headers["Content-Security-Policy"]


def test_component_files_are_served(server, snaps):
    assert get(server, drive_page(snaps) + "components/drive/drive.js")[0] == 200


def test_topics_are_only_the_targets_own(server, snaps):
    topics = get(server, drive_page(snaps) + "_oolite/topics")[2]
    assert set(json.loads(topics)) == {"drive"}


@pytest.mark.parametrize(
    "path", ["components/drive/drive.test.js", "../harness.py", "components/../../plugins.py"]
)
def test_tests_and_files_outside_helper_web_are_not_served(server, snaps, path):
    with pytest.raises(urllib.error.HTTPError):
        get(server, drive_page(snaps) + path)


def trade_dispatch(snaps):
    return f"s/{snaps[0].id}/component.trade_table/_oolite/dispatch"


def test_a_click_the_component_may_send_is_applied_to_that_snapshot(server, snaps):
    post(server, trade_dispatch(snaps), {"type": "ui/open_commodity", "commodity": "food"})
    assert snaps[0].model.ui.commodity == "food"


def test_a_click_the_component_may_not_send_is_refused(server, snaps):
    assert post(server, trade_dispatch(snaps), {"type": "ui/choose_tab", "tab": "all"}) == 403
