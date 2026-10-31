from helper.platform.linux_x11.gamewindow import (
    GameWindow,
    parse_frame_extents,
    parse_geometry,
    parse_window_id,
)

XWININFO = """
xwininfo: Window id: 0x5400014 "Oolite v1.92.1 - Mar 19 2026"

  Absolute upper-left X:  1282
  Absolute upper-left Y:  204
  Relative upper-left X:  2
  Relative upper-left Y:  24
  Width: 1280
  Height: 720
  Map State: IsViewable
"""


def test_parses_xwininfo_xprop_and_xdotool_output():
    assert parse_geometry(XWININFO) == (1282, 204, 1280, 720)
    assert parse_geometry(XWININFO.replace("IsViewable", "IsUnMapped")) is None  # minimised
    assert parse_geometry("") is None
    assert parse_frame_extents("_NET_FRAME_EXTENTS(CARDINAL) = 2, 2, 24, 2") == (2, 2, 24, 2)
    assert parse_frame_extents("_NET_FRAME_EXTENTS:  not found.") == (0, 0, 0, 0)
    assert parse_window_id("_NET_ACTIVE_WINDOW(WINDOW): window id # 0x5400014") == 0x5400014
    assert parse_window_id("88080404\n") == 88080404


class FakeX:
    def __init__(self, active="0x5400014", found="88080404"):
        self.active, self.found = active, found
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args[0])
        if args[:2] == ("xdotool", "search"):
            return self.found
        if args[0] == "xwininfo":
            return XWININFO
        if args[:2] == ("xprop", "-root"):
            return f"_NET_ACTIVE_WINDOW(WINDOW): window id # {self.active}"
        return "_NET_FRAME_EXTENTS(CARDINAL) = 2, 2, 24, 2"


def test_poll_reports_geometry_frame_and_whether_the_game_is_active():
    x = FakeX()
    action = GameWindow(run=x).poll()
    assert action == {
        "type": "window/game",
        "geometry": (1282, 204, 1280, 720),
        "frame": (2, 2, 24, 2),
        "active": True,  # 0x5400014 == 88080404
    }
    x.active = "0x3800004"  # VS Code
    assert GameWindow(run=x).poll()["active"] is False


def test_no_game_window_means_no_geometry_and_it_keeps_looking():
    x = FakeX(found="")
    window = GameWindow(run=x)
    assert window.poll() == {
        "type": "window/game",
        "geometry": None,
        "frame": (0, 0, 0, 0),
        "active": False,
    }
    window.poll()
    assert x.calls.count("xdotool") == 2
