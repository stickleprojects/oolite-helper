# Copilot instructions: Oolite Key Helper

A second-screen helper for the space game Oolite. An Oolite add-on writes JSON messages describing game events to the game log, and a Python/Tk window follows the log and shows the keys for the current context. Read `README.md` for the overview and `CLAUDE.md` for the full project notes; the rules below are the ones that matter most when working on an issue.

## Layout

- `oxp/CtxKeys.oxp/Config/script.js`: the Oolite world script (JavaScript, runs inside the game). All output goes through `this._emit(type, data)`, which writes `[ctxkeys]: {json}` log lines.
- `helper/`: the Python package (`oolite-helper` entry point).
  - `sources.py` follows the log; `state.py` turns messages into a context.
  - `contexts.py` lists which actions to show; `keys.py`/`plist.py` read the key bindings.
  - `screen.py` places the window; `settings.py` reads and checks config.toml and layout.toml (pydantic, #135); `app.py` is the Tk window.
- `scripts/launch-oolite.sh`: game launcher (fixes the AppImage's data folders, starts the helper).

## Rules

- **Work on a branch and open a PR against `main`.** `main` is protected for everyone. Reference the issue with `Closes #N`.
- **Never hard-code key bindings.** Keys and their descriptions always come from the game's own `keyconfig2.plist` and `descriptions.plist`, plus the player's overrides. `contexts.py` holds action names only (`key_docking_clearance_request`, …).
- **Game behaviour claims need a source.** Tips and notes in `contexts.py` cite the Oolite 1.92.1 source (`PlayerEntityControls.m`, `StationEntity.m`, …). Don't add gameplay advice from memory. Link the source file and line in the PR if you add one.
- **The message format is a contract.** If you change what the add-on sends, update the helper's `state.py`, the test scenarios, and the docs in the same PR.
- **Python 3.11+, standard library only** at runtime (Tkinter comes from the system). Dev/test tools go in `[project.optional-dependencies] dev` in `pyproject.toml`.
- **No game, no display in this environment.** Oolite isn't installed here. Keep logic out of Tk widgets so it can be tested headless. Use `xvfb-run` only for smoke tests that the window builds.
- **Don't commit** extracted AppImage contents, game logs, save files, `.venv/` or `*.egg-info/`.
- Match the existing style: small modules, docstrings that say *why*, comments only where the code can't speak for itself.

## Running things

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]" pytest ruff==0.17.1
.venv/bin/python -m pytest -q
.venv/bin/ruff format . && .venv/bin/ruff check --fix .   # rules in ruff.toml
node --check oxp/CtxKeys.oxp/Config/script.js
node --test tests/oxp/script.test.js
shellcheck scripts/*.sh
```

CI runs all of these on every PR (`.github/workflows/ci.yml`) and must pass before merging,
so run them, including `ruff format`, before pushing.
