"""The web host process (#59): plugin pages in locked-down WebKit views.

Run by the helper as `/usr/bin/python3 -I host.py` (it needs the system's
GTK 3 and WebKit2 4.1 bindings, which the helper's venv doesn't have), so it
imports nothing from the helper. It talks JSON lines: commands on stdin,
events on stdout. See PROTOCOL in helper/webhost/__init__.py.

Each plugin window is a GTK popup (override-redirect, never takes focus: the
#59 spike checked clicks leave keyboard focus on the game) holding a WebKit
view with its own ephemeral web context. The page's JavaScript runs in
WebKit's sandboxed web process; the helper starts this process with the
environment from webhost.sandbox_env() so that sandbox can't see the real
~/.cache, a trusted X cookie or the sound server.

A frame is a widgetwindow (#124): one popup holding the views opened into
it instead of windows of their own. Its own page (#141), the "chrome", fills
it: the title bar and a column of the helper's widgets, drawn by the helper's
lib/frame.js, with its edit-mode edges and ⚓ list. It alone gets
window.ooliteFrame, for the bar's buttons, for starting a move or a resize, for
a place picked, and to say where the placeholders in its column are: each
plugin's view is laid over its placeholder, clipped to the column (in_column),
so it scrolls with the column but keeps its own web process. Drags follow the
pointer here, and the ghost outline where a moved window lands is GTK.

The pure functions at the top (no GTK) are tested in CI.
"""

import json
import mimetypes
import os
import sys
import urllib.parse

PROTOCOL = 5
API = 1  # the version of the page's `oolite` object
SCHEME = "plugin"

MIME = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".txt": "text/plain",
}
SIZE_LIMITS = (16, 4000)  # px: no vanishing or screen-covering windows (oolite.show hides)
LOG_TEXT_LIMIT = 500
# Widgetwindows' edit mode (#124): the edges its page may resize it from, and
# the ghost outline's width (as the page's edges, lib/frame.js).
EDGES = ("left", "right", "top", "bottom")
EDGE_PX = 6
MIN_PX = 80  # as widgets.MIN_SIZE
DRAG_REPORT_SECONDS = 0.04  # how often a dragged edge's rect goes to the helper
EDIT_COLOUR = "#ffb000"  # the helper's accent: lit ✎ and edges
PAGE_MESSAGES_PER_SECOND = 20  # more than this from one page are dropped
# A frame's page sends placeholder rects at most once an animation frame while
# its column scrolls, so they have a budget of their own.
PLACEHOLDER_MESSAGES_PER_SECOND = 120
PLACEHOLDER_LIMIT = 32  # plugin widgets in one widgetwindow
ACTION_LIMIT = 2000  # characters of JSON in one dispatched action
# Files the helper provides to every plugin under plugin://<name>/_oolite/
# (theme.css, dev.js): given in the "open" command, never read from disk.
EXTRAS = "_oolite/"


def csp(plugin):
    """The Content-Security-Policy sent with every file of a plugin."""
    own = f"{SCHEME}://{plugin}"
    return "; ".join(
        (
            "default-src 'none'",
            f"script-src {own}",
            f"style-src {own} 'unsafe-inline'",  # style="" attributes; CSS can't fetch anyway
            f"img-src {own} data: blob:",
            f"font-src {own}",
            "connect-src 'none'",
            "media-src 'none'",
            "frame-src 'none'",
            "worker-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        )
    )


def resolve(root, plugin, uri):
    """The file a plugin:// URI names, or None if it's outside the plugin's folder.

    Only `plugin://<this plugin>/...` resolves; any other host is refused, so a
    plugin can't read another plugin's files.
    """
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme != SCHEME or parsed.hostname != plugin.lower():
        return None
    path = urllib.parse.unquote(parsed.path).lstrip("/") or "index.html"
    if "\0" in path:
        return None
    base = os.path.realpath(root)
    full = os.path.realpath(os.path.join(base, path))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        return None
    return full


def content_type(path):
    ext = os.path.splitext(path)[1].lower()
    return MIME.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def allowed_navigation(plugin, uri):
    """Pages may only move between their own plugin:// files."""
    parsed = urllib.parse.urlsplit(uri)
    return parsed.scheme == SCHEME and parsed.hostname == plugin.lower()


CHROME = ("edit", "close", "move", "resize", "dock")  # what a frame's own page may ask of it
PLACE_LIMIT = 100  # characters in a place a frame's page picked


def page_message(raw, chrome=False):
    """A whitelisted message from a page as a dict, or None to drop it.

    Version 1: {"type": "resize", "width": w, "height": h},
    {"type": "show", "shown": bool} (hide the window while it has nothing to show),
    {"type": "log", "text": "..."} (for developers; shown in the helper's log) and
    {"type": "dispatch", "action": {...}}: a UI action, which the helper checks
    against the plugin's manifest before doing anything with it.
    A frame's own page (chrome) may also send {"type": "chrome", "do": one of CHROME},
    with "edge": one of EDGES for "resize" and "place": PLACE for "dock",
    and {"type": "placeholders", "column": [x, y, w, h], "rects": {ID: [x, y, w, h]}}:
    where its column and the placeholders of the plugins' widgets in it are.
    """
    try:
        msg = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(msg, dict):
        return None
    kind = msg.get("type")
    if kind == "resize":
        size = []
        for name in ("width", "height"):
            value = msg.get(name)
            if not isinstance(value, int) or isinstance(value, bool):
                return None
            size.append(max(SIZE_LIMITS[0], min(SIZE_LIMITS[1], value)))
        return {"type": "resize", "width": size[0], "height": size[1]}
    if kind == "show" and isinstance(msg.get("shown"), bool):
        return {"type": "show", "shown": msg["shown"]}
    if kind == "log" and isinstance(msg.get("text"), str):
        return {"type": "log", "text": msg["text"][:LOG_TEXT_LIMIT]}
    action = msg.get("action")
    if kind == "dispatch" and isinstance(action, dict) and len(json.dumps(action)) <= ACTION_LIMIT:
        return {"type": "dispatch", "action": action}
    if kind == "chrome" and chrome:
        return _chrome(msg)
    if kind == "placeholders" and chrome:
        return _placeholders(msg)
    return None


def _chrome(msg):
    what = msg.get("do")
    if what == "resize":
        edge = msg.get("edge")
        return {"type": "chrome", "do": what, "edge": edge} if edge in EDGES else None
    if what == "dock":
        place = msg.get("place")
        if not isinstance(place, str) or not 0 < len(place) <= PLACE_LIMIT:
            return None
        return {"type": "chrome", "do": what, "place": place}
    return {"type": "chrome", "do": what} if what in CHROME else None


def drag_start(msg, editing, edges):
    """Whether a frame page's chrome message msg starts a drag: pressing its
    title bar ("move"), or an edge that resizes it ("resize"), in edit mode."""
    if not editing:
        return False
    return msg["do"] == "move" or (msg["do"] == "resize" and msg["edge"] in edges)


def _rect(value):
    """[x, y, w, h] of whole numbers within the size limits, as a tuple, or None."""
    if not isinstance(value, list) or len(value) != 4:
        return None
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in value):
        return None
    x, y, w, h = value
    far = SIZE_LIMITS[1] * 4  # a column scrolled a long way still has sane numbers
    if not (-far <= x <= far and -far <= y <= far and 0 <= w <= far and 0 <= h <= far):
        return None
    return (x, y, w, h)


def _placeholders(msg):
    column, rects = _rect(msg.get("column")), msg.get("rects")
    if column is None or not isinstance(rects, dict) or len(rects) > PLACEHOLDER_LIMIT:
        return None
    checked = {}
    for wid, value in rects.items():
        rect = _rect(value)
        if not isinstance(wid, str) or len(wid) > 200 or rect is None:
            return None
        checked[wid] = rect
    return {"type": "placeholders", "column": column, "rects": checked}


def in_column(rect, column):
    """Where a plugin's view shows in its widgetwindow (#141). rect is its
    placeholder and column the page's column, both (x, y, w, h) in the page's
    (and so the window's) pixels. Returns (part, offset): part, the piece of
    rect inside column, which shows; offset, where the view's top left is
    from part's, so a view scrolled partly out keeps its place. None when none
    of it is inside."""
    left, top = max(rect[0], column[0]), max(rect[1], column[1])
    right = min(rect[0] + rect[2], column[0] + column[2])
    bottom = min(rect[1] + rect[3], column[1] + column[3])
    if right <= left or bottom <= top:
        return None
    return (left, top, right - left, bottom - top), (rect[0] - left, rect[1] - top)


WHEEL_LINES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def wheel_lines(direction, deltas=(0, 0)):
    """How far a wheel turn goes, (dx, dy) in lines: one for a click of a
    wheel (direction "up", "down", "left" or "right"); a touchpad's "smooth"
    turn gives its own deltas, in lines too."""
    if direction == "smooth":
        return tuple(deltas)
    return WHEEL_LINES.get(direction, (0, 0))


def extra_name(plugin, uri):
    """The helper-provided file a plugin://<plugin>/_oolite/... URI names, or None."""
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme != SCHEME or parsed.hostname != plugin.lower():
        return None
    path = urllib.parse.unquote(parsed.path).lstrip("/")
    return path[len(EXTRAS) :] if path.startswith(EXTRAS) else None


# Injected into every page before its own scripts. CSP doesn't apply to it.
# window.oolite is read-only, and __oolite_receive can't be replaced, so a page
# can only confuse itself by calling it.
BRIDGE = """
(() => {
  const handlers = new Map(), last = new Map();
  const post = (m) => window.webkit.messageHandlers.oolite.postMessage(JSON.stringify(m));
  const oolite = Object.freeze({
    api: API_VERSION,
    on(topic, fn) {
      if (!handlers.has(topic)) handlers.set(topic, new Set());
      handlers.get(topic).add(fn);
      if (last.has(topic)) fn(last.get(topic));
      return () => handlers.get(topic).delete(fn);
    },
    resize(width, height) { post({type: "resize", width, height}); },
    show(shown) { post({type: "show", shown: Boolean(shown)}); },
    log(text) { post({type: "log", text: String(text)}); },
    dispatch(action) { post({type: "dispatch", action}); },
  });
  const receive = (topic, value) => {
    last.set(topic, value);
    for (const fn of handlers.get(topic) || []) {
      try { fn(value); } catch (e) { oolite.log(`${topic}: ${e}`); }
    }
  };
  for (const [name, value] of [["oolite", oolite], ["__oolite_receive", receive]]) {
    Object.defineProperty(window, name, {value, writable: false, configurable: false});
  }
})();
""".replace("API_VERSION", str(API))


# Injected only into a frame's own page, after BRIDGE.
CHROME_BRIDGE = """
(() => {
  const post = (what, more) => window.webkit.messageHandlers.oolite.postMessage(
    JSON.stringify({type: "chrome", do: what, ...more}));
  const frame = Object.freeze({
    edit() { post("edit"); },
    close() { post("close"); },
    move() { post("move"); },
    resize(edge) { post("resize", {edge}); },
    dock(place) { post("dock", {place}); },
    placeholders(column, rects) {
      window.webkit.messageHandlers.oolite.postMessage(
        JSON.stringify({type: "placeholders", column, rects}));
    },
  });
  Object.defineProperty(window, "ooliteFrame", {value: frame, writable: false});
})();
"""


def receive_script(topic, value):
    return f"__oolite_receive({json.dumps(topic)}, {json.dumps(value)})"


# -- GTK -----------------------------------------------------------------


def main():
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    gi.require_version("Soup", "3.0")
    from gi.repository import Gdk, Gio, GLib, Gtk, Soup, WebKit2

    def emit(event, **fields):
        sys.stdout.write(json.dumps({"ev": event, **fields}) + "\n")
        sys.stdout.flush()

    def popup():
        window = Gtk.Window(type=Gtk.WindowType.POPUP)
        window.set_accept_focus(False)
        window.set_focus_on_map(False)
        return window

    def place_window(window, rect):
        if rect is None:
            window.hide()
            return
        x, y, w, h = rect
        window.move(x, y)
        window.resize(w, h)
        window.show()
        gdk_window = window.get_window()
        if gdk_window is not None:
            gdk_window.raise_()

    class FrameWindow:
        """A widgetwindow: its own page (the title bar and a column of widgets)
        filling it, with each plugin's view laid over its placeholder there.

        The page's ✎ asks the helper to toggle its edit mode. In edit mode the
        page draws the edges that resize it and its ⚓ list (#141), and says
        when one of its edges or its title bar is pressed: the drag follows the
        pointer here (the window manager doesn't manage popups), telling the
        helper the rect as it goes and when released, with a native ghost
        outline where a moved window would land.
        """

        def __init__(self, fid):
            self.id = fid
            self.window = popup()
            self.css = Gtk.CssProvider()
            self.css.load_from_data(f"#edge {{ background: {EDIT_COLOUR}; }}".encode())
            self.rect = None  # where the helper last placed it
            self.drag = None  # (edge, pointer x, y, rect) while an edge is dragged
            self.sent = 0.0  # when the last drag rect went to the helper
            self.pressed = None  # (x, y) where button 1 went down on the page, while it's down
            self.editing = False
            self.edges = ()  # those the helper says resize it
            # Its own page is the overlay's child; each plugin's view is in a
            # Gtk.Layout of its own over it, sized to the part of the view
            # inside the column, which so clips it (in_column).
            self.root = root = Gtk.Overlay()
            root.connect("get-child-position", self.on_child_position)
            self.clips = {}  # plugin window id -> (its Gtk.Layout, its view)
            self.shown = set()  # those its helper has placed (not hidden)
            self.column = None  # (x, y, w, h): the page's column, as its page last said
            self.rects = {}  # plugin window id -> its placeholder's (x, y, w, h)
            self.parts = {}  # Gtk.Layout -> (x, y, w, h): where in the window it shows
            self.page = None  # its own page's view
            self.window.add(root)
            root.show_all()
            self.ghost = [self.ghost_side() for _ in range(4)]  # top, bottom, left, right

        def ghost_side(self):
            """One side of the outline showing where a dragged window would land."""
            side = popup()
            box = Gtk.EventBox(visible_window=True)
            box.set_name("edge")
            self.style(box)
            side.add(box)
            box.show()
            return side

        def show_ghost(self, rect):
            if rect is None:
                for side in self.ghost:
                    side.hide()
                return
            x, y, w, h = rect
            t = EDGE_PX
            for side, (sx, sy, sw, sh) in zip(
                self.ghost,
                ((x, y, w, t), (x, y + h - t, w, t), (x, y, t, h), (x + w - t, y, t, h)),
                strict=True,
            ):
                place_window(side, (sx, sy, max(1, sw), max(1, sh)))

        def style(self, widget):
            widget.get_style_context().add_provider(
                self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def bar(self, editing=False, edges=(), ghost=None):
            self.editing = editing
            self.edges = tuple(edges)
            if not editing:
                self.drag = None
            self.show_ghost(ghost if editing else None)

        def chrome(self, msg):
            """What the frame's own page asked (page_message's "chrome")."""
            what = msg["do"]
            if what in ("edit", "close"):  # the helper checks edit mode for ×
                emit("frame", id=self.id, msg={"type": what})
            elif what == "dock" and self.editing:  # the helper checks the place
                emit("frame", id=self.id, msg={"type": "dock", "place": msg["place"]})
            elif drag_start(msg, self.editing, self.edges) and self.pressed and self.rect:
                # The page tells us after its mousedown: start from where it was.
                self.drag = (msg.get("edge", "move"), *self.pressed, tuple(self.rect))

        def dragged(self, event):
            """The rect the drag so far gives: the dragged edge follows the pointer."""
            side, px, py, (x, y, w, h) = self.drag
            dx, dy = round(event.x_root - px), round(event.y_root - py)
            if side == "move":
                x, y = x + dx, y + dy
            elif side == "left":
                dx = min(dx, w - MIN_PX)
                x, w = x + dx, w - dx
            elif side == "right":
                w = max(MIN_PX, w + dx)
            elif side == "top":
                dy = min(dy, h - MIN_PX)
                y, h = y + dy, h - dy
            else:
                h = max(MIN_PX, h + dy)
            return [x, y, w, h]

        def on_motion(self, box, event):
            if self.drag is None:
                return False
            rect = self.dragged(event)
            self.window.move(rect[0], rect[1])
            self.window.resize(rect[2], rect[3])
            now = GLib.get_monotonic_time() / 1e6
            if now - self.sent >= DRAG_REPORT_SECONDS:
                self.sent = now
                emit("frame", id=self.id, msg=self.report(rect, event, False))
            return True

        def on_release(self, box, event):
            if self.drag is None:
                return False
            msg = self.report(self.dragged(event), event, True)
            self.drag = None
            emit("frame", id=self.id, msg=msg)
            return True

        def report(self, rect, event, done):
            """The drag so far, for the helper: the rect and, moving, the pointer."""
            msg = {"type": self.kind(), "rect": rect, "done": done}
            if msg["type"] == "move":
                msg["pointer"] = [round(event.x_root), round(event.y_root)]
            return msg

        def kind(self):
            return "move" if self.drag[0] == "move" else "resize"

        def add(self, view, wid, chrome=False):
            """Its own page (chrome) fills it; a plugin's view goes over its
            placeholder once the page says where that is."""
            if not chrome:
                clip = Gtk.Layout()
                clip.put(view, 0, 0)
                clip.connect("scroll-event", self.on_unused_wheel)
                self.root.add_overlay(clip)
                self.clips[wid] = (clip, view)
                self.lay_out()
                return
            self.page = view
            self.root.add(view)
            # The page's mousedown reaches us (as "move") after GTK's press:
            # remember where it was, and follow a move drag from here.
            view.connect("button-press-event", self.on_page_press)
            view.connect("motion-notify-event", self.on_motion)
            view.connect("button-release-event", self.on_page_release)

        def on_unused_wheel(self, clip, event):
            """A wheel turn over a plugin's view that its page didn't use (it
            can't scroll that way, and WebKit passes those to the view's parent):
            its page scrolls the column instead."""
            ok, direction = event.get_scroll_direction()
            _, *deltas = event.get_scroll_deltas()
            dx, dy = wheel_lines(direction.value_nick if ok else "smooth", deltas)
            if self.page is not None and (dx or dy):
                script = f"globalThis.ooliteFrameWheel?.({dx}, {dy})"
                self.page.evaluate_javascript(script, -1, None, None, None, None, None)
            return True

        def on_page_press(self, view, event):
            if event.button == 1:
                self.pressed = (event.x_root, event.y_root)
            return False  # the page gets it too

        def on_page_release(self, view, event):
            if event.button == 1:
                self.pressed = None
            self.on_release(view, event)
            return False  # the page sees the button go up, so it isn't left pressed

        def place(self, rect):
            self.rect = rect
            if self.drag is None:  # mid-drag the pointer, not the helper, places it
                place_window(self.window, rect)

        def show_plugin(self, wid, shown):
            (self.shown.add if shown else self.shown.discard)(wid)
            self.lay_out()

        def remove(self, wid):
            clip, _ = self.clips.pop(wid)
            self.parts.pop(clip, None)
            self.shown.discard(wid)
            clip.destroy()

        def placeholders(self, column, rects):
            self.column, self.rects = column, rects
            self.lay_out()

        def lay_out(self):
            """Each shown plugin's view over its placeholder, clipped to the column."""
            for wid, (clip, view) in self.clips.items():
                rect = self.rects.get(wid)
                fit = None
                if wid in self.shown and rect is not None and self.column is not None:
                    fit = in_column(rect, self.column)
                if fit is None:
                    self.parts.pop(clip, None)
                    clip.hide()
                    continue
                part, (dx, dy) = fit
                self.parts[clip] = part
                view.set_size_request(rect[2], rect[3])
                clip.set_size(rect[2], rect[3])
                clip.move(view, dx, dy)
                view.show()
                clip.show()
                clip.queue_resize()

        def on_child_position(self, overlay, child, allocation):
            part = self.parts.get(child)
            if part is None:
                return False  # the edges: GTK's own placing
            allocation.x, allocation.y, allocation.width, allocation.height = part
            return True

        def refit(self):
            """Back to its placed size once its views have shrunk to fit it."""
            if self.rect is not None and self.drag is None:
                self.window.resize(self.rect[2], self.rect[3])

        def raise_(self):
            gdk_window = self.window.get_window()
            if self.window.get_visible() and gdk_window is not None:
                gdk_window.raise_()

        def close(self):
            for side in self.ghost:
                side.destroy()
            self.window.destroy()

    class PluginWindow:
        def __init__(
            self, wid, plugin, root, entry, background, extras, frame=None, index=0, chrome=False
        ):
            self.id = wid
            self.chrome = chrome and frame is not None  # the frame's own page (#141)
            self.plugin = plugin
            self.root = root
            self.extras = extras  # name -> text, served under _oolite/
            self.loaded = False
            self.topics = {}  # latest value of each topic, replayed after a (re)load
            self.recent = []  # times of recent page messages, for the rate limit
            self.recent_places = []  # the same for a frame page's placeholder messages

            # Ephemeral (nothing on disk), sandboxed, and one per window so the
            # scheme handler can only ever serve this plugin's folder.
            context = WebKit2.WebContext.new_ephemeral()
            context.set_sandbox_enabled(True)
            context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
            context.register_uri_scheme(SCHEME, self.serve)
            context.get_security_manager().register_uri_scheme_as_secure(SCHEME)
            context.connect("download-started", lambda c, d: d.cancel())

            content = WebKit2.UserContentManager()
            content.add_script(
                WebKit2.UserScript(
                    BRIDGE,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserScriptInjectionTime.START,
                    None,
                    None,
                )
            )
            if self.chrome:
                content.add_script(
                    WebKit2.UserScript(
                        CHROME_BRIDGE,
                        WebKit2.UserContentInjectedFrames.TOP_FRAME,
                        WebKit2.UserScriptInjectionTime.START,
                        None,
                        None,
                    )
                )
            content.register_script_message_handler("oolite")
            content.connect("script-message-received::oolite", self.on_page_message)

            settings = WebKit2.Settings(
                enable_developer_extras=False,
                javascript_can_open_windows_automatically=False,
                allow_file_access_from_file_urls=False,
                allow_universal_access_from_file_urls=False,
                enable_webaudio=False,
                enable_media=False,
                enable_webgl=False,
                enable_page_cache=False,
                # The untrusted X cookie has no GLX, so GPU rendering can't work.
                hardware_acceleration_policy=WebKit2.HardwareAccelerationPolicy.NEVER,
            )
            self.view = WebKit2.WebView(
                web_context=context, user_content_manager=content, settings=settings
            )
            colour = Gdk.RGBA()
            if colour.parse(background):
                self.view.set_background_color(colour)
            self.view.connect("decide-policy", self.on_policy)
            self.view.connect("create", lambda *a: None)  # no pop-ups
            self.view.connect("context-menu", lambda *a: True)  # no menu
            self.view.connect("load-changed", self.on_load)
            self.view.connect("load-failed", self.on_load_failed)
            self.view.connect("web-process-terminated", self.on_crash)

            # In a frame (#124) the view is one of its column; else a window of its own.
            self.frame = frame
            self.framed = frame is not None
            if self.framed:
                frame.add(self.view, wid, self.chrome)
                if self.chrome:
                    self.view.hide()  # until placed
            else:
                self.window = popup()
                self.window.add(self.view)
                self.view.show()
            self.view.load_uri(f"{SCHEME}://{plugin}/{entry}")

        def serve(self, request):
            uri = request.get_uri()
            extra = extra_name(self.plugin, uri)
            if extra is not None:
                path, data = extra, self.extras.get(extra)
                data = None if data is None else data.encode()
            else:
                path = resolve(self.root, self.plugin, uri)
                data = None
                if path is not None:
                    with open(path, "rb") as f:
                        data = f.read()
            if data is None:
                request.finish_error(
                    GLib.Error.new_literal(
                        Gio.io_error_quark(), "not found", Gio.IOErrorEnum.NOT_FOUND
                    )
                )
                return
            data = GLib.Bytes.new(data)
            response = WebKit2.URISchemeResponse.new(
                Gio.MemoryInputStream.new_from_bytes(data), data.get_size()
            )
            response.set_content_type(content_type(path))
            headers = Soup.MessageHeaders.new(Soup.MessageHeadersType.RESPONSE)
            # With headers set, WebKit reads the type from them, not from
            # set_content_type; without it, nosniff would refuse every script.
            headers.append("Content-Type", content_type(path))
            headers.append("Content-Security-Policy", csp(self.plugin))
            headers.append("X-Content-Type-Options", "nosniff")
            response.set_http_headers(headers)
            request.finish_with_response(response)

        def on_policy(self, view, decision, kind):
            if kind == WebKit2.PolicyDecisionType.RESPONSE:
                return False
            uri = decision.get_navigation_action().get_request().get_uri()
            if kind == WebKit2.PolicyDecisionType.NAVIGATION_ACTION and allowed_navigation(
                self.plugin, uri
            ):
                decision.use()
            else:
                decision.ignore()
            return True

        def on_load(self, view, event):
            if event == WebKit2.LoadEvent.STARTED:
                self.loaded = False
            elif event == WebKit2.LoadEvent.FINISHED and not self.loaded:
                self.loaded = True
                for topic, value in self.topics.items():
                    self.run(receive_script(topic, value))
                emit("loaded", id=self.id)

        def on_load_failed(self, view, event, uri, error):
            emit("error", id=self.id, message=f"couldn't load {uri}: {error.message}")
            return False

        def on_crash(self, view, reason):
            emit("crashed", id=self.id, reason=reason.value_nick)

        def on_page_message(self, manager, result):
            raw = result.get_js_value().to_string()
            # Rate-limited before parsing, so a page can't make us parse junk without
            # end. Only the frame's own page has the placeholders budget.
            placing = self.chrome and '"placeholders"' in raw
            now = GLib.get_monotonic_time() / 1e6
            recent = self.recent_places if placing else self.recent
            recent[:] = [t for t in recent if now - t < 1] + [now]
            limit = PLACEHOLDER_MESSAGES_PER_SECOND if placing else PAGE_MESSAGES_PER_SECOND
            if len(recent) > limit:
                return
            msg = page_message(raw, self.chrome)
            if msg is None:
                return
            if msg["type"] == "placeholders":
                self.frame.placeholders(msg["column"], msg["rects"])
                emit("placeholders", id=self.frame.id, column=msg["column"], rects=msg["rects"])
            elif msg["type"] == "chrome":
                self.frame.chrome(msg)
            else:
                emit("page", id=self.id, msg=msg)

        def run(self, script):
            self.view.evaluate_javascript(script, -1, None, None, None, None, None)

        def topic(self, name, value):
            self.topics[name] = value
            if self.loaded:
                self.run(receive_script(name, value))

        def place(self, rect):
            if not self.framed:
                place_window(self.window, rect)
            elif not self.chrome:
                self.frame.show_plugin(self.id, rect is not None)  # over its placeholder
            elif rect is None:
                self.view.hide()
            else:
                self.view.set_size_request(rect[2], rect[3])  # it fills its frame
                self.view.show()
                self.frame.refit()

        def close(self):
            if self.framed and not self.chrome:
                self.frame.remove(self.id)
            else:
                (self.view if self.framed else self.window).destroy()

    windows = {}
    frames = {}

    def handle(cmd):
        op = cmd.get("op")
        wid = cmd.get("id")
        if op == "frame":
            if wid not in frames:
                frames[wid] = FrameWindow(wid)
            frames[wid].bar(cmd.get("editing", False), cmd.get("edges", ()), cmd.get("ghost"))
        elif op == "open":
            if wid in windows:
                windows.pop(wid).close()
            frame = cmd.get("frame")
            if frame is not None and frame not in frames:
                emit("error", id=wid, message=f"open: no frame {frame!r}")
                return
            windows[wid] = PluginWindow(
                wid,
                cmd["plugin"],
                cmd["root"],
                cmd.get("entry", "index.html"),
                cmd["background"],
                cmd.get("extras") or {},
                frames.get(frame),
                cmd.get("index", 0),
                cmd.get("chrome", False),
            )
        elif op == "quit":
            Gtk.main_quit()
        elif wid in frames and op in ("place", "close"):
            if op == "place":
                frames[wid].place(cmd.get("rect"))
            else:
                frames.pop(wid).close()
        elif wid not in windows:
            emit("error", id=wid, message=f"{op}: no window {wid!r}")
        elif op == "place":
            windows[wid].place(cmd.get("rect"))
            if not windows[wid].framed:
                for frame in frames.values():  # widgetwindows stay above lone widgets
                    frame.raise_()
        elif op == "topic":
            windows[wid].topic(cmd["name"], cmd.get("value"))
        elif op == "close":
            windows.pop(wid).close()
            emit("closed", id=wid)
        else:
            emit("error", id=wid, message=f"unknown op {op!r}")

    buffer = b""

    def on_input(channel, condition):
        nonlocal buffer
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:  # the helper has gone: so do we
            Gtk.main_quit()
            return False
        buffer += chunk
        *lines, buffer = buffer.split(b"\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                handle(json.loads(line))
            except Exception as exc:  # one bad command mustn't stop the host
                emit("error", id=None, message=f"{type(exc).__name__}: {exc}")
        return True

    GLib.io_add_watch(
        GLib.IOChannel.unix_new(sys.stdin.fileno()), GLib.IO_IN | GLib.IO_HUP, on_input
    )
    emit("ready", protocol=PROTOCOL, api=API, webkit=_webkit_version(WebKit2))
    Gtk.main()


def _webkit_version(webkit):
    return ".".join(
        str(n)
        for n in (
            webkit.get_major_version(),
            webkit.get_minor_version(),
            webkit.get_micro_version(),
        )
    )


if __name__ == "__main__":
    main()
