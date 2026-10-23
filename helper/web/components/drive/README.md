<!-- Made by `python -m helper.harness --readmes` from component.toml and drive.states.json: edit those and run it again. -->

# drive

TORUS ✓/✗ and JUMP ✓/✗ while flying

| | |
|---|---|
| **Reads** | `drive` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `drive.css`, `drive.js` |
| **Tests** | `drive.test.js` |

Use it in a widget: `components = ["drive"]`. Try it: `python -m helper.harness drive`.

## Named states

From `drive.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **docked** | *shows nothing* |
| **both ready** | <img src="images/both-ready.png" width="640" alt="both ready"> |
| **mass locked** | <img src="images/mass-locked.png" width="640" alt="mass locked"> |
| **jump blocked** | <img src="images/jump-blocked.png" width="640" alt="jump blocked"> |
| **torus only** | <img src="images/torus-only.png" width="640" alt="torus only"> |
