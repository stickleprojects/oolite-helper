#!/usr/bin/env bash
# The live checks as CI runs them (its Live UI job, and scripts/live-ui-docker.sh):
# on a hidden display with no access control, then run-ci-checks.sh --only live.
# Not xvfb-run: its cookie-only server refuses the xauth call that makes the web
# host's untrusted cookie (#152); a desktop admits it as a local user.
# Env: VENV, as for run-ci-checks.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

display=:99
Xvfb "$display" -screen 0 1280x800x24 -nolisten tcp &
xvfb=$!
trap 'kill "$xvfb"' EXIT
for _ in $(seq 50); do
  [[ -e /tmp/.X11-unix/X${display#:} ]] && break
  sleep 0.1
done
unset XAUTHORITY
DISPLAY=$display scripts/run-ci-checks.sh --only live
