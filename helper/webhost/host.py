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

A frame is a widgetwindow (#124): one popup with a title bar, whose plugin
views are packed into it top to bottom instead of getting windows of their own.

The pure functions at the top (no GTK) are tested in CI.
"""

import json
import mimetypes
import os
import sys
import urllib.parse

PROTOCOL = 2
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
PAGE_MESSAGES_PER_SECOND = 20  # more than this from one page are dropped
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


def page_message(raw):
    """A whitelisted message from a page as a dict, or None to drop it.

    Version 1: {"type": "resize", "width": w, "height": h},
    {"type": "show", "shown": bool} (hide the window while it has nothing to show),
    {"type": "log", "text": "..."} (for developers; shown in the helper's log) and
    {"type": "dispatch", "action": {...}}: a UI action, which the helper checks
    against the plugin's manifest before doing anything with it.
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
    return None


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
        """A widgetwindow: a title bar over a column of plugin views."""

        def __init__(self, fid):
            self.id = fid
            self.window = popup()
            self.css = Gtk.CssProvider()
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.bar = Gtk.Label(xalign=0.5)  # the title, centred on the whole bar
            self.bar.set_name("title")
            # × over its right end: shown, but closing comes with edit mode (#124 step 3).
            close = Gtk.Button(label="×", relief=Gtk.ReliefStyle.NONE, halign=Gtk.Align.END)
            close.set_name("close")
            close.set_can_focus(False)
            close.set_focus_on_click(False)
            for part in (self.bar, close):
                part.get_style_context().add_provider(
                    self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            title = Gtk.Overlay()
            title.add(self.bar)
            title.add_overlay(close)
            self.views = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            outer.pack_start(title, False, False, 0)
            outer.pack_start(self.views, True, True, 0)
            self.window.add(outer)
            outer.show_all()

        def title(self, text, colours, height):
            background, text_colour = colours
            font = max(8, round(height * 0.5))
            self.css.load_from_data(
                (
                    f"#title {{ background: {background}; color: {text_colour}; "
                    f"font: bold {font}px sans-serif; padding: 0 {font}px; }}"
                    f"#close {{ background: none; border: none; box-shadow: none; "
                    f"color: {text_colour}; font: bold {font}px sans-serif; "
                    f"padding: 0 {font // 2}px; min-height: 0; }}"
                ).encode()
            )
            self.bar.set_text(text)
            self.bar.set_size_request(-1, height)

        def add(self, view, index):
            """Packs view in index order among the views already here."""
            view.frame_index = index
            self.views.pack_start(view, False, False, 0)
            ordered = sorted(self.views.get_children(), key=lambda v: v.frame_index)
            for position, child in enumerate(ordered):
                self.views.reorder_child(child, position)

        def place(self, rect):
            place_window(self.window, rect)

        def raise_(self):
            gdk_window = self.window.get_window()
            if self.window.get_visible() and gdk_window is not None:
                gdk_window.raise_()

        def close(self):
            self.window.destroy()

    class PluginWindow:
        def __init__(self, wid, plugin, root, entry, background, extras, frame=None, index=0):
            self.id = wid
            self.plugin = plugin
            self.root = root
            self.extras = extras  # name -> text, served under _oolite/
            self.loaded = False
            self.topics = {}  # latest value of each topic, replayed after a (re)load
            self.recent = []  # times of recent page messages, for the rate limit

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
            self.framed = frame is not None
            if self.framed:
                frame.add(self.view, index)
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
            now = GLib.get_monotonic_time() / 1e6
            self.recent = [t for t in self.recent if now - t < 1] + [now]
            if len(self.recent) > PAGE_MESSAGES_PER_SECOND:
                return
            msg = page_message(result.get_js_value().to_string())
            if msg is not None:
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
            elif rect is None:
                self.view.hide()
            else:
                self.view.set_size_request(rect[2], rect[3])  # its frame places it
                self.view.show()

        def close(self):
            (self.view if self.framed else self.window).destroy()

    windows = {}
    frames = {}

    def handle(cmd):
        op = cmd.get("op")
        wid = cmd.get("id")
        if op == "frame":
            if wid not in frames:
                frames[wid] = FrameWindow(wid)
            frames[wid].title(cmd["title"], cmd["colours"], cmd["title_height"])
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
