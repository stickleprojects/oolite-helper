<!-- Made by `python -m helper.harness --readmes` from component.toml and trade_here.states.json: edit those and run it again. -->

# trade_here

Your hold, prices against the last market, and the best buys; a hint until you dock

| | |
|---|---|
| **Reads** | `market_advice` |
| **Sends** | nothing |
| **Needs** | nothing |
| **Files** | `trade_here.css`, `trade_here.js` |
| **Tests** | `trade_here.test.js` |

Use it in a widget: `components = ["trade_here"]`. Try it: `python -m helper.harness trade_here`.

## Named states

From `trade_here.states.json`. *Shows nothing* means it draws nothing in that state; a widget hides while all its components do.

| State | Picture |
|---|---|
| **not docked yet** | <img src="images/not-docked-yet.png" width="560" alt="not docked yet"> |
| **docked with cargo** | <img src="images/docked-with-cargo.png" width="560" alt="docked with cargo"> |
