"""Widgetwindows driven with the mouse (#141), on a hidden X display:

    OOLITE_HELPER_LIVE_UI=1 .venv/bin/python -m pytest tests/test_frame_live.py

Needs Xvfb, marco (the desktop's window manager, so focus behaves as it does
in play), xdotool, scrot, GTK 3, WebKit2 4.1 and xauth. CI runs it in its
Live UI job (scripts/run-ci-checks.sh --only live).
OOLITE_HELPER_LIVE_UI=here uses the display you're on instead of a hidden one
(no Xvfb needed): keep your hands off the mouse while it runs.

A stand-in game window has keyboard focus and prints the keys it gets. The
real web host shows a widgetwindow's page over it; xdotool clicks, drags and
scrolls it as a player would, and after each the test types a key and checks
the game got it: nothing the player does to a widgetwindow takes the keyboard
from the game.
"""

import os
import select
import shutil
import subprocess
import sys
import time

import pytest

from helper.layout import widgets_from_specs, windows_from_specs
from helper.model import Model
from helper.plugins import WebWidgets, discover
from helper.screen import Monitor
from helper.settings import COMPONENTS
from helper.webhost import WebHost
from helper.webhost.host import in_column
from helper.widgets import title_height
from tests.configs import load_widgets, load_widgetwindows

HERE = os.environ.get("OOLITE_HELPER_LIVE_UI") == "here"
TOOLS = ("xdotool", "scrot", "xauth") if HERE else ("Xvfb", "marco", "xdotool", "scrot", "xauth")
pytestmark = pytest.mark.skipif(
    not os.environ.get("OOLITE_HELPER_LIVE_UI") or not all(map(shutil.which, TOOLS)),
    reason=f"set OOLITE_HELPER_LIVE_UI=1 or =here (needs {', '.join(TOOLS)})",
)
DISPLAY = os.environ.get("DISPLAY", ":0") if HERE else ":97"
SCREEN = Monitor("V", True, 1280, 800, 0, 0)
# A short widgetwindow: its hold widget (400 px) is taller than its column.
CONFIG = """
[[widgetwindows]]
id = "w"
title = "Test"
screen = "V"
x = 600
y = 100
width = 400
height = 200
widgets = [{ components = ["hold"], height = 400 }]
"""
# The stand-in game: takes focus like a normal window, prints each key it gets.
# A widgetwindow with a plugin's widget, drawn all in SWATCH, between two holds:
# scrolled, the swatch goes up under the title bar.
SWATCH = (255, 0, 255)
SWATCH_CONFIG = """
[[widgetwindows]]
id = "w"
title = "Test"
screen = "V"
x = 600
y = 100
width = 400
height = 300
widgets = [
  { components = ["hold"], height = 150 },
  { components = ["swatch"], height = 120 },
  { components = ["hold"], height = 400 },
]
"""
SWATCH_MANIFEST = """\
name = "swatch"
version = "1.0.0"
api = 1
topics = ["context"]
width = 200
height = 120
"""
SWATCH_PAGE = '<html style="background: #ff00ff; height: 100%"><body></body></html>'
SCROLLING_SWATCH_PAGE = (
    '<html style="background: #ff00ff"><body style="margin: 0">'
    '<div style="height: 240px"></div></body></html>'
)
GAME = """
import sys, tkinter
root = tkinter.Tk(className="fakegame")
root.title("fake game")
root.geometry("1280x800+0+0")
root.bind("<KeyPress>", lambda e: (print("key", e.keysym), sys.stdout.flush()))
root.mainloop()
"""


def xdotool(*args, env):
    return subprocess.run(
        ["xdotool", *map(str, args)], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()


def wait(check, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(scope="module")
def desktop(tmp_path_factory):
    """(env, the game's process): a hidden display with marco and the stand-in game, focused."""
    env = {**os.environ, "DISPLAY": DISPLAY}
    procs = []
    try:
        if not HERE:
            env.pop("XAUTHORITY", None)
            xvfb = ["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"]
            procs.append(subprocess.Popen(xvfb))
            started = lambda: os.path.exists(f"/tmp/.X11-unix/X{DISPLAY[1:]}")  # noqa: E731
            assert wait(started), "Xvfb didn't start"
            wm_log = tmp_path_factory.mktemp("wm") / "marco.log"
            wm = ["marco", "--replace"]
            with open(wm_log, "w") as log:
                procs.append(subprocess.Popen(wm, env=env, stdout=log, stderr=log))
        game = subprocess.Popen(
            [sys.executable, "-c", GAME], env=env, stdout=subprocess.PIPE, text=True
        )
        procs.append(game)

        def found():
            search = ["xdotool", "search", "--name", "fake game"]
            return subprocess.run(search, env=env, capture_output=True).stdout

        assert wait(found), "the stand-in game didn't open"
        window = found().split()[0].decode()
        activate = ["xdotool", "windowactivate", "--sync", window]
        # The window manager may still be starting (slower in CI): until it is, it can't activate.
        if not wait(lambda: subprocess.run(activate, env=env, capture_output=True).returncode == 0):
            why = "" if HERE else f"marco {'running' if procs[1].poll() is None else 'exited'}: "
            why += "" if HERE else wm_log.read_text()[-2000:]
            pytest.fail(f"couldn't give the stand-in game the keyboard. {why}")
        yield env, game
    finally:
        for proc in reversed(procs):
            proc.kill()
            proc.wait()


def open_frame(tmp_path, monkeypatch, config, manifests=None):
    """The widgetwindow config.toml's text makes, shown and loaded: (made, model).
    made.pump(seconds) runs the helper for a while; made.events is every web host
    event so far."""
    monkeypatch.setenv("DISPLAY", DISPLAY)
    if not HERE:
        monkeypatch.delenv("XAUTHORITY", raising=False)
    path = tmp_path / "config.toml"
    path.write_text(config)
    plugins = tuple(manifests or ())
    windows = windows_from_specs(load_widgetwindows(path, plugins))
    model = Model(layout=widgets_from_specs(load_widgets(path, plugins)), windows=windows)
    host = WebHost()
    events = []
    poll = host.poll

    def recorded():
        found = poll()
        events.extend({**e, "at": time.monotonic()} for e in found)
        return found

    host.poll = recorded
    made = WebWidgets(model, manifests or {}, host=host, components=COMPONENTS, monitors=[SCREEN])
    made.pump = lambda seconds=0.3: pump(made, model, seconds)
    made.events = events
    loaded = lambda: any(e["ev"] == "loaded" for e in events)  # noqa: E731
    assert wait(lambda: pump(made, model, 0) or loaded(), 20), "the page didn't load"
    made.pump(1)  # drawn
    return made, model


@pytest.fixture
def frame(desktop, tmp_path, monkeypatch):
    """The widgetwindow, shown and loaded: (mouse, model, made) where
    mouse(...) runs xdotool on the hidden display."""
    env, _ = desktop
    made, model = open_frame(tmp_path, monkeypatch, CONFIG)
    yield (lambda *args: xdotool(*args, env=env)), model, made
    made.close()


def open_swatch(tmp_path, monkeypatch, page):
    """SWATCH_CONFIG's widgetwindow, its swatch's page being page: (made, model)."""
    root = tmp_path / "plugins" / "swatch"
    root.mkdir(parents=True)
    (root / "plugin.toml").write_text(SWATCH_MANIFEST)
    (root / "index.html").write_text(page)
    made, model = open_frame(tmp_path, monkeypatch, SWATCH_CONFIG, discover(root.parent)[0])
    assert wait(lambda: made.pump(0) or placeholders(made), 10), "no placeholders came"
    made.pump(0.5)
    return made, model


@pytest.fixture
def swatch(desktop, tmp_path, monkeypatch):
    """SWATCH_CONFIG's widgetwindow: (mouse, model, made), as frame."""
    made, model = open_swatch(tmp_path, monkeypatch, SWATCH_PAGE)
    yield (lambda *args: xdotool(*args, env=desktop[0])), model, made
    made.close()


@pytest.fixture
def scrolling_swatch(desktop, tmp_path, monkeypatch):
    """As swatch, but its page is taller than its widget, so it scrolls itself."""
    made, model = open_swatch(tmp_path, monkeypatch, SCROLLING_SWATCH_PAGE)
    yield (lambda *args: xdotool(*args, env=desktop[0])), model, made
    made.close()


def pump(made, model, seconds):
    end = time.monotonic() + seconds
    while True:
        model.notify()
        made.tick()
        if time.monotonic() >= end:
            return False
        time.sleep(0.02)


def game_gets_keys(mouse, game):
    """Types a key; True if the stand-in game got it."""
    mouse("key", "k")
    ready, _, _ = select.select([game.stdout], [], [], 2)
    return bool(ready) and game.stdout.readline().strip() == "key k"


def spec(model):
    return model.topic("windows")[0].spec


def bar(model):
    """(x, y, w, title bar height) of the widgetwindow now."""
    window = spec(model)
    return window.x, window.y, window.width, title_height(window)


def button(model, n):
    """The middle of the nth button from the bar's right end (0: ×, 1: ✎, 2: ⚓)."""
    x, y, w, h = bar(model)
    em = max(8, round(h * 0.5))
    return x + w - round(em * (0.9 + 1.7 * n)), y + h // 2


def click(mouse, made, point):
    mouse("mousemove", *point, "click", 1)
    made.pump()


def test_clicking_its_pencil_turns_edit_mode_on_and_the_game_keeps_the_keyboard(frame, desktop):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    assert "w" in made.editing
    assert game_gets_keys(mouse, desktop[1])


def test_clicking_its_pencil_again_turns_edit_mode_off(frame):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    click(mouse, made, button(model, 1))
    assert "w" not in made.editing


def test_dragging_its_title_bar_in_edit_mode_moves_it(frame, desktop):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    x, y, _, h = bar(model)
    mouse("mousemove", x + 40, y + h // 2, "mousedown", 1)
    made.pump(0.2)
    for step in range(1, 11):
        mouse("mousemove", x + 40 - 30 * step, y + h // 2 + 30 * step)
        made.pump(0.05)
    mouse("mouseup", 1)
    made.pump()
    assert (spec(model).x, spec(model).y) != (600, 100)
    assert game_gets_keys(mouse, desktop[1])


def test_dragging_its_title_bar_outside_edit_mode_does_nothing(frame):
    mouse, model, made = frame
    x, y, _, h = bar(model)
    mouse("mousemove", x + 40, y + h // 2, "mousedown", 1)
    mouse("mousemove", x - 200, y + 200)
    mouse("mouseup", 1)
    made.pump()
    assert (spec(model).x, spec(model).y) == (600, 100)


def test_dragging_its_right_edge_in_edit_mode_widens_it(frame, desktop):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    x, y, w, _ = bar(model)
    mouse("mousemove", x + w - 2, y + 100, "mousedown", 1)
    for step in range(1, 7):
        mouse("mousemove", x + w - 2 + 10 * step, y + 100)
        made.pump(0.05)
    mouse("mouseup", 1)
    made.pump()
    assert spec(model).width > 400
    assert game_gets_keys(mouse, desktop[1])


def place_in_list(model, row):
    """The middle of a row of its ⚓ list, which opens under the bar's right
    end: with one screen and no game, one column, headed "V" (row 0), then
    left, right, top, bottom and Float."""
    x, y, w, h = bar(model)
    em = max(8, round(h * 0.5))
    line = round(em * 1.15) + 4  # its text's line, and 2 px above and below
    return x + w - 2 * em, y + h + 1 + line * row + line // 2


def test_picking_a_place_from_its_anchor_list_docks_it_there(frame, desktop):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    click(mouse, made, button(model, 2))
    click(mouse, made, place_in_list(model, 1))  # left
    assert spec(model).dock == "screen:V:left"
    assert game_gets_keys(mouse, desktop[1])


def test_its_cross_in_edit_mode_closes_it(frame):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    click(mouse, made, button(model, 0))
    assert not model.topic("windows")[0].open


def test_its_cross_outside_edit_mode_does_nothing(frame):
    mouse, model, made = frame
    click(mouse, made, button(model, 0))
    assert model.topic("windows")[0].open


def test_the_wheel_scrolls_its_column_and_the_game_keeps_the_keyboard(frame, desktop, tmp_path):
    mouse, model, made = frame
    x, y, w, h = bar(model)
    column = f"{x},{y + h},{w},{200 - h}"

    def shot(name):
        path = tmp_path / name
        subprocess.run(["scrot", "-a", column, "-o", str(path)], env=desktop[0], check=True)
        return path.read_bytes()

    before = shot("before.png")
    mouse("mousemove", x + w // 2, y + 120)
    for _ in range(5):
        mouse("click", 5)  # wheel down
    made.pump(0.5)
    assert shot("after.png") != before
    assert game_gets_keys(mouse, desktop[1])


# -- a plugin's view over its placeholder (#141 step 3) ------------------------


def placeholders(made):
    """Every placeholders event so far with the swatch's in it, oldest first."""
    return [e for e in made.events if e["ev"] == "placeholders" and e["rects"]]


def shown_part(event):
    """Where the swatch's view should show in the window, (x, y, w, h), as the
    page's event says: its placeholder cut to the column. None if none shows."""
    if not event["rects"]:
        return None
    (rect,) = event["rects"].values()
    fit = in_column(tuple(rect), tuple(event["column"]))
    return None if fit is None else fit[0]


def window_shot(env, model, path):
    """The widgetwindow's pixels now: (width, height, rgb bytes)."""
    window = spec(model)
    area = f"{window.x},{window.y},{window.width},{window.height}"
    subprocess.run(["scrot", "-a", area, "-o", str(path)], env=env, check=True)
    data = path.read_bytes()
    fields, at = [], 0
    while len(fields) < 4:  # P6, width, height, maxval; # starts a comment
        while data[at : at + 1].isspace():
            at += 1
        if data[at : at + 1] == b"#":
            at = data.index(b"\n", at)
            continue
        end = at
        while not data[end : end + 1].isspace():
            end += 1
        fields.append(data[at:end])
        at = end
    width, height = int(fields[1]), int(fields[2])
    return width, height, data[at + 1 : at + 1 + width * height * 3]


def swatch_box(env, model, path):
    """(x, y, w, h) in the window of the pixels drawn in SWATCH, or None."""
    width, height, rgb = window_shot(env, model, path)
    near = lambda i: all(abs(rgb[i + c] - SWATCH[c]) < 24 for c in range(3))  # noqa: E731
    rows = [y for y in range(height) if any(near((y * width + x) * 3) for x in range(width))]
    if not rows:
        return None
    cols = [x for x in range(width) if any(near((y * width + x) * 3) for y in rows)]
    return cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1


def close_to(box, part, px=1):
    if box is None or part is None:
        return box is part
    return all(abs(a - b) <= px for a, b in zip(box, part, strict=True))


def wheel(mouse, model, clicks=1):
    """Turns the wheel down over the hold above the swatch."""
    window = spec(model)
    mouse("mousemove", window.x + window.width // 2, window.y + 60)
    for _ in range(clicks):
        mouse("click", 5)


def test_the_wheel_scrolls_a_plugin_view_with_its_column(swatch, desktop, tmp_path):
    mouse, model, made = swatch
    before = placeholders(made)[-1]
    wheel(mouse, model)
    made.pump(0.1)
    after = placeholders(made)[-1]
    assert after["rects"] != before["rects"]
    assert close_to(swatch_box(desktop[0], model, tmp_path / "shot.ppm"), shown_part(after))


def test_a_plugin_view_keeps_up_with_a_long_scroll(swatch, desktop, tmp_path):
    mouse, model, made = swatch
    tops = []
    for step in range(6):
        wheel(mouse, model)
        made.pump(0.03)
        box = swatch_box(desktop[0], model, tmp_path / f"shot{step}.ppm")
        made.pump(0)
        tops.append((box, [shown_part(e) for e in placeholders(made)]))
    for box, parts in tops:
        # The view is where one of the page's last few reports said: the page
        # reports once an animation frame, and a wheel step takes several.
        assert any(close_to(box, part) for part in parts[-3:]), (box, parts[-3:])
    assert sum(box is not None for box, _ in tops) >= 4  # it was in sight as it scrolled


def test_a_plugin_scrolled_under_the_title_bar_is_cut_off_at_the_column(swatch, desktop, tmp_path):
    mouse, model, made = swatch
    first = placeholders(made)[-1]
    (rect,) = first["rects"].values()
    column = first["column"]
    for _ in range(20):  # until the swatch is about half out of the column
        (now,) = placeholders(made)[-1]["rects"].values()
        if now[1] <= column[1] - rect[3] // 2:
            break
        wheel(mouse, model)
        made.pump(0.2)
    made.pump(0.3)
    last = placeholders(made)[-1]
    (now,) = last["rects"].values()
    assert column[1] - rect[3] < now[1] < column[1]  # partly scrolled out
    box = swatch_box(desktop[0], model, tmp_path / "shot.ppm")
    assert box is not None and box[1] >= column[1]  # none over the title bar
    assert close_to(box, shown_part(last))


def test_clicking_a_plugin_view_keeps_the_games_keyboard(swatch, desktop):
    mouse, model, made = swatch
    (rect,) = placeholders(made)[-1]["rects"].values()
    window = spec(model)
    click(mouse, made, (window.x + rect[0] + rect[2] // 2, window.y + rect[1] + rect[3] // 2))
    assert game_gets_keys(mouse, desktop[1])


def swatch_top(made):
    """The top of the swatch's placeholder, as the page last said."""
    (rect,) = placeholders(made)[-1]["rects"].values()
    return rect[1]


def wheel_over_swatch(mouse, made, model, clicks=1):
    window = spec(model)
    mouse("mousemove", window.x + 200, window.y + swatch_top(made) + 60)
    for _ in range(clicks):
        mouse("click", 5)
        made.pump(0.15)
    made.pump(0.5)


def test_a_plugin_that_can_scroll_takes_the_wheel_itself(scrolling_swatch):
    mouse, model, made = scrolling_swatch
    top = swatch_top(made)
    wheel_over_swatch(mouse, made, model)
    assert swatch_top(made) == top  # the column stayed put


def test_at_its_end_a_plugin_passes_the_wheel_to_the_column(scrolling_swatch):
    mouse, model, made = scrolling_swatch
    top = swatch_top(made)
    wheel_over_swatch(mouse, made, model, clicks=6)  # 120 px of its own, then the column's
    assert swatch_top(made) < top


def test_the_wheel_over_a_plugin_that_cant_scroll_scrolls_the_column(swatch):
    mouse, model, made = swatch
    top = swatch_top(made)
    wheel_over_swatch(mouse, made, model)
    assert swatch_top(made) < top
