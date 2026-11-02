#!/usr/bin/env bash
# Run the checks CI runs. CI's jobs call this script too (.github/workflows/ci.yml), one group
# each, so the two can't drift. Locally it uses one Python and one Node, not CI's matrix.
#
# Usage: scripts/run-ci-checks.sh [--quick] [--live] [--only GROUP]...
#   --only   python (Tkinter, pytest), lint (ruff, mypy), js (syntax, add-on and web tests),
#            shell (shellcheck) or live (as --live); repeat for several. Default: the first four.
#   --quick  only pytest and ruff
#   --live   also the live web host and widgetwindow tests (need a display; the UI one uses xvfb)
#
# Every check runs even after one fails; the failed ones are listed at the end.
# Exit: 0 all passed, 1 a check failed, 2 a bad option or no venv.
# Env: VENV, the venv (or Python install) whose bin/ has the tools (default .venv).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

usage_error() {
  echo "$1 (see --help)" >&2
  exit 2
}

quick=0 live=0 groups=()
while (($#)); do
  case "$1" in
    --quick) quick=1 ;;
    --live) live=1 ;;
    --only)
      (($# > 1)) || usage_error "--only needs a group"
      case "$2" in
        python | lint | js | shell | live) groups+=("$2") ;;
        *) usage_error "unknown group: $2 (python, lint, js, shell or live)" ;;
      esac
      shift
      ;;
    -h | --help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) usage_error "unknown option: $1" ;;
  esac
  shift
done
((${#groups[@]})) || groups=(python lint js shell)
wants() { printf '%s\n' "${groups[@]}" | grep -qx "$1"; }
wants live && live=1

bin="${VENV:-.venv}/bin"
if [[ ! -x "$bin/python" ]] && { wants python || wants lint || wants shell || ((live)); }; then
  echo "no venv at ${VENV:-.venv}: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' ruff==0.17.1" >&2
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

if wants python; then
  ((quick)) || check "Tkinter" "$bin/python" -c "import tkinter, helper.app"
  check "pytest" "$bin/python" -m pytest -q
fi
if wants lint; then
  check "ruff check" "$bin/ruff" check .
  check "ruff format" "$bin/ruff" format --check .
  ((quick)) || check "mypy" "$bin/mypy" helper/plist.py helper/settings.py helper/screen.py helper/sources.py
fi
if wants js && ((!quick)); then
  check "JS syntax" js_syntax
  check "add-on tests" node --test tests/oxp/script.test.js
  check "web tests" node --test helper/web/lib/*.test.js helper/web/components/*/*.test.js \
    helper/web/widgets/*/*.test.js
fi
if wants shell && ((!quick)); then
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
