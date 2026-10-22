"""Message sources: where the helper gets the add-on's JSON messages from.

A source has poll(), which returns the messages that arrived since the last
call. LogSource follows Latest.log; a debug-console TCP source can be added
later with the same interface.
"""

import contextlib
import json
import os
import re

from .paths import LOG as DEFAULT_LOG

# e.g. 16:33:52.857 [ctxkeys]: {"version":"0.1","type":"hello"}
LINE_RE = re.compile(r"^\S+ \[ctxkeys\]: (\{.*\})\s*$")
# Oolite's last line on a normal exit, e.g. "Closing log at 2026-10-21 16:31:26 +1100."
CLOSE_PREFIX = "Closing log at "


class LogSource:
    """Follows Latest.log, including when Oolite recreates it at game start.

    On first open (and on each new file) it reads from the beginning, so the
    state is right even if the helper starts after the game.
    """

    def __init__(self, path=DEFAULT_LOG):
        self.path = path
        self._file = None
        self._inode = None
        self._partial = ""

    def poll(self):
        # A new file means a new game run, so start the state again.
        messages = [{"type": "session"}] if self._reopen_if_needed() else []
        if self._file is None:
            return messages
        chunk = self._file.read()
        if not chunk:
            return messages
        lines = (self._partial + chunk).split("\n")
        self._partial = lines.pop()  # incomplete last line, if any
        for line in lines:
            if line.startswith(CLOSE_PREFIX):
                messages.append({"type": "closed"})
                continue
            m = LINE_RE.match(line)
            if m:
                with contextlib.suppress(json.JSONDecodeError):
                    messages.append(json.loads(m.group(1)))
        return messages

    def _reopen_if_needed(self):
        """Open the log if it's new; returns True when a new file was opened."""
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            return False
        replaced = st.st_ino != self._inode
        truncated = self._file is not None and st.st_size < self._file.tell()
        if self._file is None or replaced or truncated:
            if self._file is not None:
                self._file.close()
            self._file = open(self.path, encoding="utf-8", errors="replace")
            self._inode = st.st_ino
            self._partial = ""
            return True
        return False
