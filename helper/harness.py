"""A harness for developing web components and widgets with fake game data (#82).

    .venv/bin/python -m helper.harness                   # browse at http://127.0.0.1:8566/
    .venv/bin/python -m helper.harness --shots gallery   # an image of each, at each snapshot

Each scenario (scenarios/*.yaml, the fake game's timelines) is replayed through
a fresh model, and a **snapshot** is kept at the end of each stretch with the
same context (docked, near station, red alert, ...). The harness shows every
built-in component on its own, and every widget in a config file, at the
snapshot you pick, at its real size. Pages are served from helper/web as they
are, so edit a component and refresh. Clicks work: they're checked and
applied to that snapshot's model like the helper does.

--shots takes a screenshot of each with headless Chrome or Chromium, and
writes an index.html to browse them.
"""

import argparse
import contextlib
import html
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, plugin_api, web
from .keys import load_keymap
from .markets import MarketStore
from .model import Model
from .plugins import Manifest, builtin_manifest, discover
from .webhost.host import content_type, csp
from .widgets import COMPONENTS, WidgetSpec, load_widgets

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"
# How each component is shown on its own: (width, height, layout). Small ones
# are strips docked to the game; the rest fill a laptop-sized widget.
COMPONENT_VIEWS = {
    "drive": (640, 40, "compact"),
    "clearance": (640, 40, "compact"),
    "trade_here": (560, 480, "compact"),
    "heading": (1600, 140, "large"),
    "tip": (1600, 100, "large"),
    "status": (1600, 40, "large"),
}
DEFAULT_VIEW = (1600, 900, "large")
GAME_SIZE = (1280, 720)  # for widgets docked to the game with no size of their own


# -- snapshots -----------------------------------------------------------------


@dataclass
class Snapshot:
    id: str  # "<scenario>.<messages applied>", e.g. "docking.4"
    scenario: str
    step: int
    context: str
    model: Model


def _messages(path):
    from tests.fakegame import load_scenario  # the fake game lives with the tests

    return [step["msg"] for step in load_scenario(path) if "msg" in step]


def _replay(messages, keymap, store):
    model = Model(markets=MarketStore(store), keymap=keymap)
    for msg in messages:
        try:
            model.dispatch(msg)
        except Exception as exc:  # a scenario testing bad input; the helper skips it too
            print(f"harness: skipped {msg.get('type')}: {exc}", file=sys.stderr)
    return model


def snapshots(paths, keymap, folder):
    """A Snapshot at the end of each stretch of one context, for each scenario."""
    found = []
    for path in paths:
        path = Path(path)
        messages = _messages(path)
        model = _replay([], keymap, Path(folder) / f"{path.stem}.json")
        ends, last = [], None
        for i, msg in enumerate(messages, start=1):
            with contextlib.suppress(Exception):  # reported when the snapshot is replayed
                model.dispatch(msg)
            context = model.topic("context")
            if last is not None and context != last:
                ends.append(i - 1)
            last = context
        ends.append(len(messages))
        for end in dict.fromkeys(e for e in ends if e > 0):
            sid = f"{path.stem}.{end}"
            snap = _replay(messages[:end], keymap, Path(folder) / f"{sid}.json")
            found.append(Snapshot(sid, path.stem, end, snap.topic("context"), snap))
    return found


# -- what to show --------------------------------------------------------------


@dataclass(frozen=True)
class Target:
    id: str  # "component.drive" or "widget.<id>"
    title: str
    spec: WidgetSpec
    manifest: Manifest

    @property
    def builtin(self):
        return self.manifest.name == web.HOST

    @property
    def size(self):
        width = self.spec.width or GAME_SIZE[0]
        height = self.spec.height or (
            40 if self.spec.dock in ("game:top", "game:bottom") else GAME_SIZE[1]
        )
        return width, height

    @property
    def entry(self):
        return self.manifest.entry


def targets(config_path=None, plugins=None):
    """Every built-in component on its own, then every widget in config_path."""
    found = []
    for name in COMPONENTS:
        width, height, layout = COMPONENT_VIEWS.get(name, DEFAULT_VIEW)
        spec = WidgetSpec(components=(name,), width=width, height=height, layout=layout)
        found.append(Target(f"component.{name}", name, spec, builtin_manifest(COMPONENTS, (name,))))
    manifests = plugins if plugins is not None else discover()[0]
    if config_path and Path(config_path).exists():
        for n, spec in enumerate(load_widgets(config_path, plugins=set(manifests)), start=1):
            wid = spec.id or f"widget{n}:{spec.components[0]}"
            if spec.components[0] in manifests:
                manifest = manifests[spec.components[0]]
            else:
                manifest = builtin_manifest(COMPONENTS, spec.components)
            title = f"{wid}: {', '.join(spec.components)}"
            found.append(Target(f"widget.{wid}", title, spec, manifest))
    return found


def topic_values(target, model):
    """{topic: value} for what the target's page reads, as the helper sends them."""
    values = {name: plugin_api.topic_value(model, name) for name in target.manifest.topics}
    if target.manifest.keys:
        keys = {action: plugin_api.key_info(model, action) for action in target.manifest.keys}
        values[plugin_api.KEYS_TOPIC] = keys
    return values


# -- the server ----------------------------------------------------------------

# The page's `oolite` object: topics are fetched from the harness (again every
# second, so a click's result shows), and clicks are posted back to it.
DEV_JS = """(() => {
  if (window.oolite) return;
  const base = new URL(".", document.currentScript.src);
  const handlers = new Map(), last = new Map();
  const post = (name, body) => fetch(new URL(name, base), {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  async function poll() {
    const values = await (await fetch(new URL("topics", base))).json();
    for (const [topic, value] of Object.entries(values)) {
      if (last.has(topic) && JSON.stringify(last.get(topic)) === JSON.stringify(value)) continue;
      last.set(topic, value);
      for (const fn of handlers.get(topic) || []) fn(value);
    }
  }
  const oolite = Object.freeze({
    api: API,
    on(topic, fn) {
      if (!handlers.has(topic)) handlers.set(topic, new Set());
      handlers.get(topic).add(fn);
      if (last.has(topic)) fn(last.get(topic));
      return () => handlers.get(topic).delete(fn);
    },
    dispatch(action) { post("dispatch", action).then(poll); },
    resize(width, height) {},
    show(shown) {},
    log(text) { post("log", {text: String(text)}); },
  });
  Object.defineProperty(window, "oolite", {value: oolite});
  poll();
  if (!location.search.includes("shot")) setInterval(poll, 1000);
})();
""".replace("API", str(plugin_api.API))


class HarnessServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, snaps, found):
        self.snapshots = {snap.id: snap for snap in snaps}
        self.order = [snap.id for snap in snaps]
        self.targets = {target.id: target for target in found}
        self.lock = threading.Lock()  # the models aren't thread-safe
        super().__init__(address, HarnessHandler)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}/"

    def page_url(self, sid, tid):
        target = self.targets[tid]
        return f"{self.url}s/{sid}/{tid}/{target.entry}"


class HarnessHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            query = urllib.parse.parse_qs(parsed.query)
            sid = query.get("snap", [self.server.order[0]])[0]
            return self.send(200, "text/html", index_html(self.server, sid).encode())
        found = self.route(parsed.path)
        if found is None:
            return self.send(404, "text/plain", b"not found")
        snap, target, path = found
        if path.startswith("_oolite/"):
            return self.extra(snap, target, path.removeprefix("_oolite/"))
        root = Path(target.manifest.root).resolve()
        full = (root / path).resolve()
        if not full.is_relative_to(root) or not full.is_file() or full.name.endswith(".test.js"):
            return self.send(404, "text/plain", b"not found")
        self.send(200, content_type(str(full)), full.read_bytes(), target)

    def do_POST(self):
        found = self.route(urllib.parse.urlsplit(self.path).path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"null")
        except ValueError:
            body = None
        if found is None or not isinstance(body, dict):
            return self.send(400, "text/plain", b"bad request")
        snap, target, path = found
        if path == "_oolite/dispatch":
            checked = plugin_api.check_action(body, target.manifest.actions)
            if checked is None:
                print(f"harness: {target.id} refused {body!r}", file=sys.stderr)
                return self.send(403, "text/plain", b"refused")
            with self.server.lock:
                snap.model.dispatch(checked)
        elif path == "_oolite/log":
            print(f"harness: {target.id}: {body.get('text')}", file=sys.stderr)
        self.send(204, "text/plain", b"")

    def route(self, path):
        """(snapshot, target, the path within the page) for /s/<snap>/<target>/<path>."""
        parts = path.split("/", 4)
        if len(parts) < 5 or parts[1] != "s":
            return None
        snap = self.server.snapshots.get(parts[2])
        target = self.server.targets.get(parts[3])
        if snap is None or target is None:
            return None
        return snap, target, urllib.parse.unquote(parts[4])

    def extra(self, snap, target, name):
        spec = target.spec
        if name == "widget.html" and target.builtin:
            return self.send(200, "text/html", target.manifest.page.encode(), target)
        if name == "theme.css":
            css = plugin_api.theme_css(spec.layout, spec.font_scale)
            return self.send(200, "text/css", css.encode(), target)
        if name == "dev.js":
            return self.send(200, "text/javascript", DEV_JS.encode(), target)
        if name == "widget.js" and target.builtin:
            widget = {
                "components": list(spec.components),
                "topics": list(target.manifest.topics),
                "width": target.size[0],
            }
            script = f"globalThis.OOLITE_WIDGET = {json.dumps(widget)};\n"
            return self.send(200, "text/javascript", script.encode(), target)
        if name == "topics":
            with self.server.lock:
                values = topic_values(target, snap.model)
            return self.send(200, "application/json", json.dumps(values).encode())
        self.send(404, "text/plain", b"not found")

    def send(self, status, mime, data, target=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")  # edit a file, refresh, see it
        if target is not None:
            # The plugin policy, for this server's same-origin files and fetches.
            name = target.manifest.name
            policy = csp(name).replace(f"plugin://{name}", "'self'")
            policy = policy.replace("connect-src 'none'", "connect-src 'self'")
            self.send_header("Content-Security-Policy", policy)
            self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


PAGE_STYLE = """
body { margin: 0; background: #0b0e12; color: #c9d1d9; font: 14px sans-serif; }
header { position: sticky; top: 0; z-index: 1; padding: 10px 16px; background: #161b22; }
select { font: inherit; }
section { padding: 12px 16px; }
h2 { margin: 0 0 6px; font-size: 14px; color: #8b949e; }
.frame { overflow: hidden; border: 1px solid #30363d; }
iframe, img { display: block; border: 0; transform-origin: 0 0; }
"""


def index_html(server, sid):
    """The browsing page: a snapshot picker, then each target at that snapshot."""
    options = "".join(
        f'<option value="{s}"{" selected" if s == sid else ""}>'
        f"{html.escape(s)}: {html.escape(server.snapshots[s].context)}</option>"
        for s in server.order
    )
    sections = []
    for tid, target in server.targets.items():
        width, height = target.size
        scale = min(1.0, 960 / width)
        src = html.escape(server.page_url(sid, tid))
        heading = f"{html.escape(target.title)} ({width}×{height}, {target.spec.layout})"
        sections.append(
            f"<section><h2>{heading}</h2>"
            f'<div class="frame" style="width:{width * scale:.0f}px;height:{height * scale:.0f}px">'
            f'<iframe src="{src}" width="{width}" height="{height}" '
            f'style="transform:scale({scale:.3f})"></iframe></div></section>'
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Component harness</title>"
        f"<style>{PAGE_STYLE}</style></head><body><header><form>Snapshot "
        f"<select name='snap' onchange='this.form.submit()'>{options}</select> "
        "<span>(edit a component's files and refresh)</span></form></header>"
        + "".join(sections)
        + "</body></html>"
    )


# -- screenshots ---------------------------------------------------------------


def find_chrome():
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def shoot(server, out, chrome, only=None):
    """Screenshot every target at every snapshot into out/<target>/<snapshot>.png."""
    out = Path(out)
    shots = []
    with tempfile.TemporaryDirectory(prefix="oolite-harness-chrome-") as profile:
        for tid, target in server.targets.items():
            if only and not any(word in tid for word in only):
                continue
            width, height = target.size
            for sid in server.order:
                path = out / tid / f"{sid}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                command = [
                    chrome,
                    "--headless",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    f"--user-data-dir={profile}",
                    f"--window-size={width},{height}",
                    "--virtual-time-budget=3000",
                    f"--screenshot={path}",
                    server.page_url(sid, tid) + "?shot",
                ]
                subprocess.run(command, capture_output=True, timeout=60, check=False)
                if path.exists():
                    shots.append((tid, sid, path.relative_to(out)))
                else:
                    print(f"harness: no image for {tid} at {sid}", file=sys.stderr)
    rows = []
    for tid, target in server.targets.items():
        mine = [(sid, rel) for t, sid, rel in shots if t == tid]
        if not mine:
            continue
        width = min(target.size[0], 640)
        cells = "".join(
            f"<figure><figcaption>{html.escape(sid)}: "
            f"{html.escape(server.snapshots[sid].context)}</figcaption>"
            f'<img src="{html.escape(str(rel))}" width="{width}"></figure>'
            for sid, rel in mine
        )
        rows.append(f"<section><h2>{html.escape(target.title)}</h2>{cells}</section>")
    (out / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Component gallery</title>"
        f"<style>{PAGE_STYLE} figure {{ display: inline-block; margin: 0 12px 12px 0; }}"
        "</style></head><body>" + "".join(rows) + "</body></html>"
    )
    return shots


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--scenario", type=Path, action="append", help="fake-game scenario (default: all)"
    )
    parser.add_argument(
        "--config", type=Path, default=Path(config.PATH), help="widgets to show (config.toml)"
    )
    parser.add_argument("--port", type=int, default=8566)
    parser.add_argument("--shots", type=Path, metavar="DIR", help="write images here and exit")
    parser.add_argument(
        "--only", action="append", metavar="TEXT", help="--shots: only targets whose id has TEXT"
    )
    args = parser.parse_args()
    try:
        import tests.fakegame  # noqa: F401
    except ImportError:
        parser.error("run this from the oolite-helper repository (it needs tests/fakegame.py)")
    paths = args.scenario or sorted(SCENARIOS.glob("*.yaml"))
    try:
        keymap = load_keymap()
    except Exception:
        keymap = None  # no game here: keys show as unbound
    with tempfile.TemporaryDirectory(prefix="oolite-harness-") as folder:
        try:
            snaps = snapshots(paths, keymap, folder)
            found = targets(args.config)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        port = 0 if args.shots else args.port
        server = HarnessServer(("127.0.0.1", port), snaps, found)
        if args.shots:
            chrome = find_chrome()
            if chrome is None:
                parser.error("--shots needs google-chrome or chromium on the PATH")
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                shots = shoot(server, args.shots, chrome, args.only)
            finally:
                server.shutdown()
            print(f"{len(shots)} images; open {args.shots / 'index.html'}")
            return
        print(f"Component harness at {server.url} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
