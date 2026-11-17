#!/usr/bin/env python3
"""SessionStart: give the agent the project state instead of letting it re-read the codebase.

On first sight of a folder that looks like a project (git repo, package.json, ...)
the folder is registered automatically, with a summary and recent commits.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402


def main():
    d = core.hook_input()
    cwd = d.get("cwd") or os.getcwd()
    conn = core.connect()
    p = core.ensure_project(conn, cwd, auto=os.environ.get("AGENTHQ_AUTO_REGISTER", "1") != "0")
    conn.execute("INSERT INTO sessions (project_id, session_id, cwd, started_at) VALUES (?,?,?,?)",
                 (p["id"] if p else None, d.get("session_id") or "", cwd, core.now()))
    conn.commit()
    cli = core.cli_hint()
    first = not conn.execute("SELECT 1 FROM meta WHERE key='welcomed'").fetchone()
    out = []
    if first:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('welcomed', ?)", (core.now(),))
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        out.append(
            "[Agent HQ] Agent HQ was just installed. It keeps project memory and tasks across sessions. "
            f"{n} project(s) tracked so far. In your first reply, briefly tell the user Agent HQ is active "
            "and offer to import their other projects with /agent-hq:onboard (it scans common code "
            "folders and registers every repo).")
    if p:
        out.append(core.briefing(conn, p))
        out.append(
            "\n[Agent HQ protocol] Read the state above before exploring code. When the user gives a new "
            f"task, record it first (Agent HQ MCP tool task_add, or {cli} t add \"...\"). Mark it doing when "
            "you start, done when finished. After a meaningful chunk of work write one result entry "
            f"(tool log with kind=result, or {cli} log \"what changed, how to verify, what's next\" "
            "-k result): it becomes 'where we left off' for the next session.")
    if out:
        print("\n".join(out))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # a hook must never break the session
        print(f"[Agent HQ] session hook error: {e}", file=sys.stderr)
    sys.exit(0)
