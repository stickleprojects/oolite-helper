import subprocess

import pytest

from helper import screen


def test_list_monitors_parses_primary_and_negative_offsets(monkeypatch):
    output = """Monitors: 2
 0: +*DP-1 1920/521x1080/293+0+0  DP-1
 1: +eDP-1 1600/345x900/194+-1600+-200  eDP-1
"""
    monkeypatch.setattr(
        screen.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )
    monitors = screen.list_monitors()
    assert monitors == [
        screen.Monitor("DP-1", True, 1920, 1080, 0, 0),
        screen.Monitor("eDP-1", False, 1600, 900, -1600, -200),
    ]
    assert screen.geometry(monitors[1], 294, 900) == "294x900+-1600+-200"


@pytest.mark.parametrize(
    ("anchor", "x", "y"),
    [
        ("top-left", -1910, 130),
        ("top", -1616, 130),
        ("top-right", -1322, 130),
        ("left", -1910, 275),
        ("center", -1616, 275),
        ("right", -1322, 275),
        ("bottom-left", -1910, 420),
        ("bottom", -1616, 420),
        ("bottom-right", -1322, 420),
    ],
)
def test_geometry_every_anchor_and_percent_size(anchor, x, y):
    monitor = screen.Monitor("test", False, 1000, 600, -1920, 120)
    assert screen.geometry(monitor, "40%", "50%", anchor, 10) == f"392x290+{x}+{y}"


def test_geometry_pixel_size_is_capped_and_anchor_validated():
    monitor = screen.Monitor("test", False, 1000, 600, 10, 20)
    assert screen.geometry(monitor, 1200, 700, "center", 10) == "980x580+20+30"
    with pytest.raises(SystemExit, match="Unknown anchor"):
        screen.geometry(monitor, anchor="middle")


def test_choose_monitor_named_default_fallback_and_error():
    primary = screen.Monitor("DP-1", True, 1920, 1080, 0, 0)
    secondary = screen.Monitor("HDMI-1", False, 1280, 720, 1920, 0)
    assert screen.choose_monitor([primary, secondary]) is secondary
    assert screen.choose_monitor([primary, secondary], "DP-1") is primary
    assert screen.choose_monitor([primary]) is primary
    assert screen.choose_monitor([]) is None
    with pytest.raises(SystemExit, match="available: DP-1, HDMI-1"):
        screen.choose_monitor([primary, secondary], "missing")


def test_list_monitors_handles_xrandr_errors(monkeypatch):
    for error in (OSError("not installed"), subprocess.CalledProcessError(1, "xrandr")):
        def fail(*args, **kwargs):
            raise error

        monkeypatch.setattr(screen.subprocess, "run", fail)
        assert screen.list_monitors() == []
