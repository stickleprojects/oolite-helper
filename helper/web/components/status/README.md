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

<table>
<tr><td valign="top"><b>all well</b><br><i>shows nothing</i></td></tr>
<tr><td valign="top"><b>a message only</b><br><i>shows nothing</i></td></tr>
<tr><td valign="top"><b>notice</b><br><img src="images/notice.png" width="900" alt="notice"></td></tr>
<tr><td valign="top"><b>warning</b><br><img src="images/warning.png" width="900" alt="warning"></td></tr>
<tr><td valign="top"><b>error</b><br><img src="images/error.png" width="900" alt="error"></td></tr>
</table>
