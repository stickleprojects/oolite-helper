"""Write scenario-driven Oolite messages to a helper-readable log."""

import argparse
import json
import math
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path


def load_scenario(path):
    """Read a JSON-compatible YAML scenario without adding a runtime dependency."""
    with open(path, encoding="utf-8") as scenario_file:
        steps = json.load(scenario_file)
    if not isinstance(steps, list):
        raise ValueError("scenario must be a list of steps")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or "after" not in step:
            raise ValueError(f"step {index + 1} must be an object with an 'after' value")
        delay = step["after"]
        if (
            isinstance(delay, bool)
            or not isinstance(delay, (int, float))
            or not math.isfinite(delay)
            or delay < 0
        ):
            raise ValueError(f"step {index + 1} has an invalid 'after' value")
        if "rotate" in step:
            valid = step["rotate"] is True and set(step) == {"after", "rotate"}
        elif "close" in step:
            valid = step["close"] is True and set(step) == {"after", "close"}
        else:
            valid = set(step) == {"after", "msg"} and isinstance(step["msg"], dict)
        if not valid:
            raise ValueError(f"step {index + 1} must contain a message, rotate, or close")
    return steps


class LogWriter:
    """Write the timestamped lines and file changes the helper expects."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "w", encoding="utf-8")

    def emit(self, message):
        now = datetime.now().astimezone()
        timestamp = now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        self._file.write(f"{timestamp} [ctxkeys]: {payload}\n")
        self._file.flush()

    def rotate(self):
        self._file.close()
        fd, temp_path = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        os.close(fd)
        try:
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        self._file = open(self.path, "a", encoding="utf-8")

    def close(self):
        now = datetime.now().astimezone()
        self._file.write(f"Closing log at {now.strftime('%Y-%m-%d %H:%M:%S %z')}.\n")
        self._file.flush()
        self.stop()

    def stop(self):
        if not self._file.closed:
            self._file.close()


def run_scenario(steps, log_path, speed=1):
    if (
        isinstance(speed, bool)
        or not isinstance(speed, (int, float))
        or not math.isfinite(speed)
        or speed <= 0
    ):
        raise ValueError("speed must be a positive number")
    writer = LogWriter(log_path)
    try:
        for step in steps:
            delay = step["after"] / speed
            if delay:
                time.sleep(delay)
            if "rotate" in step:
                writer.rotate()
            elif "close" in step:
                writer.close()
                return
            else:
                writer.emit(step["msg"])
    finally:
        writer.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--log", type=Path, required=True, help="path to the helper log")
    parser.add_argument(
        "--speed", type=float, default=1, help="timeline speed multiplier (default: 1)"
    )
    args = parser.parse_args()
    try:
        run_scenario(load_scenario(args.scenario), args.log, args.speed)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
