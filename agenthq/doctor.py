"""agent-hq doctor: is the installation actually working? Hooks are silent by nature, so check."""
import json
import os
import subprocess
import sys

from agenthq import core


def run(conn):
    ok = True

    def line(passed, what, hint=""):
        nonlocal ok
        ok = ok and passed is not False
        mark = {True: "ok  ", False: "FAIL", None: "warn"}[passed]
        print(f"[{mark}] {what}" + (f"\n       {hint}" if hint and passed is not True else ""))

    line(sys.version_info >= (3, 8), f"Python {sys.version.split()[0]}", "Python 3.8+ is required")
    line(True, f"Database {core.db_path()}")
    n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    line(True if n else None, f"{n} projects tracked",
         "" if n else "Run /agent-hq:onboard in Claude Code, or `agent-hq scan --add`")

    last = conn.execute("SELECT started_at FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    line(True if last else None,
         f"Hooks fired, last session started {last[0]}" if last else "No sessions recorded yet",
         "" if last else "Start a new Claude Code session with the plugin enabled, then re-run doctor")

    srv = os.path.join(core.HERE, "mcp_server.py")
    try:
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "doctor", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        out = subprocess.run([sys.executable, srv], input="\n".join(json.dumps(m) for m in msgs),
                             capture_output=True, text=True, timeout=10).stdout
        tools = json.loads(out.strip().splitlines()[-1])["result"]["tools"]
        line(True, f"MCP server answers, {len(tools)} tools")
    except Exception as e:
        line(False, "MCP server did not answer", str(e)[:200])

    tr = os.path.expanduser("~/.claude/projects")
    line(True if os.path.isdir(tr) else None, "Claude Code transcripts found (agent cost works)"
         if os.path.isdir(tr) else "No ~/.claude/projects folder: agent cost will be empty")
    print("\nAll good." if ok else "\nSomething is off, see FAIL lines above.")
    return 0 if ok else 1
