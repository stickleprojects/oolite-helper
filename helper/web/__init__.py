"""The built-in web components (#82), and the page for each widget.

Each component is a folder in helper/web/components/<name>/ holding a
component.toml and its files:

    description = "TORUS ✓/✗ and JUMP ✓/✗ while flying"
    title = "Drive"                      # optional: its tab label in a tabs widget
    topics = ["drive"]                   # what it reads: names from plugin_api.TOPICS
    actions = ["ui/choose_tab"]          # optional: what it may send (plugin_api.ACTIONS)
    needs = ["keys"]                     # optional: other components whose files it uses

and <name>.states.json: named example states, {name: {topic: value}}, which
the harness offers and takes pictures of, and the tests render.

Its .js files register it with Oolite.component() (helper/web/lib/widget.js)
and its .css files style it. Its tests ship beside it as <name>.test.js (run
with node --test; lib/testing.js gives them a fake DOM) and are never loaded
into a page. A widget's page is generated: it loads the shared
files in lib/ and the files of the components the widget lists (and what they
need), nothing else, and the widget gets only those components' topics and
may send only their actions.

A widget draws its components side by side, unless it's a named widget that
draws itself (helper/widgets.py): then the page also loads the widget's own
files, after the components', and gets the widget's own topics and actions
too. The tabs widget, for one, shows its components one at a time under a
tab row.
"""

import html
import json
import os
import tomllib
from dataclasses import dataclass

from ..plugin_api import ACTIONS, TOPICS

DIR = os.path.dirname(os.path.abspath(__file__))
COMPONENTS_DIR = os.path.join(DIR, "components")
HOST = "builtin"  # the pages' address: plugin://builtin/
LIB_CSS = ("lib/base.css",)
LIB_JS = ("lib/dom.js", "lib/format.js", "lib/widget.js")


@dataclass(frozen=True)
class WebComponent:
    name: str
    description: str
    topics: tuple
    title: str | None = None  # its label as a tab; None: it can't be one
    actions: tuple = ()
    needs: tuple = ()
    files: tuple = ()  # its .css and .js files, relative to DIR
    states: tuple = ()  # ((name, {topic: value}), ...) from <name>.states.json


def read_component(folder):
    """The WebComponent in folder/component.toml; raises ValueError saying what's wrong."""
    name = os.path.basename(os.path.normpath(folder))
    with open(os.path.join(folder, "component.toml"), "rb") as f:
        data = tomllib.load(f)
    unknown = set(data) - {"description", "title", "topics", "actions", "needs"}
    if unknown:
        raise ValueError(f"component {name}: unknown settings: {', '.join(sorted(unknown))}")
    topics, actions = data.get("topics", []), data.get("actions", [])
    if not all(topic in TOPICS for topic in topics):
        raise ValueError(f"component {name}: topics must be from plugin_api.TOPICS")
    if not all(action in ACTIONS for action in actions):
        raise ValueError(f"component {name}: actions must be from plugin_api.ACTIONS")
    files = sorted(
        f"components/{name}/{file}"
        for file in os.listdir(folder)
        if file.endswith((".css", ".js")) and not file.endswith(".test.js")
    )
    states = ()
    states_file = os.path.join(folder, f"{name}.states.json")
    if os.path.exists(states_file):
        with open(states_file, encoding="utf-8") as f:
            named = json.load(f)
        for state, values in named.items():
            if not isinstance(values, dict) or not set(values) <= set(topics):
                raise ValueError(f"component {name}: state {state!r} may only set its topics")
        states = tuple(named.items())
    return WebComponent(
        name,
        data.get("description", ""),
        tuple(topics),
        data.get("title"),
        tuple(actions),
        tuple(data.get("needs", [])),
        tuple(files),
        states,
    )


def discover(folder=COMPONENTS_DIR):
    """{name: WebComponent} for every built-in component. A broken one is a bug: it raises."""
    found = {
        name: read_component(os.path.join(folder, name))
        for name in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, name, "component.toml"))
    }
    for component in found.values():
        missing = set(component.needs) - set(found)
        if missing:
            raise ValueError(f"component {component.name} needs {', '.join(sorted(missing))}")
    return found


def loaded(components, names):
    """The components to load for a widget listing names: what they need first, each once."""
    order = []

    def add(name):
        if name in order:
            return
        for need in components[name].needs:
            add(need)
        order.append(name)

    for name in names:
        add(name)
    return [components[name] for name in order]


def tab_titles(components):
    """[(name, title), ...] for the components that can be tabs: Keys first
    (an emergency shows it), then by name."""
    titled = sorted(components.values(), key=lambda c: (c.name != "keys", c.name))
    return [(c.name, c.title) for c in titled if c.title]


def _unique(items):
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True)
class Page:
    """A widget's generated page: what to serve, read and allow."""

    html: str
    topics: tuple
    actions: tuple


def page(components, names, widget=None):
    """The Page for a widget showing these built-in components. widget: the
    named widget it is, if any (widgets.NamedWidget), whose own files load last."""
    parts = loaded(components, names)
    files = [file for part in parts for file in part.files]
    files += widget.files if widget else ()
    # Relative to the page, _oolite/widget.html, so it works wherever it's
    # served: plugin://builtin/ in the web host, or under the harness's paths.
    css = ["theme.css", *(f"../{f}" for f in (*LIB_CSS, *files) if f.endswith(".css"))]
    js = ["dev.js", "widget.js", *(f"../{f}" for f in (*LIB_JS, *files) if f.endswith(".js"))]
    lines = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        *(f'<link rel="stylesheet" href="{html.escape(href)}">' for href in css),
        '</head><body><div id="root"></div>',
        *(f'<script src="{html.escape(src)}"></script>' for src in js),
        "</body></html>",
    ]
    own = (widget.topics, widget.actions) if widget else ((), ())
    return Page(
        "\n".join(lines) + "\n",
        _unique([*(topic for part in parts for topic in part.topics), *own[0]]),
        _unique([*(action for part in parts for action in part.actions), *own[1]]),
    )


def widget_config(names, widget, topics, width):
    """The page's OOLITE_WIDGET, as the script that sets it (_oolite/widget.js)."""
    config = {"components": list(names), "widget": widget, "topics": list(topics), "width": width}
    return f"globalThis.OOLITE_WIDGET = {json.dumps(config)};\n"
