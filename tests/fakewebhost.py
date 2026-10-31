"""A stand-in for helper/webhost/host.py that speaks the protocol without GTK.

Answers "open" with "loaded" and echoes every command as {"ev": "got", "cmd": ...}
so tests can see what the client sent. FAKE_WEBHOST_PROTOCOL changes the
protocol it claims.
"""

import json
import os
import sys


def emit(event, **fields):
    sys.stdout.write(json.dumps({"ev": event, **fields}) + "\n")
    sys.stdout.flush()


emit("ready", protocol=int(os.environ.get("FAKE_WEBHOST_PROTOCOL", "2")), api=1, webkit="fake")
for line in sys.stdin:
    cmd = json.loads(line)
    emit("got", cmd=cmd)
    if cmd["op"] == "open":
        emit("loaded", id=cmd["id"])
    elif cmd["op"] == "close":
        emit("closed", id=cmd["id"])
    elif cmd["op"] == "quit":
        break
