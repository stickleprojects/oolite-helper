import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from helper import harness
from helper.widgets import COMPONENTS, WIDGETS

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


def test_every_component_is_a_target_on_its_own_then_every_named_widget():
    ids = [target.id for target in harness.targets(None, plugins={})]
    assert ids == [f"component.{name}" for name in COMPONENTS] + [f"widget.{n}" for n in WIDGETS]


def test_the_configs_widgets_come_after_the_components(tmp_path):
    found = harness.targets(config_with_a_strip(tmp_path), plugins={})
    assert found[-1].id == "config.strip"


def test_a_widget_target_reads_only_its_components_topics(tmp_path):
    found = harness.targets(config_with_a_strip(tmp_path), plugins={})
    assert found[-1].manifest.topics == ("clearance", "context", "drive")


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
    assert page.count("<iframe") == len(COMPONENTS) + len(WIDGETS)


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
    assert post(server, trade_dispatch(snaps), {"type": "ui/choose_tab", "tab": "all_keys"}) == 403


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
    assert target.id == "config.strip"


def test_a_widgets_name_is_that_named_widget():
    (target,) = harness.targets(None, plugins={}, names=["top-strip"])
    assert (target.id, target.spec.dock) == ("widget.top-strip", "game:top")


def test_named_widgets_and_components_have_different_names():
    assert not set(WIDGETS) & set(COMPONENTS)


def test_an_unknown_name_says_whats_available():
    with pytest.raises(ValueError, match="isn't a component, a named widget or a widget"):
        harness.targets(None, plugins={}, names=["sonar"])


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
    assert "| **Reads** | `clearance`, `context` |" in clearance_readme()


def test_a_readme_links_what_a_component_needs():
    page = harness.readme(COMPONENTS["all_keys"], [], (1600, 900))
    assert "[`keys`](../keys/README.md)" in page


def test_a_readme_shows_each_states_picture():
    assert '<img src="images/expiring.png"' in clearance_readme()


def test_a_readme_says_when_a_state_shows_nothing():
    assert "| **away from stations** | *shows nothing* |" in clearance_readme()


def test_a_readmes_states_are_a_row_each_name_then_picture():
    assert '| **expiring** | <img src="images/expiring.png"' in clearance_readme()


def test_strips_are_shown_at_their_own_width():
    assert 'width="640"' in clearance_readme()


def test_bigger_components_are_scaled_down():
    assert 'width="560"' in clearance_readme(size=(1600, 900))


@pytest.mark.parametrize("name", list(COMPONENTS))
def test_each_components_readme_is_up_to_date_with_its_states(name):
    """Run `python -m helper.harness --readmes` after changing a states file."""
    text = (Path(harness.web.COMPONENTS_DIR) / name / "README.md").read_text()
    for state, _ in COMPONENTS[name].states:
        assert f"| **{state}** |" in text, f"{name}: {state!r} isn't in its README"


TOP_STRIP = WIDGETS["top-strip"]


def top_strip_readme():
    pictures = [("just launched", "just-launched.png")]
    return harness.widget_readme(TOP_STRIP, pictures, (1280, 40))


def test_a_named_widget_readme_starts_with_its_description():
    assert f"# top-strip\n\n{TOP_STRIP.description}\n" in top_strip_readme()


def test_a_named_widget_readme_links_its_components_readmes():
    assert "[`drive`](../../components/drive/README.md)" in top_strip_readme()


def test_a_named_widget_readme_says_where_it_docks():
    assert "| **Dock** | `game:top` |" in top_strip_readme()


def test_a_named_widget_readme_says_its_width():
    assert "| **Width** | the game's width |" in top_strip_readme()


def test_a_named_widget_readme_says_when_its_components_choose_its_size():
    assert "| **Height** | what its components need |" in top_strip_readme()


def test_a_named_widget_readme_shows_how_to_use_it():
    assert 'widget = "top-strip"' in top_strip_readme()


def test_a_named_widget_readme_shows_its_own_states():
    row = '| **just launched** | <img src="images/just-launched.png"'
    assert row in top_strip_readme()


@pytest.mark.parametrize("name", list(WIDGETS))
def test_each_named_widgets_readme_is_up_to_date_with_its_states(name):
    """Run `python -m helper.harness --readmes` after changing a named widget's states."""
    text = (Path(harness.web.DIR) / "widgets" / name / "README.md").read_text()
    for state, _ in WIDGETS[name].states:
        assert f"| **{state}** |" in text, f"{name}: {state!r} isn't in its README"


def test_a_named_widgets_state_sets_each_of_its_components_states():
    target = harness.widget_target("top-strip")
    values = {state: values for c, state, values in target.states if c == "widget"}
    drive, clearance = dict(COMPONENTS["drive"].states), dict(COMPONENTS["clearance"].states)
    assert values["just launched"] == {**clearance["none"], **drive["mass locked"]}


def show_url():
    return f"s/{harness.BLANK}/component.clearance/_oolite/show"


def test_the_latest_show_report_wins_whatever_order_they_arrive_in(clearance_server):
    post(clearance_server, show_url(), {"shown": True, "seq": 2})
    post(clearance_server, show_url(), {"shown": False, "seq": 1})  # older, arriving late
    assert clearance_server.shown[(harness.BLANK, "component.clearance")] == (2, True)


# -- which READMEs to remake -----------------------------------------------------------


def test_a_components_own_change_remakes_its_readme():
    assert harness.affected(["helper/web/components/tip/tip.css"]) == ["tip"]


def test_a_change_remakes_the_components_that_need_it_too():
    changed = harness.affected(["helper/web/components/keys/keys.js"], widgets={})
    assert set(changed) == {"keys", "all_keys"}


def test_a_change_to_the_shared_stylesheet_remakes_every_readme():
    assert harness.affected(["helper/web/lib/base.css"]) == [*COMPONENTS, *WIDGETS]


def test_a_change_to_the_themes_colours_remakes_every_readme():
    assert harness.affected(["helper/tk/components/style.py"]) == [*COMPONENTS, *WIDGETS]


def test_a_components_change_remakes_the_named_widgets_showing_it():
    assert harness.affected(["helper/web/components/drive/drive.js"]) == ["drive", "top-strip"]


def test_a_named_widgets_own_change_remakes_only_its_readme():
    assert harness.affected(["helper/web/widgets/top-strip/widget.toml"]) == ["top-strip"]


def test_a_change_to_reading_widget_settings_remakes_every_named_widget():
    assert harness.affected(["helper/widgets.py"]) == list(WIDGETS)


def test_the_readmes_and_pictures_themselves_dont_count():
    paths = [
        "helper/web/components/tip/README.md",
        "helper/web/components/tip/images/a.png",
        "helper/web/widgets/top-strip/README.md",
        "helper/web/widgets/top-strip/images/a.png",
    ]
    assert harness.affected(paths) == []


def test_files_outside_the_components_dont_count():
    assert harness.affected(["helper/state.py", "README.md"]) == []


def test_a_bar_makes_a_tabs_widget():
    (target,) = harness.targets(None, plugins={}, names=["keys|all_keys"])
    assert (target.spec.widget, target.spec.components) == ("tabs", ("keys", "all_keys"))


def test_a_plus_and_a_bar_cant_be_mixed():
    with pytest.raises(ValueError, match="not both"):
        harness.targets(None, plugins={}, names=["tip+keys|all_keys"])


def test_a_tabs_named_states_show_that_tab():
    (target,) = harness.targets(None, plugins={}, names=["keys|all_keys"])
    values = next(v for c, _, v in target.states if c == "all_keys")
    assert values["tabs"]["shown"] == "all_keys"


def test_pictures_stop_animations_so_they_come_out_the_same_each_run():
    assert "animation-play-state: paused" in harness.DEV_JS
