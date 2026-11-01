"""The lock-tests hook blocks edits to tests while .claude/tests-locked exists (#145)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "lock-tests.sh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="the hook needs jq")


def run_hook(root, path, locked=True):
    (root / ".claude").mkdir(exist_ok=True)
    if locked:
        (root / ".claude" / "tests-locked").touch()
    event = {"tool_name": "Edit", "tool_input": {"file_path": str(root / path)}}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"},
        check=False,
    )


@pytest.mark.parametrize(
    "path",
    ["tests/test_hold.py", "tests/oxp/script.test.js", "helper/web/components/hold/hold.test.js"],
)
def test_a_test_file_is_blocked_while_locked(tmp_path, path):
    result = run_hook(tmp_path, path)
    assert result.returncode == 2
    assert "tests are locked" in result.stderr


def test_code_can_be_edited_while_locked(tmp_path):
    assert run_hook(tmp_path, "helper/hold.py").returncode == 0


def test_tests_can_be_edited_when_unlocked(tmp_path):
    assert run_hook(tmp_path, "tests/test_hold.py", locked=False).returncode == 0
