"""Open one plugin folder in a web view, for developing plugins and checking the host.

    .venv/bin/python -m helper.webhost tests/fixtures/plugins/probe --at 100,100

Sends a "clock" topic ({"seconds": n}) every second and prints the host's
events. Ctrl+C closes it.
"""

import argparse
import json
import os
import time

from . import WebHost, WebWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", help="the plugin's folder (its name is the folder's name)")
    parser.add_argument("--entry", default="index.html")
    parser.add_argument("--at", default="100,100", help="X,Y of the window")
    parser.add_argument("--size", default="320x240", help="WxH of the window")
    args = parser.parse_args()
    x, y = (int(n) for n in args.at.split(","))
    w, h = (int(n) for n in args.size.split("x"))
    root = os.path.abspath(args.folder)
    window = WebWindow(os.path.basename(root).lower(), root, args.entry, (x, y, w, h))

    host = WebHost()
    host.sync({"dev": window})
    start = time.monotonic()
    try:
        while True:
            host.publish("dev", "clock", {"seconds": int(time.monotonic() - start)})
            for event in host.poll():
                print(json.dumps(event), flush=True)
                if event.get("ev") == "page" and event["msg"]["type"] == "resize":
                    msg = event["msg"]
                    window = WebWindow(*window.page()[:3], (x, y, msg["width"], msg["height"]))
                    host.sync({"dev": window})
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        host.close()


if __name__ == "__main__":
    main()
