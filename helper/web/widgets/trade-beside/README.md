<!-- Made by `python -m helper.harness --readmes` from widget.toml: edit it and run it again. -->

# trade-beside

What's in the hold, the last market and the best buys, beside the game window while docked

| | |
|---|---|
| **Components** | [`trade_here`](../../components/trade_here/README.md) |
| **Dock** | `game:right` |
| **Width** | 560 px |
| **Height** | the game's height |
| **Layout** | `compact` |

Use it in `config.toml`, changing any setting `[[widgets]]` takes:

```toml
[[widgets]]
widget = "trade-beside"
```

Its id is `trade-beside` unless you give another. Try it: `python -m helper.harness trade-beside`.

## Named states

From `[states]` in `widget.toml`: each names a state of each of its components. *Shows nothing* means none of them draws anything then, so the widget hides.

| State | Picture |
|---|---|
| **in flight** | <img src="images/in-flight.png" width="560" alt="in flight"> |
| **docked with cargo** | <img src="images/docked-with-cargo.png" width="560" alt="docked with cargo"> |
