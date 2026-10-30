<!-- Made by `python -m helper.harness --readmes` from component.toml and hold.states.json: edit those and run it again. -->

# hold

Everything aboard: each lot of goods with where it was bought, what you paid and what it's worth at the last market; passengers, parcels and contracts with their time left (red when late); says when the hold is empty

| | |
|---|---|
| **Reads** | `hold` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `hold.css`, `hold.js` |
| **Tests** | `hold.test.js` |

Use it in a widget: `components = ["hold"]`. Try it: `python -m helper.harness hold`.

## Named states

From `hold.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **waiting for the game** | <img src="images/waiting-for-the-game.png" width="560" alt="waiting for the game"> |
| **empty** | <img src="images/empty.png" width="560" alt="empty"> |
| **one lot** | <img src="images/one-lot.png" width="560" alt="one lot"> |
| **two lots of food** | <img src="images/two-lots-of-food.png" width="560" alt="two lots of food"> |
| **scooped** | <img src="images/scooped.png" width="560" alt="scooped"> |
| **passengers and parcels** | <img src="images/passengers-and-parcels.png" width="560" alt="passengers and parcels"> |
| **late passenger** | <img src="images/late-passenger.png" width="560" alt="late passenger"> |
| **contract** | <img src="images/contract.png" width="560" alt="contract"> |
