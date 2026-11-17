#!/usr/bin/env python3
"""SessionEnd: close the session row so Agent HQ can show time spent per project."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

try:
    d = core.hook_input()
    if d.get("session_id"):
        conn = core.connect()
        conn.execute("UPDATE sessions SET ended_at = ? WHERE session_id = ? AND ended_at IS NULL",
                     (core.now(), d["session_id"]))
        conn.commit()
except Exception:
    pass
sys.exit(0)
