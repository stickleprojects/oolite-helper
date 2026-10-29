# Components

A **component** draws one part of the game's state, such as the key list, the docking clearance badge or the TORUS/JUMP lamps. It has no window of its own: it's shown inside a **widget**, a window that hosts one or more components, docked beside the game or placed on a monitor. Widgets you can use by name live in [../widgets/](../widgets/README.md). The helper's main window is made of components too.

Each folder here is one component. Open its `README.md` to see what it reads and sends, and a picture of each of its named states.

## What's in a component folder

| File | What | Written by |
|---|---|---|
| `component.toml` | Description, tab `title`, the `topics` it reads, the `actions` it may send, other components it `needs` | you |
| `<name>.js`, `<name>.css` | The component: `Oolite.component(name, {render(state, refresh)})` | you |
| `<name>.states.json` | Named example states, `{state: {topic: value}}`, for the harness, the tests and the README | you |
| `<name>.test.js` | Its tests (`node --test`) | you |
| `README.md`, `images/` | What `component.toml` says, and a picture of each named state | **generated** |

[docs/architecture.md](../../../docs/architecture.md) explains how to write one.

## Generated READMEs and pictures

Don't edit a component's `README.md` or `images/` by hand. Edit `component.toml` or `<name>.states.json` instead. Then either run

```bash
.venv/bin/python -m helper.harness --readmes <name>
```

to look at the result, or let CI do it.

**CI makes the pictures that are kept**, because fonts and rendering differ between machines. On a pull request, the Component READMEs workflow ([readmes.yml](../../../.github/workflows/readmes.yml)) runs `--readmes --since origin/main` and commits any change to your branch. So pull before you push again.

It remakes only what your branch changed:

- **A component's own files changed:** that component's README, the READMEs of components that `need` it, and those of the widgets that show any of them.
- **A shared file changed** (`helper/web/lib/`, the harness, the plugin API, the theme's styles): every component and every widget.
- **Anything else** (game state, the add-on, docs, generated READMEs and pictures): nothing.

A test fails if a README is missing a named state, so a new state needs a refresh.

## Trying a component

```bash
.venv/bin/python -m helper.harness clearance          # one component, with fake game data
.venv/bin/python -m helper.harness clearance+drive    # several, together as a widget
```
