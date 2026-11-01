#!/usr/bin/env bash
# PreToolUse (Edit|Write|MultiEdit|NotebookEdit): while .claude/tests-locked exists, block
# edits to tests, so a bug fix makes its committed failing test pass instead of changing it.
# Lock with `touch .claude/tests-locked`, unlock with `rm .claude/tests-locked` (gitignored).
# Exit 2 blocks the edit and shows stderr to Claude.
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
[[ -f "$root/.claude/tests-locked" ]] || exit 0

path="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
[[ -z "$path" ]] && exit 0
rel="${path#"$root"/}"

case "$rel" in
  tests/* | *.test.js | test_*.py | */test_*.py)
    echo "Blocked edit to $rel: tests are locked for this bug fix (.claude/tests-locked). Fix the code so the committed test passes; ask Kieron if the test itself is wrong." >&2
    exit 2
    ;;
esac
exit 0
