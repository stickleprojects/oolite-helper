"""The built-in web components (#82), and the page for each widget.

Each component is a folder in helper/web/components/<name>/ holding a
component.toml and its files:

    description = "TORUS ✓/✗ and JUMP ✓/✗ while flying"
    topics = ["drive"]                   # what it reads: names from plugin_api.TOPICS
    actions = ["ui/choose_tab"]          # optional: what it may send (plugin_api.ACTIONS)
    needs = ["keys"]                     # optional: other components whose files it uses

Its .js files register it with Oolite.component() (helper/web/lib/widget.js)
and its .css files style it. Its tests ship beside it as <name>.test.js (run
with node --test; lib/testing.js gives them a fake DOM) and are never loaded
into a page. A widget's page is generated: it loads the shared
files in lib/ and the files of the components the widget lists (and what they
need), nothing else, and the widget gets only those components' topics and
may send only their actions.
"""

import html
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
    actions: tuple = ()
    needs: tuple = ()
    files: tuple = ()  # its .css and .js files, relative to DIR


def read_component(folder):
    """The WebComponent in folder/component.toml; raises ValueError saying what's wrong."""
    name = os.path.basename(os.path.normpath(folder))
    with open(os.path.join(folder, "component.toml"), "rb") as f:
        data = tomllib.load(f)
    unknown = set(data) - {"description", "topics", "actions", "needs"}
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
    return WebComponent(
        name,
        data.get("description", ""),
        tuple(topics),
        tuple(actions),
        tuple(data.get("needs", [])),
        tuple(files),
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


def _unique(items):
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True)
class Page:
    """A widget's generated page: what to serve, read and allow."""

    html: str
    topics: tuple
    actions: tuple


def page(components, names):
    """The Page for a widget showing these built-in components."""
    parts = loaded(components, names)
    files = [file for part in parts for file in part.files]
    css = ["_oolite/theme.css", *LIB_CSS, *(f for f in files if f.endswith(".css"))]
    js = ["_oolite/dev.js", "_oolite/widget.js", *LIB_JS, *(f for f in files if f.endswith(".js"))]
    lines = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        *(f'<link rel="stylesheet" href="/{html.escape(href)}">' for href in css),
        '</head><body><div id="root"></div>',
        *(f'<script src="/{html.escape(src)}"></script>' for src in js),
        "</body></html>",
    ]
    return Page(
        "\n".join(lines) + "\n",
        _unique(topic for part in parts for topic in part.topics),
        _unique(action for part in parts for action in part.actions),
    )
