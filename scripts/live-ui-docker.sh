#!/usr/bin/env bash
# Runs the live checks in a container like CI's Live UI job (scripts/live-ui.Dockerfile),
# on the working tree as it is now, so what passes here passes there.
#
# Usage: scripts/live-ui-docker.sh [command...]   (default: scripts/run-live-checks.sh)
#   e.g. scripts/live-ui-docker.sh bash   for a shell in it
set -euo pipefail
cd "$(dirname "$0")/.."

# WebKit's sandbox (bubblewrap) makes user namespaces. Ubuntu 24.04's AppArmor only
# lets the host's own bwrap do that, not one in a container, so as CI does, lift the
# limit while testing (it comes back on reboot, or with =1).
userns=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
if [[ -r $userns && $(<"$userns") != 0 ]]; then
  echo "WebKit's sandbox can't start in a container while $userns is 1. For this test:" >&2
  echo "  sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0" >&2
  echo "and afterwards (or reboot):" >&2
  echo "  sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=1" >&2
  exit 2
fi

docker build -q -f scripts/live-ui.Dockerfile -t oolite-helper-live-ui . >/dev/null
# Docker's default seccomp and AppArmor profiles refuse user namespaces too.
tty=()
[[ -t 0 ]] && tty=(-it)
docker run --rm "${tty[@]}" \
  --security-opt seccomp=unconfined --security-opt apparmor=unconfined \
  oolite-helper-live-ui "$@"
