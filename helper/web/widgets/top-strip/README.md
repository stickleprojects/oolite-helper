<!-- Made by `python -m helper.harness --readmes` from widget.toml and its components' states: edit those and run it again. -->

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

Its components' named states, from their `.states.json` files. *Shows nothing* means none of its components draws anything then, so the widget hides.

| State | Picture |
|---|---|
| **clearance: away from stations** | *shows nothing* |
| **clearance: none** | <img src="images/clearance-none.png" width="700" alt="clearance: none"> |
| **clearance: requested** | <img src="images/clearance-requested.png" width="700" alt="clearance: requested"> |
| **clearance: granted** | <img src="images/clearance-granted.png" width="700" alt="clearance: granted"> |
| **clearance: expiring** | <img src="images/clearance-expiring.png" width="700" alt="clearance: expiring"> |
| **clearance: refused** | <img src="images/clearance-refused.png" width="700" alt="clearance: refused"> |
| **drive: docked** | *shows nothing* |
| **drive: both ready** | <img src="images/drive-both-ready.png" width="700" alt="drive: both ready"> |
| **drive: mass locked** | <img src="images/drive-mass-locked.png" width="700" alt="drive: mass locked"> |
| **drive: jump blocked** | <img src="images/drive-jump-blocked.png" width="700" alt="drive: jump blocked"> |
| **drive: torus only** | <img src="images/drive-torus-only.png" width="700" alt="drive: torus only"> |
