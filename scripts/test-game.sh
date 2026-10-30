#!/bin/bash
# Set up the test commander: a fresh Test.oolite-save (the game's standard
# start, docked at Lave, with 10,000 Cr and fuel scoops) and the test add-on,
# which gives Test a passenger, a parcel and a cargo contract when docked.
#
#   scripts/test-game.sh           # install (resets the Test save each time)
#   scripts/test-game.sh remove    # take the test add-on out again
#
# Then load the "Test" commander in the game. The add-on does nothing for any
# other commander.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APPIMAGE_PATH="${OOLITE_APPIMAGE:-$HOME/Games/Oolite/oolite-1.92.1-x86_64.AppImage}"
GAME_DATA="${OOLITE_GAMEDATA:-$(dirname "$APPIMAGE_PATH")/GameData}"
ADDON="$GAME_DATA/AddOns/CtxKeysTest.oxp"

if [[ "${1:-}" == "remove" ]]; then
    rm -f "$ADDON"
    echo "test-game: removed the test add-on (the Test save is kept)"
    exit 0
fi

mkdir -p "$GAME_DATA/SavedGames" "$GAME_DATA/AddOns"
cp "$REPO/tests/game/Test.oolite-save" "$GAME_DATA/SavedGames/Test.oolite-save"
ln -sfn "$REPO/tests/game/CtxKeysTest.oxp" "$ADDON"
echo "test-game: installed Test.oolite-save and the test add-on; load commander Test"
