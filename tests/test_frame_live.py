"""Widgetwindows driven with the mouse (#141), on a hidden X display:

    OOLITE_HELPER_LIVE_UI=1 .venv/bin/python -m pytest tests/test_frame_live.py

Needs Xvfb, marco (the desktop's window manager, so focus behaves as it does
in play), xdotool, scrot, GTK 3, WebKit2 4.1 and xauth. Not run in CI.
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
from helper.plugins import WebWidgets
from helper.screen import Monitor
from helper.settings import COMPONENTS
from helper.webhost import WebHost
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
            wm = ["marco", "--replace"]
            procs.append(subprocess.Popen(wm, env=env, stderr=subprocess.DEVNULL))
            time.sleep(1)
        game = subprocess.Popen(
            [sys.executable, "-c", GAME], env=env, stdout=subprocess.PIPE, text=True
        )
        procs.append(game)

        def found():
            search = ["xdotool", "search", "--name", "fake game"]
            return subprocess.run(search, env=env, capture_output=True).stdout

        assert wait(found), "the stand-in game didn't open"
        window = found().split()[0].decode()
        xdotool("windowactivate", "--sync", window, env=env)
        yield env, game
    finally:
        for proc in reversed(procs):
            proc.kill()
            proc.wait()


@pytest.fixture
def frame(desktop, tmp_path, monkeypatch):
    """The widgetwindow, shown and loaded: (mouse, model, made, page) where
    mouse(...) runs xdotool on the hidden display and page is its own page's rect."""
    env, game = desktop
    monkeypatch.setenv("DISPLAY", DISPLAY)
    if not HERE:
        monkeypatch.delenv("XAUTHORITY", raising=False)
    path = tmp_path / "config.toml"
    path.write_text(CONFIG)
    windows = windows_from_specs(load_widgetwindows(path))
    model = Model(layout=widgets_from_specs(load_widgets(path)), windows=windows)
    host = WebHost()
    events = []
    poll = host.poll

    def recorded():
        found = poll()
        events.extend(found)
        return found

    host.poll = recorded
    made = WebWidgets(model, {}, host=host, components=COMPONENTS, monitors=[SCREEN])
    made.pump = lambda seconds=0.3: pump(made, model, seconds)
    loaded = lambda: any(e["ev"] == "loaded" for e in events)  # noqa: E731
    assert wait(lambda: pump(made, model, 0) or loaded(), 20), "the page didn't load"
    made.pump(1)  # drawn
    yield (lambda *args: xdotool(*args, env=env)), model, made
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


def test_dragging_its_right_edge_in_edit_mode_widens_it(frame):
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


def test_its_anchor_opens_the_list_of_places_under_its_bar(frame, desktop):
    mouse, model, made = frame
    click(mouse, made, button(model, 1))
    before = mapped(mouse)
    click(mouse, made, button(model, 2))
    assert len(mapped(mouse)) > len(before)
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


def mapped(mouse):
    """The ids of the windows shown now."""
    return set(mouse("search", "--onlyvisible", "--name", "").split())
