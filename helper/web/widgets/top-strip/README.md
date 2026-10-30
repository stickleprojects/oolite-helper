<!-- Made by `python -m helper.harness --readmes` from widget.toml: edit it and run it again. -->

# top-strip

Docking clearance and the TORUS/JUMP lamps in a strip above the game window

| | |
|---|---|
| **Components** | [`clearance`](../../components/clearance/README.md), [`drive`](../../components/drive/README.md) |
| **Dock** | `game:top` |
| **Width** | the game's width |
| **Height** | what its components need |
| **Layout** | `compact` |

Use it in `config.toml`, changing any setting `[[widgets]]` takes:

```toml
[[widgets]]
widget = "top-strip"
```

Its id is `top-strip` unless you give another. Try it: `python -m helper.harness top-strip`.

## Named states

From `[states]` in `widget.toml`: each names a state of each of its components. *Shows nothing* means none of them draws anything then, so the widget hides.

| State | Picture |
|---|---|
| **docked** | <img src="images/docked.png" width="700" alt="docked"> |
| **just launched** | <img src="images/just-launched.png" width="700" alt="just launched"> |
| **waiting for clearance** | <img src="images/waiting-for-clearance.png" width="700" alt="waiting for clearance"> |
| **cleared to dock** | <img src="images/cleared-to-dock.png" width="700" alt="cleared to dock"> |
| **clearance running out** | <img src="images/clearance-running-out.png" width="700" alt="clearance running out"> |
| **refused clearance** | <img src="images/refused-clearance.png" width="700" alt="refused clearance"> |
| **in open space** | <img src="images/in-open-space.png" width="700" alt="in open space"> |
| **too near a planet to jump** | <img src="images/too-near-a-planet-to-jump.png" width="700" alt="too near a planet to jump"> |
