# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Workflow

`main` is protected for everyone, the maintainer included. Every change goes in through a pull request, and the CI checks must pass.

1. Fork the repo, or branch if you have access, from an up-to-date `main`. Use names like `fix/…`, `feat/…`, `docs/…` or `chore/…`.
2. Make your change, with tests (see below).
3. Run the checks locally (next section).
4. Open a pull request against `main`. Say what changed and how you tested it, and reference the issue with `Closes #N`.

## Running the checks locally

These are the same checks CI runs on every pull request:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" pytest ruff

.venv/bin/python -m pytest -q                    # helper tests (Python 3.11+)
.venv/bin/ruff check .                           # lint (rules in ruff.toml)
.venv/bin/ruff format --check .                  # formatting (fix with: ruff format .)
node --check oxp/CtxKeys.oxp/Config/script.js    # add-on syntax
node --test tests/oxp/script.test.js             # add-on tests (Node 20+; name the file, not the folder)
node --test helper/web/lib/*.test.js helper/web/components/*/*.test.js  # web component tests
.venv/bin/shellcheck scripts/*.sh                # launcher (shellcheck-py, in the dev extra)
```

None of these need Oolite or a display.

The plugin web host (#59) also has a live test that needs a display, GTK 3, WebKit2 4.1 (`gir1.2-webkit2-4.1`) and `xauth`. It checks the WebKit sandbox, so run it after WebKit upgrades:

```bash
OOLITE_HELPER_LIVE_WEBHOST=1 .venv/bin/python -m pytest tests/test_webhost_live.py
```

## Testing tools

- **Fake game** (`tests/fakegame.py`, `scenarios/*.yaml`): writes add-on-style log lines on a timeline. Use it to drive `GameState` in tests, or to see the helper without Oolite:
  ```bash
  .venv/bin/python -m tests.fakegame scenarios/docking.yaml --log /tmp/fake.log --speed 2 &
  .venv/bin/oolite-helper --log /tmp/fake.log --stay
  ```
- **Plugin browser preview**: serve a plugin with live scenario data, without the helper or WebKit:
  ```bash
  .venv/bin/python -m helper.preview examples/plugins/keys --scenario scenarios/trade.yaml
  ```
  Open the printed local URL. Use `--speed` to change the timeline or `--loop` to repeat it.
- **Fake Oolite** (`tests/oxp/fake-oolite.js`): runs the add-on under Node with strict stand-ins for Oolite's script objects. It throws on any property it doesn't know, so typos fail a test instead of failing silently in the game.

## Project rules

- **Never hard-code key bindings.** Keys and their descriptions come from the game's `keyconfig2.plist`/`descriptions.plist` and the player's overrides. `helper/contexts.py` holds action names only.
- **Claims about game behaviour need a source.** Tips in `contexts.py` and the stand-ins in `fake-oolite.js` cite the Oolite 1.92.1 source; please do the same.
- **The message format is a contract.** If the add-on's messages change, update `helper/state.py`, the scenarios, the Node tests and the docs in the same pull request.
- Python runtime: 3.11+ with the standard library only (Tkinter comes from the system). Test and dev tools go in the `dev` extra.
- Don't commit game logs, saves, extracted AppImage contents, `.venv/` or `*.egg-info/`.
