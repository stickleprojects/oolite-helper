"""Plugin web views (#59): the helper's side of the web host process.

Plugins render themselves in HTML and JavaScript inside WebKit's sandbox, in
a separate process (host.py) because Tk and GTK don't share a main loop. The
helper drives it over a pipe:

    host = WebHost()
    host.sync({"radar": WebWindow("radar", "/path/to/radar", rect=(10, 10, 300, 200))})
    host.publish("radar", "jump_blocker", {"by": "planet"})
    for event in host.poll():  # call often, e.g. on every tick
        ...

sync() is declarative: give it every window that should exist, keyed by a
stable id, and it opens, moves, hides (rect=None) and closes to match. That's
what lets a layout change (a config file today; an admin panel later) be just
a new set of windows. If the host process dies it's restarted, with backoff,
and the windows and their latest topics are replayed. A window whose page
fails or crashes is closed and stays closed until retry(id) or a sync() that
changes it.

PROTOCOL (version 1): JSON objects, one per line.

  helper -> host (stdin)
    {"op": "open", "id": ID, "plugin": NAME, "root": DIR, "entry": "index.html",
     "background": "#101418", "extras": {NAME: TEXT}}  opens hidden; extras are
                                                      served at plugin://NAME/_oolite/
    {"op": "place", "id": ID, "rect": [x, y, w, h]}   or "rect": null to hide
    {"op": "topic", "id": ID, "name": TOPIC, "value": JSON}
    {"op": "close", "id": ID}
    {"op": "quit"}
  host -> helper (stdout)
    {"ev": "ready", "protocol": 1, "api": 1, "webkit": "2.52.6"}
    {"ev": "loaded", "id": ID}
    {"ev": "page", "id": ID, "msg": {"type": "resize", "width": w, "height": h}}
    {"ev": "page", "id": ID, "msg": {"type": "show", "shown": bool}}
    {"ev": "page", "id": ID, "msg": {"type": "log", "text": "..."}}
    {"ev": "page", "id": ID, "msg": {"type": "dispatch", "action": {...}}}  unchecked!
    {"ev": "error", "id": ID or null, "message": "..."}
    {"ev": "crashed", "id": ID, "reason": "crashed" | "exceeded-memory-limit" | ...}
    {"ev": "closed", "id": ID}
  made by WebHost.poll() itself
    {"ev": "host_exited", "code": N}                  restarting after a delay
    {"ev": "unavailable", "message": "..."}           couldn't start; retrying
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass

from ..components.style import BG

PROTOCOL = 1
HOST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "host.py")
# The system Python, which has the GTK and WebKit bindings (python3-gi,
# gir1.2-webkit2-4.1); the helper's venv doesn't.
PYTHON = os.environ.get("OOLITE_HELPER_WEBHOST_PYTHON", "/usr/bin/python3")
RESTART_DELAYS = (1, 2, 5, 10, 30)  # seconds before each successive restart
WRITE_BUFFER_LIMIT = 1 << 20  # unsent bytes before the host counts as hung
# Passed through to the host; everything else in the helper's environment is dropped.
PASS_ENV = (
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "DISPLAY",
    "XDG_RUNTIME_DIR",
    "XDG_DATA_DIRS",
    "XDG_CONFIG_DIRS",
    "DBUS_SESSION_BUS_ADDRESS",
)


@dataclass(frozen=True)
class WebWindow:
    plugin: str  # the name in plugin://<name>/
    root: str  # the plugin's folder: the only files its pages can load
    entry: str = "index.html"
    rect: tuple | None = None  # (x, y, w, h), or None to hide
    extras: tuple = ()  # ((name, text), ...): files served at plugin://<plugin>/_oolite/<name>

    def page(self):
        return (self.plugin, self.root, self.entry, self.extras)


def runtime_dir(environ=os.environ):
    """A private folder for the helper's run-time files (the X cookie)."""
    base = environ.get("XDG_RUNTIME_DIR") or f"/tmp/oolite-helper-{os.getuid()}"
    path = os.path.join(base, "oolite-helper")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def cache_dir(environ=os.environ):
    base = environ.get("XDG_CACHE_HOME") or os.path.join(environ["HOME"], ".cache")
    path = os.path.join(base, "oolite-helper", "webhost")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def sandbox_env(environ, cookie, cache):
    """The host's environment. Each setting closes a hole the #59 spike found.

    WebKit's sandbox binds whatever these point at into the web process:
    - XDG_CACHE_HOME: otherwise the whole real ~/.cache, read-write
    - XAUTHORITY: an *untrusted* cookie, so X hides XTEST, RECORD, XInput and
      GLX from it (no keylogging or screenshots); otherwise ~/.Xauthority
    - PULSE_SERVER: a socket that doesn't exist; otherwise the sound server,
      read-write, which can record the microphone
    """
    env = {name: environ[name] for name in PASS_ENV if name in environ}
    env.update(
        XAUTHORITY=cookie,
        XDG_CACHE_HOME=cache,
        PULSE_SERVER="unix:/nonexistent/pulse",
        GDK_BACKEND="x11",  # popup placement is X11's
    )
    return env


def untrusted_cookie(path, display, run=subprocess.run):
    """Write an untrusted X cookie for display to path; None, or why it failed.

    timeout 60: the X server forgets the cookie once nothing has used it for a
    minute, so an old one is useless after the host stops.
    """
    if os.path.exists(path):
        os.remove(path)  # xauth would merge into it
    try:
        result = run(
            ["xauth", "-q", "-f", path, "generate", display, ".", "untrusted", "timeout", "60"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"couldn't run xauth: {exc}"
    if result.returncode != 0 or not os.path.exists(path):
        return f"xauth couldn't make an untrusted cookie: {result.stderr.strip()}"
    return None


def default_env():
    """The sandbox environment for a new host; raises RuntimeError if it can't be made safe."""
    display = os.environ.get("DISPLAY")
    if not display:
        raise RuntimeError("no DISPLAY")
    cookie = os.path.join(runtime_dir(), "webhost.xauth")
    problem = untrusted_cookie(cookie, display)
    if problem:
        raise RuntimeError(problem)  # fail closed: never fall back to the trusted cookie
    return sandbox_env(os.environ, cookie, cache_dir())


class WebHost:
    def __init__(self, command=None, make_env=default_env, clock=time.monotonic):
        self.command = command or [PYTHON, "-I", HOST]
        self.make_env = make_env
        self.clock = clock
        self.process = None
        self.ready = False
        self.windows = {}  # id -> WebWindow: what should exist
        self.opened = {}  # id -> WebWindow: what the host has (as far as we know)
        self.topics = {}  # id -> {topic: value}: the latest of each, replayed on reopen
        self.failed = {}  # id -> why: closed after an error, until retry() or a change
        self.restarts = 0
        self.next_start = 0.0
        self._read = b""
        self._write = b""
        self._pending = []  # events made here between polls

    # -- what the helper calls -------------------------------------------

    def sync(self, windows):
        """Make the host's windows match windows ({id: WebWindow})."""
        for wid in set(self.windows) - set(windows):
            self.topics.pop(wid, None)
            self.failed.pop(wid, None)
        for wid, window in windows.items():
            old = self.windows.get(wid)
            if old is not None and old.page() != window.page():
                self.topics.pop(wid, None)
                self.failed.pop(wid, None)  # a changed window gets another chance
        self.windows = dict(windows)
        self._reconcile()

    def publish(self, wid, topic, value):
        """Send a topic's value to a window's page, if it changed."""
        topics = self.topics.setdefault(wid, {})
        if topic in topics and topics[topic] == value:
            return
        topics[topic] = value
        if wid in self.opened:
            self._send(op="topic", id=wid, name=topic, value=value)

    def retry(self, wid):
        """Reopen a window that failed (e.g. a "reopen" button)."""
        if self.failed.pop(wid, None) is not None:
            self._reconcile()

    def poll(self):
        """Start or restart the host if due, flush commands and return new events."""
        events, self._pending = self._pending, []
        if self.process is not None and self.process.poll() is not None:
            events.append({"ev": "host_exited", "code": self.process.returncode})
            self._stopped()
        if self.process is None and self.clock() >= self.next_start:
            events.extend(self._start())
        if self.process is not None:
            self._flush()
            events.extend(self._handle(e) for e in self._read_events())
        return [e for e in events if e is not None]

    def close(self):
        if self.process is None:
            return
        self._send(op="quit")
        self._flush()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process = None

    # -- the process -----------------------------------------------------

    def _start(self):
        try:
            env = self.make_env()
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                env=env,
                start_new_session=True,  # Ctrl+C is for the helper; the host exits when it does
            )
        except (OSError, RuntimeError) as exc:
            self._backoff()
            return [{"ev": "unavailable", "message": f"plugins can't start: {exc}"}]
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)
        self.ready = False
        self.opened = {}
        self._read = self._write = b""
        return []

    def _stopped(self):
        self.process = None
        self.ready = False
        self.opened = {}
        self._backoff()

    def _backoff(self):
        delay = RESTART_DELAYS[min(self.restarts, len(RESTART_DELAYS) - 1)]
        self.restarts += 1
        self.next_start = self.clock() + delay

    def _kill(self, why):
        self.process.kill()
        self.process.wait()
        self._stopped()
        self._pending.append({"ev": "host_exited", "code": None, "message": why})

    def _send(self, **command):
        self._write += json.dumps(command).encode() + b"\n"

    def _flush(self):
        while self._write:
            try:
                written = os.write(self.process.stdin.fileno(), self._write)
            except BlockingIOError:
                break
            except BrokenPipeError:
                self._write = b""  # it died; poll() notices next time
                return
            self._write = self._write[written:]
        if len(self._write) > WRITE_BUFFER_LIMIT:
            self._kill("the web host stopped reading")

    def _read_events(self):
        if self.process is None:
            return []
        while True:
            try:
                chunk = os.read(self.process.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not chunk:
                break
            self._read += chunk
        *lines, self._read = self._read.split(b"\n")
        events = []
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue  # not ours (stray output)
            if isinstance(event, dict):
                events.append(event)
        return events

    def _handle(self, event):
        kind = event.get("ev")
        if kind == "ready":
            if event.get("protocol") != PROTOCOL:
                self._kill(f"web host speaks protocol {event.get('protocol')}, not {PROTOCOL}")
                return None
            self.ready = True
            self.restarts = 0
            self._reconcile()
        elif kind in ("error", "crashed") and event.get("id") in self.opened:
            wid = event["id"]
            self.failed[wid] = event.get("message") or event.get("reason") or kind
            self._reconcile()  # closes it
        elif kind == "closed":
            self.opened.pop(event.get("id"), None)
        return event

    def _reconcile(self):
        if not self.ready:
            return  # done on "ready"
        wanted = {wid: w for wid, w in self.windows.items() if wid not in self.failed}
        for wid in list(self.opened):
            if wid not in wanted or wanted[wid].page() != self.opened[wid].page():
                self._send(op="close", id=wid)
                del self.opened[wid]
        for wid, window in wanted.items():
            old = self.opened.get(wid)
            if old is None:
                plugin, root, entry, extras = window.page()
                self._send(
                    op="open",
                    id=wid,
                    plugin=plugin,
                    root=root,
                    entry=entry,
                    background=BG,
                    extras=dict(extras),
                )
                for topic, value in self.topics.get(wid, {}).items():
                    self._send(op="topic", id=wid, name=topic, value=value)
            if old is None or old.rect != window.rect:
                rect = list(window.rect) if window.rect else None
                self._send(op="place", id=wid, rect=rect)
            self.opened[wid] = window
        if self.process is not None:
            self._flush()
