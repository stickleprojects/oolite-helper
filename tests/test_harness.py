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


def test_the_first_snapshot_is_blank(snaps):
    assert (snaps[0].id, snaps[0].context) == (harness.BLANK, "waiting for game")


def test_a_scenarios_snapshots_start_where_it_starts(snaps):
    assert snaps[1].context == "docked"


def test_a_snapshot_is_kept_for_each_context_the_scenario_passes_through(snaps):
    assert "near station" in [snap.context for snap in snaps]


def test_one_snapshot_per_stretch_of_one_context(snaps):
    contexts = [snap.context for snap in snaps]
    assert all(a != b for a, b in zip(contexts, contexts[1:], strict=False))


def test_a_snapshot_is_named_by_its_scenario_and_step(snaps):
    assert [snap.id for snap in snaps[1:]] == [f"docking.{snap.step}" for snap in snaps[1:]]


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


# -- choosing targets by name ------------------------------------------------------


def test_a_component_name_is_that_component_alone():
    assert [t.id for t in harness.targets(None, plugins={}, names=["clearance"])] == [
        "component.clearance"
    ]


def test_components_joined_with_plus_are_one_widget():
    (target,) = harness.targets(None, plugins={}, names=["clearance+drive"])
    assert target.spec.components == ("clearance", "drive")


def test_a_widget_id_is_that_widget_from_the_config(tmp_path):
    (target,) = harness.targets(config_with_a_strip(tmp_path), plugins={}, names=["strip"])
    assert target.id == "widget.strip"


def test_an_unknown_name_says_whats_available():
    with pytest.raises(ValueError, match="isn't a component or a widget"):
        harness.targets(None, plugins={}, names=["radar"])


def test_a_widgets_states_are_its_components_states():
    (target,) = harness.targets(None, plugins={}, names=["clearance+drive"])
    assert {component for component, _, _ in target.states} == {"clearance", "drive"}


# -- states and edits ----------------------------------------------------------------


@pytest.fixture
def clearance_server(snaps):
    made = harness.HarnessServer(("127.0.0.1", 0), snaps, harness.targets(None, {}, ["clearance"]))
    threading.Thread(target=made.serve_forever, daemon=True).start()
    yield made
    made.shutdown()
    made.server_close()


def overrides_url():
    return f"s/{harness.BLANK}/component.clearance/_oolite/override"


def clearance_now(server):
    return server.values(harness.BLANK, "component.clearance")["clearance"]


def test_a_named_state_sets_its_components_topics(clearance_server):
    post(clearance_server, overrides_url(), {"component": "clearance", "state": "expiring"})
    assert clearance_now(clearance_server)["flashes"] is True


def test_an_edited_topic_replaces_the_snapshots_value(clearance_server):
    badge = {"status": "granted", "text": "Edited", "colour": "green", "flashes": False}
    post(clearance_server, overrides_url(), {"topic": "clearance", "value": badge})
    assert clearance_now(clearance_server) == badge


def test_reset_goes_back_to_the_snapshot(clearance_server):
    post(clearance_server, overrides_url(), {"component": "clearance", "state": "expiring"})
    post(clearance_server, overrides_url(), {"reset": True})
    assert clearance_now(clearance_server) is None


def test_a_topic_the_target_doesnt_read_is_refused(clearance_server):
    assert post(clearance_server, overrides_url(), {"topic": "drive", "value": None}) == 400


def test_an_unknown_state_is_refused(clearance_server):
    body = {"component": "clearance", "state": "on fire"}
    assert post(clearance_server, overrides_url(), body) == 400


def test_one_target_opens_with_its_states_and_topics(clearance_server):
    page = get(clearance_server, "")[2].decode()
    assert "<option>expiring</option>" in page and 'data-topic="clearance"' in page


def test_pictures_are_taken_at_each_snapshot_then_in_each_named_state(clearance_server, snaps):
    stems = [stem for _, stem, _, _ in harness.cases(clearance_server, "component.clearance")]
    assert stems[: len(snaps)] == [snap.id for snap in snaps]
    assert "state.clearance-expiring" in stems


# -- READMEs -------------------------------------------------------------------------

CLEARANCE = COMPONENTS["clearance"]
PICTURES = [("away from stations", None), ("expiring", "expiring.png")]


def clearance_readme(size=(640, 40)):
    return harness.readme(CLEARANCE, PICTURES, size)


def test_a_readme_starts_with_the_components_description():
    assert f"# clearance\n\n{CLEARANCE.description}\n" in clearance_readme()


def test_a_readme_lists_what_the_component_reads():
    assert "| **Reads** | `clearance` |" in clearance_readme()


def test_a_readme_links_what_a_component_needs():
    page = harness.readme(COMPONENTS["all_keys"], [], (1600, 900))
    assert "[`keys`](../keys/README.md)" in page


def test_a_readme_shows_each_states_picture():
    assert '<img src="images/expiring.png"' in clearance_readme()


def test_a_readme_says_when_a_state_shows_nothing():
    assert "<b>away from stations</b><br><i>shows nothing</i>" in clearance_readme()


def test_strips_are_one_to_a_row():
    assert clearance_readme().count("<tr>") == 2


def test_bigger_components_are_two_to_a_row():
    assert clearance_readme(size=(1600, 900)).count("<tr>") == 1


@pytest.mark.parametrize("name", list(COMPONENTS))
def test_each_components_readme_is_up_to_date_with_its_states(name):
    """Run `python -m helper.harness --readmes` after changing a states file."""
    text = (Path(harness.web.COMPONENTS_DIR) / name / "README.md").read_text()
    for state, _ in COMPONENTS[name].states:
        assert f"<b>{state}</b>" in text, f"{name}: {state!r} isn't in its README"
