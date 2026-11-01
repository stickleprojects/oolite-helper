"""scripts/run-ci-checks.sh runs every check and lists the failed ones (#149)."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run-ci-checks.sh"
TOOLS = ("python", "ruff", "mypy", "shellcheck", "node")


def fake_tools(tmp_path, failing=()):
    """A venv and a node whose tools only log their name, and exit 1 if listed in failing."""
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    log = tmp_path / "calls.log"
    for tool in TOOLS:
        status = 1 if tool in failing else 0
        script = bin_dir / tool
        script.write_text(f'#!/bin/sh\necho "{tool} $*" >> "{log}"\nexit {status}\n')
        script.chmod(0o755)
    return bin_dir, log


def run(tmp_path, *args, failing=()):
    bin_dir, log = fake_tools(tmp_path, failing)
    env = {**os.environ, "VENV": str(bin_dir.parent), "PATH": f"{bin_dir}:/usr/bin:/bin"}
    result = subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


def test_a_failing_check_is_listed_and_the_rest_still_run(tmp_path):
    result, calls = run(tmp_path, failing=("ruff",))
    assert result.returncode == 1
    assert "FAILED: ruff check ruff format" in result.stdout
    assert any(call.startswith("shellcheck") for call in calls)  # the last check still ran


def test_an_unknown_option_exits_2(tmp_path):
    result, calls = run(tmp_path, "--fast")
    assert result.returncode == 2
    assert "unknown option: --fast" in result.stderr
    assert calls == []


def test_quick_runs_only_pytest_and_ruff(tmp_path):
    result, calls = run(tmp_path, "--quick")
    assert result.returncode == 0
    assert [call.split()[0] for call in calls] == ["python", "ruff", "ruff"]
    assert "-m pytest -q" in calls[0]


def test_only_js_runs_the_node_checks_without_a_venv(tmp_path):
    bin_dir, log = fake_tools(tmp_path)
    (bin_dir / "python").unlink()  # CI's Node jobs have no Python set up
    env = {**os.environ, "VENV": str(bin_dir.parent), "PATH": f"{bin_dir}:/usr/bin:/bin"}
    result = subprocess.run(
        ["bash", str(SCRIPT), "--only", "js"], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0
    assert {call.split()[0] for call in log.read_text().splitlines()} == {"node"}


def test_an_unknown_group_exits_2(tmp_path):
    result, calls = run(tmp_path, "--only", "docs")
    assert result.returncode == 2
    assert "unknown group: docs" in result.stderr
    assert calls == []
