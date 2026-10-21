I want to build a context-aware key helper for the space game **Oolite**: a small window on my laptop screen that shows the keyboard shortcuts for whatever I'm doing in the game at that moment. For example, near a station it should show "Shift+L request docking clearance" and the docking computer keys.

**My setup**
- Oolite 1.92.1, run from the AppImage at `~/Games/Oolite/oolite-1.92.1-x86_64.AppImage`
- Linux, MATE desktop, X11. A laptop with Intel integrated graphics.
- The game runs on my primary screen, an ultrawide (DP-2, 3840x1080 at position 0,0). The helper window should go on the laptop screen (eDP-1, 1920x1080 at position 960,1080), which sits centred below it.

**Planned approach (please check it before building)**
1. **An Oolite add-on (OXP)** containing a JavaScript world script that listens for game events and writes a marker line to Oolite's log on each change, e.g. `log("ctxkeys", "CONTEXT: near_station")`. Add-on scripts can't write their own files or use the network, as far as I know, so the log is the only way out. Event handlers I believe exist, which need checking against the 1.92 scripting API:
   - `shipEnteredStationAegis` / `shipExitedStationAegis`
   - `shipDockedWithStation` / `shipWillLaunchFromStation`
   - `alertConditionChanged`
   - `shipExitedWitchspace` / `shipWillEnterWitchspace`
   - `shipTargetAcquired`
   - `guiScreenChanged`

   Ideally it also writes the current state when the game starts or loads.
2. **A Python helper window** that follows `Latest.log` (handling the log being recreated each time the game starts), keeps track of the current context, and shows the matching key list in a large, readable font. Tkinter or GTK is fine. It should open on the laptop screen without stealing focus from the game.

**Things to find out first**
- Where this AppImage keeps its user data: the log file (probably `~/.Oolite/Logs/Latest.log`) and the AddOns folder. Run the game once if they don't exist yet.
- The game's real key settings. Extract the AppImage (`--appimage-extract`, into a scratch folder) and read its `keyconfig*.plist`, then check for any user overrides. The key lists should be built from those files, not typed in from memory.
- That log lines from an add-on actually appear in `Latest.log`. Some log message types may need enabling in a logcontrol setting.

**Contexts to start with**
- Docked (trading, shipyard, launch)
- Flying in normal space
- Near a station (docking clearance, docking computer)
- Red alert / combat
- Hyperspace and galactic jump
- Menu screens (via `guiScreenChanged`)

Build it in small steps: first confirm a log line from the add-on shows up, then the window that follows the log, then the key lists.
