"""Serve a plugin in a browser with a scenario-driven model."""

import argparse
import json
import math
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import plugin_api
from .keys import load_keymap
from .markets import MarketStore
from .model import Model
from .plugins import read_manifest
from .webhost.host import MIME, csp, page_message, resolve


def _preview_csp(name):
    """Adapt the plugin-scheme policy to this server's same-origin files."""
    return (
        csp(name)
        .replace(f"plugin://{name}", "'self'")
        .replace("connect-src 'none'", "connect-src 'self'")
    )


def _dev_script():
    return f"""(() => {{
  if (window.oolite) return;
  const handlers = new Map(), last = new Map();
  const post = (message) => fetch("/_oolite/message", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(message)
  }});
  const oolite = Object.freeze({{
    api: {plugin_api.API},
    on(topic, fn) {{
      if (!handlers.has(topic)) handlers.set(topic, new Set());
      handlers.get(topic).add(fn);
      if (last.has(topic)) fn(last.get(topic));
      return () => handlers.get(topic).delete(fn);
    }},
    dispatch(action) {{ post({{type: "dispatch", action}}); }},
    resize(width, height) {{ post({{type: "resize", width, height}}); }},
    log(text) {{ post({{type: "log", text: String(text)}}); }}
  }});
  const receive = (topic, value) => {{
    last.set(topic, value);
    for (const fn of handlers.get(topic) || []) {{
      try {{ fn(value); }} catch (error) {{ oolite.log(`${{topic}}: ${{error}}`); }}
    }}
  }};
  Object.defineProperty(window, "oolite", {{value: oolite}});
  const events = new EventSource("/_oolite/events");
  events.onmessage = (event) => {{
    const {{topic, value}} = JSON.parse(event.data);
    receive(topic, value);
  }};
}})();
"""


class PreviewServer(ThreadingHTTPServer):
    """A threaded local-only server for one validated plugin."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, manifest, model, layout="compact"):
        if layout not in plugin_api.LAYOUTS:
            raise ValueError(f"unknown layout {layout!r}")
        self.manifest = manifest
        self.model = model
        self.layout = layout
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.scenario_thread = None
        super().__init__(address, PreviewHandler)

    def shutdown(self):
        self.stopping.set()
        super().shutdown()

    def topic_values(self):
        values = {name: plugin_api.topic_value(self.model, name) for name in self.manifest.topics}
        if self.manifest.keys:
            values[plugin_api.KEYS_TOPIC] = {
                action: plugin_api.key_info(self.model, action) for action in self.manifest.keys
            }
        return values

    def start_scenario(self, steps, speed=1, loop=False):
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or speed <= 0
        ):
            raise ValueError("speed must be a positive number")
        if self.scenario_thread is not None:
            raise RuntimeError("scenario is already running")
        self.scenario_thread = threading.Thread(
            target=self._play_scenario, args=(steps, speed, loop), daemon=True
        )
        self.scenario_thread.start()
        return self.scenario_thread

    def _play_scenario(self, steps, speed, loop):
        index = 0
        finished = False
        while not self.stopping.is_set():
            if finished or not steps:
                if self.stopping.wait(0.2):
                    break
                with self.lock:
                    self.model.notify()
                continue

            step = steps[index]
            deadline = time.monotonic() + step["after"] / speed
            while not self.stopping.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.stopping.wait(min(0.2, remaining)):
                    return
                with self.lock:
                    self.model.notify()

            if self.stopping.is_set():
                break
            if "msg" in step:
                with self.lock:
                    self.model.dispatch(step["msg"])
            elif "close" in step:
                index = len(steps)
            with self.lock:
                self.model.notify()

            index += 1
            if index >= len(steps):
                if loop:
                    index = 0
                else:
                    finished = True


class PreviewHandler(BaseHTTPRequestHandler):
    server: PreviewServer
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/_oolite/theme.css":
            self._respond(
                200,
                plugin_api.theme_css(self.server.layout).encode(),
                "text/css",
            )
        elif path == "/_oolite/dev.js":
            self._respond(200, _dev_script().encode(), "text/javascript")
        elif path == "/_oolite/events":
            self._events()
        else:
            self._file()

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/_oolite/message":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_error(400)
            return
        if not 0 <= length <= 65536:
            self.send_error(413)
            return
        message = page_message(self.rfile.read(length).decode("utf-8", errors="replace"))
        if message is None:
            self.send_error(400, "invalid plugin message")
            return

        if message["type"] == "dispatch":
            action = plugin_api.check_action(message["action"], self.server.manifest.actions)
            if action is None:
                print(
                    f"plugin {self.server.manifest.name}: refused action {message['action']!r}",
                    file=sys.stderr,
                    flush=True,
                )
                self.send_error(403, "action refused")
                return
            with self.server.lock:
                self.server.model.dispatch(action)
                self.server.model.notify()
        elif message["type"] == "log":
            print(
                f"plugin {self.server.manifest.name}: {message['text']}",
                file=sys.stderr,
                flush=True,
            )
        self._respond(204, b"", "text/plain")

    def _file(self):
        request_path = self.path
        if urllib.parse.urlsplit(request_path).path == "/":
            request_path = "/" + self.server.manifest.entry
        uri = f"plugin://{self.server.manifest.name}{request_path}"
        path = resolve(self.server.manifest.root, self.server.manifest.name, uri)
        if path is None:
            self.send_error(404)
            return
        try:
            with open(path, "rb") as file:
                data = file.read()
        except OSError:
            self.send_error(404)
            return
        mime = MIME.get(Path(path).suffix.lower(), "application/octet-stream")
        self._respond(200, data, mime)

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Security-Policy", _preview_csp(self.server.manifest.name))
        self.end_headers()
        previous = {}
        try:
            while not self.server.stopping.is_set():
                with self.server.lock:
                    values = self.server.topic_values()
                for topic, value in values.items():
                    if topic in previous and previous[topic] == value:
                        continue
                    previous[topic] = value
                    payload = json.dumps(
                        {"topic": topic, "value": value}, ensure_ascii=False, separators=(",", ":")
                    )
                    self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()
                if self.server.stopping.wait(0.2):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _respond(self, status, data, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", _preview_csp(self.server.manifest.name))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if data:
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path, help="plugin folder")
    parser.add_argument(
        "--scenario", type=Path, default=Path("scenarios/trade.yaml"), help="fake-game scenario"
    )
    parser.add_argument("--speed", type=float, default=1, help="timeline speed multiplier")
    parser.add_argument("--loop", action="store_true", help="repeat the scenario")
    parser.add_argument("--port", type=int, default=8565)
    parser.add_argument("--layout", choices=plugin_api.LAYOUTS, default="compact")
    args = parser.parse_args()
    try:
        # The fake game lives with the tests, so the preview runs from a checkout.
        from tests.fakegame import load_scenario
    except ImportError:
        parser.error("run this from the oolite-helper repository (it needs tests/fakegame.py)")
    try:
        manifest = read_manifest(args.plugin)
        steps = load_scenario(args.scenario)
        with tempfile.TemporaryDirectory(prefix="oolite-preview-") as directory:
            try:
                keymap = load_keymap()
            except Exception:
                keymap = None
            model = Model(
                markets=MarketStore(Path(directory) / "markets.json"),
                keymap=keymap,
            )
            server = PreviewServer(("127.0.0.1", args.port), manifest, model, args.layout)
            server.start_scenario(steps, args.speed, args.loop)
            print(
                f"Serving {manifest.name} at http://127.0.0.1:{server.server_port}/ "
                "(Ctrl+C to stop)",
                flush=True,
            )
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.shutdown()
                server.server_close()
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
