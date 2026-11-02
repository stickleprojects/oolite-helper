# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Workflow

`main` is protected for everyone, the maintainer included. Every change goes in through a pull request, and the CI checks must pass.

1. Fork the repo, or branch if you have access, from an up-to-date `main`. Use names like `fix/…`, `feat/…`, `docs/…` or `chore/…`.
2. Make your change, with tests (see below).
3. Run the checks locally (next section).
4. Open a pull request against `main`. Say what changed and how you tested it, and reference the issue with `Closes #N`.

## Running the checks locally

One script runs the same checks CI runs (`.github/workflows/ci.yml`): pytest, ruff, mypy, the JavaScript syntax check, the add-on and web tests, and shellcheck. Set up the venv once, then run it:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" ruff==0.17.1

scripts/run-ci-checks.sh           # everything CI runs (about 40 s)
scripts/run-ci-checks.sh --quick   # only pytest and ruff
scripts/run-ci-checks.sh --live    # also the two live tests below (need a display)
```

You need Python 3.11+ and Node 20+. Every check runs even if one fails, and the failed ones are listed at the end. CI's jobs run the same script, one group each (`--only python`, `lint`, `js`, `shell` or `live`). It uses one Python and one Node; CI also tries Python 3.11 to 3.13 and Node 20 and 22. Fix formatting with `.venv/bin/ruff format .`.

Without `--live`, none of these need Oolite or a display.

The plugin web host (#59) also has a live test that needs a display, GTK 3, WebKit2 4.1 (`gir1.2-webkit2-4.1`) and `xauth`. It checks the WebKit sandbox, so run it after WebKit upgrades:

```bash
OOLITE_HELPER_LIVE_WEBHOST=1 .venv/bin/python -m pytest tests/test_webhost_live.py
```

Widgetwindows have a live UI test too (#141). It clicks, drags and scrolls a widgetwindow with `xdotool` and checks that a stand-in game window keeps keyboard focus. By default it runs on a hidden display (needs `xvfb` and `marco`); `=here` uses your own display, so keep off the mouse while it runs (about 30 s):

```bash
OOLITE_HELPER_LIVE_UI=1 .venv/bin/python -m pytest tests/test_frame_live.py
OOLITE_HELPER_LIVE_UI=here .venv/bin/python -m pytest tests/test_frame_live.py
```

It also puts a plugin drawn in one colour in a widgetwindow, finds it in screenshots, and checks it follows the column as it scrolls, is cut off under the title bar, and passes the wheel on when it can't scroll.

CI runs both live tests in its **Live UI** job (not a required check yet), through `scripts/run-live-checks.sh`: a hidden display with no access control, then `run-ci-checks.sh --only live`. The packages it installs are in `scripts/live-ui-packages.txt`. To run it the way CI does, in an Ubuntu 24.04 container:

```bash
scripts/live-ui-docker.sh          # builds the image the first time (about 10 minutes)
scripts/live-ui-docker.sh bash     # a shell in it
```

WebKit's sandbox needs user namespaces, which Ubuntu 24.04's AppArmor only allows for the host's own `bwrap`, not for one in a container. While you run it, set `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` (CI does the same), and set it back to `1` afterwards (a reboot also resets it); the script stops and says so if it's still 1. Not `xvfb-run`: its display only accepts its own cookie and refuses the web host's (#152).

## Testing tools

- **Fake game** (`tests/fakegame.py`, `scenarios/*.yaml`): writes add-on-style log lines on a timeline. Use it to drive `GameState` in tests, or to see the helper without Oolite:
  ```bash
  .venv/bin/python -m tests.fakegame scenarios/docking.yaml --log /tmp/fake.log --speed 2 &
  .venv/bin/oolite-helper --log /tmp/fake.log --stay
  ```
- **Component harness** (`helper/harness.py`): develop a web component or widget in your browser with fake game data.
  ```bash
  .venv/bin/python -m helper.harness                   # everything: http://127.0.0.1:8566/
  .venv/bin/python -m helper.harness clearance         # one component
  .venv/bin/python -m helper.harness clearance+drive   # components together, as a widget
  .venv/bin/python -m helper.harness top-strip         # a widget from your config.toml
  ```
  With one target open you pick where its data starts (a **snapshot**: each scenario is replayed and one kept wherever the context changes, plus a blank one), then a **named state** for each of its components (from `<name>.states.json`, e.g. clearance's "expiring"), and you can edit any topic it reads as JSON. The page reacts within half a second. Files come straight from `helper/web/`, so edit and refresh; clicks work.
- **Pictures**: `--shots DIR` saves an image of each target at every snapshot and in every named state (`--states-only` for just the states), with an `index.html`. Or as tests, one per component state (skipped unless asked; needs Chrome or Chromium):
  ```bash
  .venv/bin/python -m helper.harness clearance --shots /tmp/clearance
  OOLITE_HELPER_SHOTS=/tmp/shots .venv/bin/python -m pytest tests/test_component_images.py
  ```
- **Component READMEs**: each component folder has a generated `README.md` (what `component.toml` says, and a picture of each named state in `images/`). **CI refreshes them**: on a pull request that touches `helper/web/`, the Component READMEs workflow runs `python -m helper.harness --readmes --since origin/main` (the components you changed, those that need them, or all of them if a shared file such as `lib/base.css` or the theme changed) and commits any change to your branch, so pull before pushing again. It pushes with the `README_PUSH_TOKEN` repo secret (a fine-grained token for this repo, Contents: read and write), so CI runs on that commit without approval; without the secret it starts CI itself, and those runs need approving. You can run it locally to look, but CI's pictures are the ones kept (fonts differ between machines). A test fails if a README misses a state. Widget folders (`helper/web/widgets/<name>/`) get READMEs the same way, with a picture of the widget in each of its own named states (`[states]` in `widget.toml`, each naming a state of each component); they're remade when the widget's folder, one of its components or `helper/widgets.py` changes.
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
