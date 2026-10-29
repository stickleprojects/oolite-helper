"""A harness for developing web components and widgets with fake game data (#82).

    .venv/bin/python -m helper.harness                     # everything, at http://127.0.0.1:8566/
    .venv/bin/python -m helper.harness clearance           # one component
    .venv/bin/python -m helper.harness clearance+drive     # components together, as a widget
    .venv/bin/python -m helper.harness "keys|all_keys"     # "|" makes a tabs widget of them
    .venv/bin/python -m helper.harness top-strip           # a named widget (helper/web/widgets)
    .venv/bin/python -m helper.harness my-widget           # a widget from config.toml
    .venv/bin/python -m helper.harness clearance --shots out   # images instead

Where the data comes from:
- **Snapshots**: each scenario (scenarios/*.yaml, the fake game's timelines)
  is replayed through a fresh model, and a snapshot kept at the end of each
  stretch with one context (docked, near station, red alert, ...), plus
  "blank.0", before the game says anything.
- **Named states**: each component's <name>.states.json, e.g. clearance's
  "expiring". Picking one sets that component's topics over the snapshot.
- **Your edits**: with one target open, every topic it reads is shown as
  JSON; change one and apply it, and the page reacts within half a second.

Pages are served from helper/web as they are, so edit a component and
refresh. Clicks work: they're checked and applied to the snapshot's model
like the helper does.

--shots takes a screenshot of each target at every snapshot and in each of
its components' named states, with headless Chrome or Chromium, and writes
an index.html to browse them.
"""

import argparse
import contextlib
import html
import json
import re
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
from .plugins import Manifest, discover, page_manifest
from .webhost.host import content_type, csp
from .widgets import COMPONENTS, WIDGETS, WidgetSpec, load_widgets

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


BLANK = "blank.0"  # the snapshot before the game says anything


def snapshots(paths, keymap, folder):
    """The blank snapshot, then one at the end of each stretch of one context,
    for each scenario."""
    blank = _replay([], keymap, Path(folder) / "blank.json")
    found = [Snapshot(BLANK, "blank", 0, blank.topic("context"), blank)]
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
    id: str  # "component.drive", "widget.<name>", "config.<id>", or "widget.a+b" joined
    title: str
    spec: WidgetSpec
    manifest: Manifest
    named: tuple = ()  # a named widget's own states: ((name, {component: state}), ...)

    @property
    def generated(self):
        """Its page is the one the helper generates (not a plugin's)."""
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

    @property
    def states(self):
        """[(component, state name, {topic: value}), ...]: its components' named
        states, after a named widget's own (as component "widget"). In a widget that
        reads the tabs topic, a component's states show its tab."""
        if not self.generated:
            return []
        own = [("widget", state, self.together(chosen)) for state, chosen in self.named]
        return own + [
            (name, state, self.together({name: state}))
            for name in self.spec.components
            for state, _ in COMPONENTS[name].states
        ]

    def together(self, chosen):
        """{topic: value} for these components' states, {component: state name},
        and the named widget's own state, keyed by its name, applied last."""
        tabbed = "tabs" in self.manifest.topics
        values = {}
        for name, state in chosen.items():
            if name in COMPONENTS:
                values.update(dict(COMPONENTS[name].states)[state])
                if tabbed:
                    values.update(self.showing(name))
        own = WIDGETS[self.spec.widget].own_states if self.spec.widget in WIDGETS else ()
        values.update(dict(own).get(chosen.get(self.spec.widget), {}))
        return values

    @staticmethod
    def showing(tab):
        """The tabs topic with this tab chosen and shown."""
        tabs = [{"id": name, "text": title} for name, title in plugin_api.tabs()]
        return {"tabs": {"shown": tab, "chosen": tab, "urgent": False, "tabs": tabs}}


def component_target(name):
    width, height, layout = COMPONENT_VIEWS.get(name, DEFAULT_VIEW)
    spec = WidgetSpec(components=(name,), width=width, height=height, layout=layout)
    return Target(f"component.{name}", name, spec, page_manifest(COMPONENTS, (name,)))


def widget_target(name):
    named = WIDGETS[name]
    spec = named.spec
    title = f"{name}: {', '.join(spec.components)}"
    manifest = page_manifest(COMPONENTS, spec.components, named)
    return Target(f"widget.{name}", title, spec, manifest, named.states)


def config_targets(config_path, manifests):
    found = []
    if config_path and Path(config_path).exists():
        for n, spec in enumerate(load_widgets(config_path, plugins=set(manifests)), start=1):
            wid = spec.id or f"widget{n}:{spec.components[0]}"
            if spec.components[0] in manifests:
                manifest = manifests[spec.components[0]]
            else:
                named = WIDGETS.get(spec.widget)
                manifest = page_manifest(COMPONENTS, spec.components, named)
            title = f"{wid}: {', '.join(spec.components)}"
            found.append(Target(f"config.{wid}", title, spec, manifest))
    return found


def targets(config_path=None, plugins=None, names=()):
    """What to show. With no names: every component on its own, every
    named widget, then every widget in config_path. Otherwise each name is a
    component, a named widget, components joined with "+" (shown together, as a
    widget; "keys|all_keys" makes a tabs widget of them), or a widget id in
    config_path."""
    manifests = plugins if plugins is not None else discover()[0]
    widgets = config_targets(config_path, manifests)
    if not names:
        named = [widget_target(name) for name in WIDGETS]
        return [component_target(name) for name in COMPONENTS] + named + widgets
    found = []
    for name in names:
        if "+" in name and "|" in name:
            raise ValueError(f"{name!r}: join components with + or with |, not both")
        tabs = "|" in name
        parts = tuple(name.split("|" if tabs else "+"))
        if len(parts) == 1 and name in COMPONENTS:
            found.append(component_target(name))
        elif name in WIDGETS:
            found.append(widget_target(name))
        elif name not in COMPONENTS and all(part in COMPONENTS for part in parts):
            widget = "tabs" if tabs else None
            spec = WidgetSpec(parts, width=DEFAULT_VIEW[0], layout="large", widget=widget)
            title = (" | " if tabs else " + ").join(parts)
            manifest = page_manifest(COMPONENTS, parts, WIDGETS.get(widget))
            found.append(Target(f"widget.{name}", title, spec, manifest))
        elif any(target.id == f"config.{name}" for target in widgets):
            found.append(next(target for target in widgets if target.id == f"config.{name}"))
        else:
            ids = (t.id.removeprefix("config.") for t in widgets)
            known = ", ".join([*COMPONENTS, *WIDGETS, *ids])
            raise ValueError(
                f"{name!r} isn't a component, a named widget or a widget in the config: {known}"
            )
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
# half second, so clicks and edits show), and clicks are posted back to it.
DEV_JS = """(() => {
  if (window.oolite) return;
  const base = new URL(".", document.currentScript.src);
  const handlers = new Map(), last = new Map();
  let latest = null, ready = false, seq = 0;
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
    show(shown) {
      // Reported once the topics have arrived (the first draw, before them, is
      // empty), and numbered: the harness answers requests on several threads.
      latest = Boolean(shown);
      if (ready) post("show", {shown: latest, seq: ++seq});
    },
    log(text) { post("log", {text: String(text)}); },
  });
  Object.defineProperty(window, "oolite", {value: oolite});
  poll().then(() => {
    ready = true;
    if (latest !== null) post("show", {shown: latest, seq: ++seq});
  });
  if (!location.search.includes("shot")) setInterval(poll, 500);
})();
""".replace("API", str(plugin_api.API))


class HarnessServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, snaps, found):
        self.snapshots = {snap.id: snap for snap in snaps}
        self.order = [snap.id for snap in snaps]
        self.targets = {target.id: target for target in found}
        # (snapshot id, target id) -> {topic: value} set over the snapshot's own
        # values by a named state or an edit.
        self.overrides = {}
        # (snapshot id, target id) -> (seq, shown): what the page last said with oolite.show()
        self.shown = {}
        self.lock = threading.Lock()  # the models aren't thread-safe
        super().__init__(address, HarnessHandler)

    def values(self, sid, tid):
        """The target's topics at a snapshot, with any overrides on top."""
        target = self.targets[tid]
        with self.lock:
            values = topic_values(target, self.snapshots[sid].model)
            overrides = self.overrides.get((sid, tid), {})
        return {**values, **{k: v for k, v in overrides.items() if k in values}}

    def override(self, sid, tid, change):
        """Apply {"topic", "value"}, {"component", "state"} or {"reset": true}.
        False if it isn't one of those."""
        target = self.targets[tid]
        with self.lock:
            overrides = self.overrides.setdefault((sid, tid), {})
            if change.get("reset") is True:
                overrides.clear()
            elif "state" in change:
                named = {(c, name): values for c, name, values in target.states}
                values = named.get((change.get("component"), change["state"]))
                if values is None:
                    return False
                overrides.update(values)
            elif change.get("topic") in target.manifest.topics:
                overrides[change["topic"]] = change.get("value")
            else:
                return False
        return True

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
            if sid not in self.server.snapshots:
                sid = self.server.order[0]
            tid = query.get("target", [None])[0]
            if tid is None and len(self.server.targets) == 1:
                tid = next(iter(self.server.targets))
            if tid in self.server.targets:
                page = target_html(self.server, sid, tid)
            else:
                page = index_html(self.server, sid)
            return self.send(200, "text/html", page.encode())
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
        elif path == "_oolite/show":
            seq = body.get("seq") if isinstance(body.get("seq"), int) else 0
            with self.server.lock:
                key = (snap.id, target.id)
                if seq >= self.server.shown.get(key, (-1, True))[0]:  # the latest report wins
                    self.server.shown[key] = (seq, body.get("shown") is not False)
        elif path == "_oolite/override":
            if not self.server.override(snap.id, target.id, body):
                return self.send(400, "text/plain", b"not a topic or state of this target")
        self.send(204, "text/plain", b"")

    def route(self, path):
        """(snapshot, target, the path within the page) for /s/<snap>/<target>/<path>."""
        parts = path.split("/", 4)
        if len(parts) < 5 or parts[1] != "s":
            return None
        snap = self.server.snapshots.get(urllib.parse.unquote(parts[2]))
        target = self.server.targets.get(urllib.parse.unquote(parts[3]))  # e.g. "keys|all_keys"
        if snap is None or target is None:
            return None
        return snap, target, urllib.parse.unquote(parts[4])

    def extra(self, snap, target, name):
        spec = target.spec
        if name == "widget.html" and target.generated:
            return self.send(200, "text/html", target.manifest.page.encode(), target)
        if name == "theme.css":
            css = plugin_api.theme_css(spec.layout, spec.font_scale)
            return self.send(200, "text/css", css.encode(), target)
        if name == "dev.js":
            return self.send(200, "text/javascript", DEV_JS.encode(), target)
        if name == "widget.js" and target.generated:
            topics = target.manifest.topics
            script = web.widget_config(spec.components, spec.widget, topics, target.size[0])
            return self.send(200, "text/javascript", script.encode(), target)
        if name == "topics":
            values = self.server.values(snap.id, target.id)
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
a { color: #58a6ff; }
main { display: flex; gap: 16px; padding: 12px 16px; align-items: flex-start; }
aside { flex: 1; min-width: 320px; }
aside h3 { margin: 12px 0 6px; font-size: 13px; color: #8b949e; text-transform: uppercase; }
aside label { display: block; margin: 4px 0; }
textarea { width: 100%; box-sizing: border-box; background: #0d1117; color: #c9d1d9;
  border: 1px solid #30363d; font: 12px monospace; }
.error { color: #f85149; }
"""


def snapshot_options(server, sid):
    return "".join(
        f'<option value="{s}"{" selected" if s == sid else ""}>'
        f"{html.escape(s)}: {html.escape(server.snapshots[s].context)}</option>"
        for s in server.order
    )


def index_html(server, sid):
    """The browsing page: a snapshot picker, then each target at that snapshot."""
    options = snapshot_options(server, sid)
    sections = []
    for tid, target in server.targets.items():
        width, height = target.size
        scale = min(1.0, 960 / width)
        src = html.escape(server.page_url(sid, tid))
        link = f"?target={urllib.parse.quote(tid)}&snap={urllib.parse.quote(sid)}"
        heading = (
            f"{html.escape(target.title)} ({width}×{height}, {target.spec.layout}) "
            f'<a href="{html.escape(link)}">open with states and topics</a>'
        )
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


# One target, with its components' named states and an editor for each topic
# it reads. Changes go to the harness, and the page polls for them.
TARGET_SCRIPT = """
const base = BASE;
const send = async (body) => {
  const answer = await fetch(base + "override", {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  await load();
  return answer.ok;
};
async function load() {
  const values = await (await fetch(base + "topics")).json();
  for (const area of document.querySelectorAll("textarea[data-topic]")) {
    if (document.activeElement !== area) {
      area.value = JSON.stringify(values[area.dataset.topic] ?? null, null, 2);
    }
  }
}
for (const select of document.querySelectorAll("select[data-component]")) {
  select.addEventListener("change", () => {
    if (select.value) send({component: select.dataset.component, state: select.value});
  });
}
for (const button of document.querySelectorAll("button[data-topic]")) {
  button.addEventListener("click", async () => {
    const area = document.querySelector(`textarea[data-topic="${button.dataset.topic}"]`);
    const error = button.nextElementSibling;
    try {
      error.textContent = "";
      await send({topic: button.dataset.topic, value: JSON.parse(area.value)});
      area.blur();
    } catch (e) {
      error.textContent = String(e.message || e);
    }
  });
}
document.getElementById("reset").addEventListener("click", async () => {
  for (const select of document.querySelectorAll("select[data-component]")) select.value = "";
  await send({reset: true});
});
load();
setInterval(load, 2000);
"""


def target_html(server, sid, tid):
    """One target, large, with its named states and the topics it reads."""
    target = server.targets[tid]
    width, height = target.size
    scale = min(1.0, 1100 / width)
    src = html.escape(server.page_url(sid, tid))
    states = {}
    for component, name, _ in target.states:
        states.setdefault(component, []).append(name)
    pickers = "".join(
        f'<label>{html.escape(component)} <select data-component="{html.escape(component)}">'
        '<option value="">from the snapshot</option>'
        + "".join(f"<option>{html.escape(name)}</option>" for name in names)
        + "</select></label>"
        for component, names in states.items()
    )
    topics = "".join(
        f"<h3>{html.escape(topic)}</h3>"
        f'<textarea data-topic="{html.escape(topic)}" rows="6"></textarea>'
        f'<button data-topic="{html.escape(topic)}">Apply</button> <span class="error"></span>'
        for topic in target.manifest.topics
    )
    base = json.dumps(f"/s/{sid}/{tid}/_oolite/")
    title = html.escape(target.title)
    options = snapshot_options(server, sid)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(target.title)}: harness</title>"
        f"<style>{PAGE_STYLE}</style></head><body><header><form>"
        f'<a href="/?snap={html.escape(sid)}">all</a> · <strong>{title}</strong>'
        f" ({width}×{height}, {target.spec.layout}) · start from "
        f"<input type='hidden' name='target' value='{html.escape(tid)}'>"
        f"<select name='snap' onchange='this.form.submit()'>{options}</select>"
        "</form></header><main>"
        f'<div class="frame" style="width:{width * scale:.0f}px;height:{height * scale:.0f}px">'
        f'<iframe src="{src}" width="{width}" height="{height}" '
        f'style="transform:scale({scale:.3f})"></iframe></div>'
        f"<aside><h3>Named states</h3>{pickers or '<p>none</p>'}"
        '<button id="reset">Back to the snapshot</button>'
        f"{topics}</aside></main>"
        f"<script>{TARGET_SCRIPT.replace('BASE', base)}</script></body></html>"
    )


# -- screenshots ---------------------------------------------------------------


def find_chrome():
    for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def cases(server, tid, snapshots=True, states=True):
    """[(caption, file stem, snapshot id, overrides), ...]: what to take
    pictures of for a target: each snapshot, then each named state (over the
    blank snapshot)."""
    found = []
    if snapshots:
        for sid in server.order:
            found.append((f"{sid}: {server.snapshots[sid].context}", sid, sid, {}))
    if states:
        for component, name, values in server.targets[tid].states:
            stem = "state." + re.sub(r"[^a-z0-9]+", "-", f"{component} {name}".lower()).strip("-")
            found.append((f"{component}: {name}", stem, BLANK, values))
    return found


def picture(server, chrome, profile, tid, sid, overrides, path):
    """Take one picture of a target at a snapshot with these overrides; True if made."""
    width, height = server.targets[tid].size
    with server.lock:
        server.overrides[(sid, tid)] = dict(overrides)
        server.shown.pop((sid, tid), None)
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
    try:
        subprocess.run(command, capture_output=True, timeout=60, check=False)
    finally:
        with server.lock:
            server.overrides.pop((sid, tid), None)
    return path.exists()


def shoot(server, out, chrome, only=None, snapshots=True, states=True):
    """Pictures of every target into out/<target>/<case>.png, and out/index.html."""
    out = Path(out)
    shots = []
    with tempfile.TemporaryDirectory(prefix="oolite-harness-chrome-") as profile:
        for tid in server.targets:
            if only and not any(word in tid for word in only):
                continue
            for caption, stem, sid, overrides in cases(server, tid, snapshots, states):
                path = out / tid / f"{stem}.png"
                if picture(server, chrome, profile, tid, sid, overrides, path):
                    shots.append((tid, caption, path.relative_to(out)))
                else:
                    print(f"harness: no image for {tid}, {caption}", file=sys.stderr)
    rows = []
    for tid, target in server.targets.items():
        mine = [(caption, rel) for t, caption, rel in shots if t == tid]
        if not mine:
            continue
        width = min(target.size[0], 640)
        cells = "".join(
            f"<figure><figcaption>{html.escape(caption)}</figcaption>"
            f'<img src="{html.escape(str(rel))}" width="{width}"></figure>'
            for caption, rel in mine
        )
        rows.append(f"<section><h2>{html.escape(target.title)}</h2>{cells}</section>")
    (out / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Component gallery</title>"
        f"<style>{PAGE_STYLE} figure {{ display: inline-block; margin: 0 12px 12px 0; }}"
        "</style></head><body>" + "".join(rows) + "</body></html>"
    )
    return shots


README_NOTE = (
    "<!-- Made by `python -m helper.harness --readmes` from component.toml and "
    "{name}.states.json: edit those and run it again. -->"
)
WIDGET_NOTE = (
    "<!-- Made by `python -m helper.harness --readmes` from widget.toml: "
    "edit it and run it again. -->"
)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def readme(component, pictures, size):
    """A component's README.md: what component.toml says, then each named state's picture."""
    reads = ", ".join(f"`{item}`" for item in component.topics) or "nothing"
    sends = ", ".join(f"`{item}`" for item in component.actions) or "nothing"
    needs = ", ".join(f"[`{item}`](../{item}/README.md)" for item in component.needs) or "nothing"
    files = ", ".join(f"`{Path(file).name}`" for file in component.files)
    lines = [
        README_NOTE.format(name=component.name),
        "",
        f"# {component.name}",
        "",
        component.description,
        "",
        "| | |",
        "|---|---|",
        f"| **Reads** | {reads} |",
        f"| **Sends** | {sends} |",
        f"| **Needs** | {needs} |",
        f"| **Files** | {files} |",
        f"| **Tests** | `{component.name}.test.js` |",
        "",
        f'Use it in a widget: `components = ["{component.name}"]`. '
        f"Try it: `python -m helper.harness {component.name}`.",
        "",
        "## Named states",
        "",
        f"From `{component.name}.states.json`. *Shows nothing* means it draws nothing in that "
        "state; a widget hides while all its components do.",
        "",
    ]
    lines += picture_rows(pictures, size)
    return "\n".join(lines)


def picture_rows(pictures, size):
    """The table of named states: one row per state, its name then its picture
    (strips at their own width, bigger widgets scaled down)."""
    width, height = size
    shown = min(width, 700) if height <= 100 else 560
    rows = [
        f"| **{state}** | "
        + (
            f'<img src="images/{file}" width="{shown}" alt="{html.escape(state)}">'
            if file
            else "*shows nothing*"
        )
        + " |"
        for state, file in pictures
    ]
    return ["| State | Picture |", "|---|---|", *rows, ""]


def _extent(given, side, docked_sides):
    if given:
        return f"{given} px"
    return f"the game's {side}" if docked_sides else "what its components need"


def _own_rows(named):
    """Table rows for what a widget that draws itself reads and sends."""

    def listed(items):
        return ", ".join(f"`{item}`" for item in items)

    rows = []
    if named.topics:
        rows.append(f"| **Reads too** | {listed(named.topics)} |")
    if named.actions:
        rows.append(f"| **Sends too** | {listed(named.actions)} |")
    return rows


def widget_readme(named, pictures, size):
    """A named widget's README.md: what widget.toml says, then a picture of the widget
    in each of its named states."""
    spec = named.spec
    links = ", ".join(f"[`{name}`](../../components/{name}/README.md)" for name in spec.components)
    side = spec.dock.split(":")[1] if spec.dock else None
    where = f"`{spec.dock}`" if spec.dock else f"free, on {spec.screen or 'the desktop'}"
    width = _extent(spec.width, "width", side in ("top", "bottom"))
    height = _extent(spec.height, "height", side in ("left", "right"))
    lines = [
        WIDGET_NOTE,
        "",
        f"# {named.name}",
        "",
        named.description,
        "",
        "| | |",
        "|---|---|",
        f"| **Components** | {links} |",
        f"| **Dock** | {where} |",
        f"| **Width** | {width} |",
        f"| **Height** | {height} |",
        f"| **Layout** | `{spec.layout}` |",
        *_own_rows(named),
        "",
        "Use it in `config.toml`, changing any setting `[[widgets]]` takes:",
        "",
        "```toml",
        "[[widgets]]",
        f'widget = "{named.name}"',
        "```",
        "",
        f"Its id is `{named.name}` unless you give another. "
        f"Try it: `python -m helper.harness {named.name}`.",
        "",
        "## Named states",
        "",
        "From `[states]` in `widget.toml`: each names a state of each of its components. "
        "*Shows nothing* means none of them draws anything then, so the widget hides.",
        "",
    ]
    lines += picture_rows(pictures, size)
    return "\n".join(lines)


# Files every component's README depends on, the root styles among them: a
# change here remakes them all.
SHARED = (
    "helper/web/lib/",
    "helper/web/__init__.py",
    "helper/harness.py",
    "helper/plugin_api.py",  # makes the theme stylesheet, _oolite/theme.css
    "helper/plugins.py",
    "helper/tk/components/style.py",  # the theme's colours, fonts and layout scales
)
WIDGETS_SHARED = ("helper/widgets.py",)  # reads widget.toml; a change remakes every named widget's
GENERATED = re.compile(r"helper/web/(components|widgets)/[^/]+/(README\.md|images/)")


def _folders(paths, kind):
    """The folder names under helper/web/<kind>/ that these paths are in."""
    prefix = f"helper/web/{kind}/"
    return {path.split("/")[3] for path in paths if path.startswith(prefix) and path.count("/") > 3}


def affected(paths, components=None, widgets=None):
    """The components and named widgets whose README should be made again after
    these files changed: components whose own files changed and those that
    need them, then named widgets whose files or components changed. All of them if
    a shared file changed. The READMEs and pictures themselves don't count, so
    a refresh never causes another."""
    components = COMPONENTS if components is None else components
    widgets = WIDGETS if widgets is None else widgets
    paths = [path for path in paths if not GENERATED.match(path)]
    if any(path.startswith(SHARED) for path in paths):
        return [*components, *widgets]
    changed = _components_affected(paths, components)
    every_widget = any(path.startswith(WIDGETS_SHARED) for path in paths)
    own = _folders(paths, "widgets")
    remade = [
        name
        for name, named in widgets.items()
        if every_widget
        or name in own
        or {c.name for c in web.loaded(components, named.spec.components)} & set(changed)
    ]
    return changed + remade


def _components_affected(paths, components):
    changed = _folders(paths, "components")
    while True:
        needing = {name for name, c in components.items() if set(c.needs) & changed} - changed
        if not needing:
            break
        changed |= needing
    return [name for name in components if name in changed]


def changed_since(ref):
    """The files changed on this branch since it left ref (git diff ref...HEAD)."""
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{ref}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def state_pictures(server, chrome, profile, tid, states, images):
    """Pictures of a target in each state, [(label, stem, {topic: value}), ...],
    into images/; [(label, file or None if it showed nothing), ...]. Older
    pictures there are removed."""
    wanted, pictures = set(), []
    for label, stem, values in states:
        file = f"{stem}.png"
        if not picture(server, chrome, profile, tid, BLANK, values, images / file):
            continue
        if server.shown.get((BLANK, tid), (0, True))[1] is False:  # the page hid itself
            pictures.append((label, None))
        else:
            wanted.add(file)
            pictures.append((label, file))
    for old in images.glob("*.png") if images.exists() else ():
        if old.name not in wanted:
            old.unlink()
    return pictures


def readmes(server, chrome, folder=web.DIR):
    """Each component's and named widget's README.md, with pictures of its named
    states in its images/ folder."""
    written = []
    with tempfile.TemporaryDirectory(prefix="oolite-harness-chrome-") as profile:
        for name, component in COMPONENTS.items():
            tid = f"component.{name}"
            if tid not in server.targets:
                continue
            here = Path(folder) / "components" / name
            states = [(state, slug(state), values) for state, values in component.states]
            pictures = state_pictures(server, chrome, profile, tid, states, here / "images")
            (here / "README.md").write_text(readme(component, pictures, server.targets[tid].size))
            written.append(here / "README.md")
        for name, named in WIDGETS.items():
            tid = f"widget.{name}"
            if tid not in server.targets:
                continue
            here = Path(folder) / "widgets" / name
            target = server.targets[tid]
            states = [(s, slug(s), values) for c, s, values in target.states if c == "widget"]
            pictures = state_pictures(server, chrome, profile, tid, states, here / "images")
            (here / "README.md").write_text(widget_readme(named, pictures, target.size))
            written.append(here / "README.md")
    return written


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "targets",
        nargs="*",
        metavar="NAME",
        help="a component, components joined with + (as a widget), or a widget id from the "
        "config (default: everything)",
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
        "--states-only", action="store_true", help="--shots: only the named states, no snapshots"
    )
    parser.add_argument(
        "--readmes",
        action="store_true",
        help="write each component's and named widget's README.md and pictures of its named "
        "states, then exit "
        "(only the NAMEs given, if any)",
    )
    parser.add_argument(
        "--since",
        metavar="REF",
        help="--readmes: only components and named widgets changed since git REF (and those "
        "needing them)",
    )
    args = parser.parse_args()
    try:
        import tests.fakegame  # noqa: F401
    except ImportError:
        parser.error("run this from the oolite-helper repository (it needs tests/fakegame.py)")
    paths = args.scenario or sorted(SCENARIOS.glob("*.yaml"))
    if args.readmes:
        paths = []  # READMEs show the named states, over the blank snapshot
    if args.since:
        try:
            args.targets = affected(changed_since(args.since))
        except (OSError, subprocess.CalledProcessError) as error:
            parser.error(f"--since {args.since}: {error}")
        if not args.targets:
            print(f"Nothing changed since {args.since}: no READMEs to make.")
            return
        print(f"Changed since {args.since}: {', '.join(args.targets)}")
    try:
        keymap = load_keymap()
    except Exception:
        keymap = None  # no game here: keys show as unbound
    with tempfile.TemporaryDirectory(prefix="oolite-harness-") as folder:
        try:
            snaps = snapshots(paths, keymap, folder)
            found = targets(args.config, names=args.targets)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        port = 0 if args.shots or args.readmes else args.port
        server = HarnessServer(("127.0.0.1", port), snaps, found)
        if args.shots or args.readmes:
            chrome = find_chrome()
            if chrome is None:
                parser.error("pictures need google-chrome or chromium on the PATH")
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                if args.readmes:
                    written = readmes(server, chrome)
                    print(f"{len(written)} READMEs in {web.DIR}")
                    return
                shots = shoot(server, args.shots, chrome, snapshots=not args.states_only)
            finally:
                server.shutdown()
            print(f"{len(shots)} images; open {args.shots / 'index.html'}")
            return
        where = server.url
        if len(found) == 1:
            where += f"?target={urllib.parse.quote(found[0].id)}"
        print(f"Component harness at {where} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
