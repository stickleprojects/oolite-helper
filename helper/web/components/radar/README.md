<!-- Made by `python -m helper.harness --readmes` from component.toml and radar.states.json: edit those and run it again. -->

# radar

Every blip on the scanner, nearest first: its scanner colour (flashing as the scanner does), name and role, distance, what it's doing and its bounty; click a heading to sort

| | |
|---|---|
| **Reads** | `radar` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `radar.css`, `radar.js` |
| **Tests** | `radar.test.js` |

Use it in a widget: `components = ["radar"]`. Try it: `python -m helper.harness radar`.

## Named states

From `radar.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **nothing on the scanner** | *shows nothing* |
| **quiet** | <img src="images/quiet.png" width="560" alt="quiet"> |
| **pirate attacking you** | <img src="images/pirate-attacking-you.png" width="560" alt="pirate attacking you"> |
| **police chasing an offender** | <img src="images/police-chasing-an-offender.png" width="560" alt="police chasing an offender"> |
| **police attacking you** | <img src="images/police-attacking-you.png" width="560" alt="police attacking you"> |
| **thargoid** | <img src="images/thargoid.png" width="560" alt="thargoid"> |
| **missile incoming** | <img src="images/missile-incoming.png" width="560" alt="missile incoming"> |
| **cargo and rocks** | <img src="images/cargo-and-rocks.png" width="560" alt="cargo and rocks"> |
| **many blips** | <img src="images/many-blips.png" width="560" alt="many blips"> |
