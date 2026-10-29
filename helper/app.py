"""The helper window: reads the game's messages into the model and lays out the components."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import tkinter as tk
import traceback

from . import config
from . import layout as layout_file
from .gamewindow import GameWindow
from .keys import load_keymap
from .layout import widgets_from_specs
from .markets import MarketStore
from .model import Model
from .plugins import WebWidgets, discover
from .screen import ANCHORS, choose_monitor, geometry, list_monitors
from .sources import DEFAULT_LOG, LogSource
from .tk.components import Style
from .tk.components.body import Body
from .tk.components.chips import ClearanceBadge, DriveChips, Tabs
from .tk.components.header import Details, Heading, Location, Status, Tip
from .tk.components.style import ACCENT, BG, DIM, FG, MONO, SANS
from .widgets import COMPONENTS, TkWidget, load_widgets

POLL_MS = 200
GAME_WINDOW_EVERY = 2  # ticks between game window checks (the #50 spike used 0.5 s)


def should_quit_for_messages(messages, first_poll, quit_with_game=True):
    """Whether a close message is a live exit rather than old log replay."""
    replay = first_poll or any(m.get("type") == "session" for m in messages)
    return quit_with_game and not replay and any(m.get("type") == "closed" for m in messages)


class HelperWindow:
    def __init__(
        self,
        root,
        source,
        geometry,
        quit_with_game=True,
        font_scale=1.0,
        layout="large",
        missing_equipment="grey",
        widgets=(),
        monitors=(),
        plugins=({}, {}),
        layout_path=layout_file.PATH,
        ui="web",
    ):
        self.root = root
        self.source = source
        self.quit_with_game = quit_with_game
        self.first_poll = True
        width = int(geometry.split("x", 1)[0])
        style = self.style = Style(width, layout, font_scale)

        markets = MarketStore()
        try:
            keymap, keymap_error = load_keymap(), None
        except Exception as e:  # show the problem instead of dying
            keymap, keymap_error = None, f"Couldn't read the game's key settings: {e}"
        # The layout (#50): config.toml's widgets, with the changes saved in layout.toml.
        defaults = widgets_from_specs(widgets)
        self.model = Model(
            markets=markets,
            keymap=keymap,
            missing_equipment=missing_equipment,
            layout=layout_file.load(defaults, layout_path),
        )
        self.model.on_error = lambda exc, where: self.report(exc)
        # The notice is shown until the game sends something.
        self.model.set_status(keymap_error=keymap_error, notice=markets.load_error)

        root.title("Oolite Key Helper")
        root.geometry(geometry)
        # Not managed by the window manager: no decorations, exact placement,
        # and it never takes focus from the game.
        root.overrideredirect(True)
        root.configure(bg=BG)
        root.bind("<Button-3>", lambda e: root.destroy())  # right-click quits

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=style.px(40), pady=style.px(24, 8))
        context_label = tk.Label(header, font=style.font(SANS, 44, "bold"), fg=ACCENT, bg=BG)
        narrow = style.columns == 1  # stack the details under the heading
        context_label.pack(side="top" if narrow else "left", anchor="w")
        where_label = tk.Label(header, font=style.font(SANS, 28, "bold"), bg=BG)
        where_label.pack(
            side="top" if narrow else "left", anchor="w" if narrow else "s", padx=style.px(24, 0)
        )
        detail_label = tk.Label(
            header, font=style.font(SANS, 20), fg=DIM, bg=BG, justify="left" if narrow else "right"
        )
        if narrow:
            detail_label.pack(side="top", anchor="w")
        else:
            detail_label.pack(side="right", anchor="s", pady=style.px(0, 10))

        tabs = tk.Frame(root, bg=BG)
        tabs.pack(fill="x", padx=style.px(40), pady=style.px(0, 8))

        tip_label = tk.Label(
            root,
            font=style.font(SANS, 20),
            fg=FG,
            bg=BG,
            anchor="w",
            justify="left",
            wraplength=width - style.px(80),
        )
        tip_label.pack(fill="x", padx=style.px(40))

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=style.px(28))

        status_label = tk.Label(root, font=style.font(MONO, 12), fg=DIM, bg=BG, anchor="w")
        status_label.pack(fill="x", padx=style.px(40), pady=style.px(0, 12))

        model = self.model
        self.components = [
            Heading(model, style, context_label),
            Location(model, style, where_label),
            Details(model, style, detail_label),
            Tabs(model, style, tabs),
            DriveChips(model, style, tabs),
            ClearanceBadge(model, style, tabs),
            Tip(model, style, tip_label),
            Status(model, style, status_label),
        ]
        self.body = Body(model, style, body)
        self.components.append(self.body)
        # Widgets (#50): components in their own windows. Docked ones need the game
        # window's position, polled a few times a second only when there are any.
        # Widgets are web pages in the web host (#59): plugins, and pages the
        # helper generates for its components. Tk shows the components instead
        # with ui = "tk", or if the web host can't start.
        self.monitors = monitors
        self.widgets = []
        manifests, broken = plugins
        components = COMPONENTS if ui == "web" else None
        self.plugins = WebWidgets(
            model, manifests, broken, monitors, components=components, fallback=self.tk_widgets
        )
        if components is None:
            self.tk_widgets([w.id for w in model.layout if w.spec.components[0] in COMPONENTS])
        saver = layout_file.LayoutFile(defaults, layout_path)
        model.subscribe("layout", saver.save, initial=False)
        self.game_window = GameWindow() if self.widgets or self.plugins.widgets else None
        self.ticks = 0
        self.tick()

    def tk_widgets(self, ids):
        """Show these widgets' components in Tk windows (the fallback)."""
        self.widgets += [TkWidget(self.root, self.model, wid, self.monitors) for wid in ids]

    def tick(self):
        # Any unexpected error is reported and polling carries on: stopping here
        # would leave the window showing stale information with no sign why.
        try:
            if not self.poll_once():
                return  # the game closed and the window went with it
        except Exception as exc:
            self.report(exc)
            self.model.notify()  # show the error now, even if polling keeps failing
        self.root.after(POLL_MS, self.tick)

    def poll_once(self):
        """Read and apply new messages and notify the components; False once the window is gone."""
        messages = self.source.poll()
        quit_for_game = should_quit_for_messages(messages, self.first_poll, self.quit_with_game)
        applied = None
        for msg in messages:
            try:
                self.model.dispatch(msg)
            except Exception as exc:  # one bad message mustn't drop the rest
                self.report(exc, msg)
                continue
            applied = msg
            if msg.get("type") == "closed" and quit_for_game:
                self.root.destroy()
                return False
        if applied is not None:
            self.model.set_status(error=None, notice=None, last_message=json.dumps(applied))
        self.first_poll = False
        self.ticks += 1
        if self.game_window is not None and self.ticks % GAME_WINDOW_EVERY == 1:
            self.model.dispatch(self.game_window.poll())
        self.plugins.tick()
        self.model.notify()  # every tick: countdowns and blinking need the clock
        return True

    def report(self, exc, msg=None):
        error = f"{type(exc).__name__}: {exc}"
        if error != self.model.status.get("error"):  # once per distinct error, not every tick
            print(
                f"oolite-helper: {error}" + (f" (message: {msg})" if msg else ""), file=sys.stderr
            )
            traceback.print_exc()
            self.model.set_status(error=error)


def single_instance_lock():
    """Hold an exclusive lock for the life of the process; None if another helper has it."""
    path = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()), "oolite-helper.lock"
    )
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def main():
    parser = argparse.ArgumentParser(
        description="Context-aware key helper for Oolite.",
        epilog=f"Window settings can also go in {config.PATH} (see README).",
    )
    parser.add_argument("--log", default=DEFAULT_LOG, help="path to Oolite's Latest.log")
    parser.add_argument("--stay", action="store_true", help="keep running when the game exits")
    parser.add_argument(
        "--list-screens", action="store_true", help="list the monitors xrandr reports and exit"
    )
    win = parser.add_argument_group("window placement (overrides the config file)")
    win.add_argument(
        "--screen", help="monitor name from --list-screens (default: first non-primary monitor)"
    )
    win.add_argument("--width", help="pixels or percent of the screen, e.g. 40%%")
    win.add_argument("--height", help="pixels or percent of the screen")
    win.add_argument("--anchor", choices=ANCHORS, help="where on the screen to sit")
    win.add_argument("--margin", type=int, help="pixels from the screen edges")
    win.add_argument(
        "--layout",
        choices=config.LAYOUTS,
        help="compact: smaller text and spacing, more key columns",
    )
    win.add_argument("--font-scale", type=float, help="text size multiplier, e.g. 0.8")
    win.add_argument("--geometry", help="exact X geometry WxH+X+Y; overrides the others")
    args = parser.parse_args()

    monitors = list_monitors()
    if args.list_screens:
        for m in monitors:
            print(m)
        return

    settings = config.load_window_settings(
        overrides={
            "screen": args.screen,
            "width": args.width,
            "height": args.height,
            "anchor": args.anchor,
            "margin": args.margin,
            "layout": args.layout,
            "font_scale": args.font_scale,
            "geometry": args.geometry,
        }
    )
    window_geometry = settings["geometry"]
    if not window_geometry:
        monitor = choose_monitor(monitors, settings["screen"])
        if monitor is None:
            raise SystemExit(
                "No monitors found via xrandr; set geometry in the config "
                "file or use --geometry WxH+X+Y"
            )
        window_geometry = geometry(
            monitor, settings["width"], settings["height"], settings["anchor"], settings["margin"]
        )

    lock = single_instance_lock()
    if lock is None:
        print("oolite-helper is already running", file=sys.stderr)
        return

    plugins = discover()
    root = tk.Tk()
    helper = HelperWindow(
        root,
        LogSource(args.log),
        window_geometry,
        quit_with_game=not args.stay,
        font_scale=float(settings["font_scale"]),
        layout=settings["layout"],
        missing_equipment=settings["missing_equipment"],
        widgets=load_widgets(plugins=set(plugins[0]) | set(plugins[1])),
        monitors=monitors,
        plugins=plugins,
        ui=settings["ui"],
    )
    try:
        root.mainloop()
    finally:
        helper.plugins.close()
