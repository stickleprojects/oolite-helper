<!-- Made by `python -m helper.harness --readmes` from component.toml and clearance.states.json: edit those and run it again. -->

# clearance

Docking clearance near a station; flashes while it's timing out

| | |
|---|---|
| **Reads** | `clearance` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `clearance.css`, `clearance.js` |
| **Tests** | `clearance.test.js` |

Use it in a widget: `components = ["clearance"]`. Try it: `python -m helper.harness clearance`.

## Named states

From `clearance.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **away from stations** | *shows nothing* |
| **none** | <img src="images/none.png" width="640" alt="none"> |
| **requested** | <img src="images/requested.png" width="640" alt="requested"> |
| **granted** | <img src="images/granted.png" width="640" alt="granted"> |
| **expiring** | <img src="images/expiring.png" width="640" alt="expiring"> |
| **refused** | <img src="images/refused.png" width="640" alt="refused"> |
