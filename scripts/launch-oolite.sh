#!/bin/bash
# Launch the Oolite AppImage with working data folders.
#
# The AppImage's AppRun puts its bundled libsystemd on LD_LIBRARY_PATH, which
# breaks the host's mkdir/mktemp/dirname, so it ends up logging to stdout and
# using /GameData. OO_DIRTYPE=legacy skips that part of AppRun and runs the
# game directly; the oolite binary reads the OO_* paths below itself.

APPIMAGE_PATH="${OOLITE_APPIMAGE:-$HOME/Games/Oolite/oolite-1.92.1-x86_64.AppImage}"
GAME_DATA="${OOLITE_GAMEDATA:-$(dirname "$APPIMAGE_PATH")/GameData}"

export OO_DIRTYPE=legacy
export OO_LOGSDIR="$GAME_DATA/Logs"
export OO_SAVEDIR="$GAME_DATA/SavedGames"
export OO_SNAPSHOTSDIR="$GAME_DATA/Snapshots"
export OO_ADDONSEXTRACTDIR="$GAME_DATA/AddOns"
export OO_MANAGEDADDONSDIR="$GAME_DATA/ManagedAddOns"

mkdir -p "$OO_LOGSDIR" "$OO_SAVEDIR" "$OO_SNAPSHOTSDIR" \
         "$OO_ADDONSEXTRACTDIR" "$OO_MANAGEDADDONSDIR" \
         "$GAME_DATA/Settings" "$GAME_DATA/Library"

# Keep GNUstep's settings and caches in GameData instead of ~/GNUstep.
export GNUSTEP_CONFIG_FILE="$GAME_DATA/GNUstep.conf"
cat > "$GNUSTEP_CONFIG_FILE" <<EOF
GNUSTEP_USER_CONFIG_FILE=$GNUSTEP_CONFIG_FILE
GNUSTEP_USER_DEFAULTS_DIR=$GAME_DATA/Settings
GNUSTEP_USER_DIR_LIBRARY=$GAME_DATA/Library
GNUSTEP_USER_DIR_APPS=$GAME_DATA/Library/Applications
GNUSTEP_USER_DIR_TOOLS=$GAME_DATA/Library/Tools
EOF
# GNUstep ignores a config file that anyone but its owner can write to.
chmod 600 "$GNUSTEP_CONFIG_FILE"

# Start the key helper alongside the game (it closes itself when the game exits).
# Set OOLITE_NO_HELPER=1 to skip it.
HELPER="$(dirname "$(readlink -f "$0")")/../.venv/bin/oolite-helper"
if [[ -z "$OOLITE_NO_HELPER" && -x "$HELPER" ]]; then  # exits if one is already running
    "$HELPER" >/dev/null 2>&1 &
fi

# Not GameData: Oolite also searches a relative "AddOns", which would load add-ons twice.
cd "$(dirname "$APPIMAGE_PATH")" && exec "$APPIMAGE_PATH" "$@"
