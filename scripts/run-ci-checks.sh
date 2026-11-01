#!/usr/bin/env bash
# Run the checks CI runs (.github/workflows/ci.yml) on this machine, with the project venv.
# Keep it in step with ci.yml. Locally it uses one Python and one Node, not CI's matrix.
#
# Usage: scripts/run-ci-checks.sh [--quick] [--live]
#   --quick  only pytest and ruff
#   --live   also the live web host and widgetwindow tests (need a display; the UI one uses xvfb)
#
# Every check runs even after one fails; the failed ones are listed at the end.
# Exit: 0 all passed, 1 a check failed, 2 a bad option or no venv.
# Env: VENV, the venv to use (default .venv).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

quick=0 live=0
for arg in "$@"; do
  case "$arg" in
    --quick) quick=1 ;;
    --live) live=1 ;;
    -h | --help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
  esac
done

bin="${VENV:-.venv}/bin"
if [[ ! -x "$bin/python" ]]; then
  echo "no venv at ${VENV:-.venv}: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 2
fi

failed=()
check() {  # <name> <command...>
  echo "== $1"
  "${@:2}" || failed+=("$1")
}

js_syntax() {
  local f ok=0
  for f in oxp/CtxKeys.oxp/Config/script.js helper/web/lib/*.js helper/web/components/*/*.js \
    helper/web/widgets/*/*.js; do
    node --check "$f" || ok=1
  done
  return "$ok"
}

((quick)) || check "Tkinter" "$bin/python" -c "import tkinter, helper.app"
check "pytest" "$bin/python" -m pytest -q
check "ruff check" "$bin/ruff" check .
check "ruff format" "$bin/ruff" format --check .
if ((!quick)); then
  check "mypy" "$bin/mypy" helper/plist.py helper/settings.py helper/screen.py helper/sources.py
  check "JS syntax" js_syntax
  check "add-on tests" node --test tests/oxp/script.test.js
  check "web tests" node --test helper/web/lib/*.test.js helper/web/components/*/*.test.js \
    helper/web/widgets/*/*.test.js
  check "shellcheck" "$bin/shellcheck" scripts/*.sh .claude/hooks/*.sh
fi
if ((live)); then
  check "live web host" env OOLITE_HELPER_LIVE_WEBHOST=1 "$bin/python" -m pytest -q tests/test_webhost_live.py
  check "live UI" env OOLITE_HELPER_LIVE_UI=1 "$bin/python" -m pytest -q tests/test_frame_live.py
fi

echo
if ((${#failed[@]})); then
  echo "FAILED: ${failed[*]}"
  exit 1
fi
echo "all checks passed"
