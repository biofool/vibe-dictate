#!/usr/bin/env python3
"""vibe-dictate control client — send a command to the running daemon.

    python3 dictate_ctl.py ptt      # toggle push-to-talk
    python3 dictate_ctl.py live     # toggle live dictation
    python3 dictate_ctl.py stop     # stop current session
    python3 dictate_ctl.py status   # daemon state JSON
    python3 dictate_ctl.py quit     # exit daemon

This is what desktop shortcuts call — the daemon cannot grab global keys
itself on Wayland without root.
"""

import os
import socket
import sys
from pathlib import Path

SOCK = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "vibe-dictate" / "ctl.sock"


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("ptt", "live", "stop", "status", "quit"):
        print(__doc__.strip())
        return 2
    if not SOCK.exists():
        print("daemon not running — start it with: python3 dictate_daemon.py", file=sys.stderr)
        return 1
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(10)
        s.connect(str(SOCK))
        s.sendall(sys.argv[1].encode() + b"\n")
        reply = s.recv(4096)
    if not reply:
        print("daemon closed the connection without a reply", file=sys.stderr)
        return 1
    msg = reply.decode("utf-8", "replace").strip()
    print(msg)
    return 1 if msg.startswith("error:") else 0


if __name__ == "__main__":
    sys.exit(main())
