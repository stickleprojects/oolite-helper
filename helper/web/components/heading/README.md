<!-- Made by `python -m helper.harness --readmes` from component.toml and heading.states.json: edit those and run it again. -->

# heading

What you're doing (the context), where you are, and the details: countdowns, screen and view, price age

| | |
|---|---|
| **Reads** | `context`, `location`, `details`, `screen`, `market_age` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `heading.css`, `heading.js` |
| **Tests** | `heading.test.js` |

Use it in a widget: `components = ["heading"]`. Try it: `python -m helper.harness heading`.

## Named states

From `heading.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **waiting for game** | <img src="images/waiting-for-game.png" width="560" alt="waiting for game"> |
| **docked** | <img src="images/docked.png" width="560" alt="docked"> |
| **flying, aimed for a target** | <img src="images/flying-aimed-for-a-target.png" width="560" alt="flying, aimed for a target"> |
| **arrived at the target** | <img src="images/arrived-at-the-target.png" width="560" alt="arrived at the target"> |
| **red alert** | <img src="images/red-alert.png" width="560" alt="red alert"> |
