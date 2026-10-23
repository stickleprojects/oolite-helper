<!-- Made by `python -m helper.harness --readmes` from component.toml and status.states.json: edit those and run it again. -->

# status

The helper's status line: errors, warnings and notices (nothing when all is well)

| | |
|---|---|
| **Reads** | `status` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `status.css`, `status.js` |
| **Tests** | `status.test.js` |

Use it in a widget: `components = ["status"]`. Try it: `python -m helper.harness status`.

## Named states

From `status.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **all well** | *shows nothing* |
| **a message only** | *shows nothing* |
| **notice** | <img src="images/notice.png" width="700" alt="notice"> |
| **warning** | <img src="images/warning.png" width="700" alt="warning"> |
| **error** | <img src="images/error.png" width="700" alt="error"> |
