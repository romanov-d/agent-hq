#!/usr/bin/env python3
"""Stop: a session that did real work cannot end without a journal entry.

1. Read the transcript: any file edit, or 10+ shell commands, counts as work.
2. Check the database: did this session add an entry or a task?
3. Work but no record -> exit code 2. Claude Code shows stderr to the model and
   keeps the session going until it writes one.

Loop guard: when Claude Code re-runs the hook after a block (stop_hook_active)
we let it stop. Set AGENTHQ_STOP=off to disable, AGENTHQ_STOP=remind to only print a note.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

EDIT = ('"name":"Edit"', '"name":"Write"', '"name":"MultiEdit"', '"name":"NotebookEdit"',
        '"name": "Edit"', '"name": "Write"', '"name": "MultiEdit"', '"name": "NotebookEdit"')
BASH = ('"name":"Bash"', '"name": "Bash"')
MAX_READ = 12 * 1024 * 1024


def worked(path):
    if not path or not os.path.exists(path):
        return False
    try:
        size = os.path.getsize(path)
        with open(path, encoding="utf-8", errors="ignore") as f:
            if size > MAX_READ:
                f.seek(size - MAX_READ)
            raw = f.read()
    except OSError:
        return False
    return any(t in raw for t in EDIT) or sum(raw.count(t) for t in BASH) >= 10


def main():
    mode = os.environ.get("AGENTHQ_STOP", "block")
    d = core.hook_input()
    if mode == "off" or d.get("stop_hook_active") or not worked(d.get("transcript_path")):
        return 0
    conn = core.connect()
    p = core.project_for(conn, d.get("cwd") or os.getcwd())
    if not p:
        return 0                       # untracked folder: not our business
    row = conn.execute("SELECT started_at FROM sessions WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                       (d.get("session_id") or "",)).fetchone()
    since = row["started_at"] if row and row["started_at"] else \
        (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    n = conn.execute("SELECT COUNT(*) FROM entries WHERE ts >= ?", (since,)).fetchone()[0]
    n += conn.execute("SELECT COUNT(*) FROM tasks WHERE created_at >= ? OR done_at >= ?",
                      (since, since)).fetchone()[0]
    if n:
        return 0
    msg = (f"[Agent HQ] Work was done in {p['slug']} but nothing was recorded. Before stopping, write one "
           f"result entry: MCP tool log (kind=result), or {core.cli_hint()} log \"what changed, how to "
           "verify it, what's next\" -k result. Close finished tasks too.")
    if mode == "remind":
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 2


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
