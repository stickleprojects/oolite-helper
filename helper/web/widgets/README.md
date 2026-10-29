# Widgets

A **widget** is a small window that hosts one or more **components**, docked beside the game window or placed on a monitor. A component draws one part of the game's state, such as the docking clearance badge, and has no window of its own (see [../components/](../components/README.md)). Each folder here defines one widget, with its components, dock and size chosen for you, so `config.toml` can use it by name. Open its `README.md` to see where it goes and a picture of it in each of its named states.

## Using a widget by name

In `~/.config/oolite-helper/config.toml`:

```toml
[[widgets]]
widget = "top-strip"     # the widget
dock = "game:bottom"     # optional: change any of its settings
```

Any setting a `[[widgets]]` table takes can be changed this way (see [config.example.toml](../../../config.example.toml)). The widget's id is its name unless you give it an `id`. The id is what saves your moves and resizes in `layout.toml`.

## What's in a widget folder

| File | What | Written by |
|---|---|---|
| `widget.toml` | A `description`, the same settings as a `[[widgets]]` table (`components`, `dock`, `width`, ...), and `[states]` | you |
| `<name>.js`, `<name>.css` | Optional: the widget's own drawing (see below) | you |
| `<name>.states.json` | Optional: the widget's own named states, over its own `topics` | you |
| `<name>.test.js` | Optional: tests for its drawing, run with `node --test` | you |
| `README.md`, `images/` | Its settings, links to its components, and a picture of the whole widget in each named state | **generated** |

Each entry in `[states]` names a state for **every** component in the widget, so the picture shows the widget as it looks in the game:

```toml
[states]
"waiting for clearance" = {clearance = "requested", drive = "mass locked"}
```

The state names on the right come from each component's `<name>.states.json`. The helper checks `widget.toml` when it starts, the same way it checks a `[[widgets]]` table: unknown settings, a state that leaves out a component, or a state a component doesn't have all stop it with a message.

## A widget that draws itself

By default a widget draws its components side by side. A widget folder with its own `.js` draws the widget instead, as [tabs](tabs/README.md) does: a tab row over one component at a time. The script registers a widget of the folder's name:

```js
Oolite.widget("tabs", {
  draw(names, state, part, dispatch) {
    // names: its components; part(name) renders one; dispatch(action) sends one
    return node; // or null when there's nothing to show
  },
});
```

Its files load after its components'. `widget.toml` can then also say:

- `topics` and `actions`: what the widget itself reads and may send, beyond its components' (tabs: `["tabs"]` and `["ui/choose_tab"]`);
- `titled = true`: every component needs a `title` in its `component.toml`, e.g. its tab label.

Its own named states go in `<name>.states.json`. When it has some, each `[states]` entry names one of them too, keyed by the widget's name:

```toml
"all keys" = {keys = "near a station", all_keys = "two groups", trade_table = "three commodities", tabs = "all keys shown"}
```

## Generated READMEs and pictures

As with components, don't edit a widget's `README.md` or `images/` by hand, and let CI make the pictures that are kept. The Component READMEs workflow remakes a widget's README when:

- a file in its own folder changes;
- one of its components changes, or a component one of them `needs`;
- `helper/widgets.py` changes (it reads `widget.toml`);
- a shared file changes (`helper/web/lib/`, the harness, the plugin API, the theme's styles).

Otherwise the widget's README is left alone. A test fails if a README is missing one of the widget's states.

To look at the result locally:

```bash
.venv/bin/python -m helper.harness top-strip             # open it with fake game data
.venv/bin/python -m helper.harness --readmes top-strip   # write its README and pictures
```

## Adding a widget

1. Make a folder named after it (letters, digits, `-`, `_`; not the same name as a component).
2. Write `widget.toml` with a `description`, its settings and its `[states]`. Don't set `id`: the folder name is its id.
3. Run `--readmes <name>` to check it, and open a pull request. CI commits the README and pictures.
