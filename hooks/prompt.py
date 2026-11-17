#!/usr/bin/env python3
"""UserPromptSubmit: when a message looks like a new task, remind the agent to record it.

Rules in CLAUDE.md are read once and fade by mid-conversation; a task said in
passing gets lost. This hook fires on every message and adds ~40 tokens only
when the message reads like a request for work.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

EN = r"""\b(add|build|create|make|implement|fix|refactor|rewrite|migrate|deploy|ship|set ?up|
configure|write|update|upgrade|remove|delete|rename|move|integrate|optimi[sz]e|redesign|
investigate|debug|we need|i need|i want|let'?s|please|todo|deadline|by (monday|tuesday|wednesday|
thursday|friday|tomorrow|end of (the )?(day|week)))\b"""
RU = r"""(сделай|сделать|доделай|переделай|добавь|напиши|почини|исправь|поправь|реализуй|
настрой|создай|заведи|разберись|проверь|обнови|перенеси|выкати|задеплой|нужно|надо|давай|
собери|подготовь|оформи|задача|дедлайн|срочно)"""
TASK_RE = re.compile(EN + "|" + RU, re.I | re.X)
SKIP_RE = re.compile(r"\bhq (t|log|p|d) |^/", re.I)


def main():
    d = core.hook_input()
    text = (d.get("prompt") or "").strip()
    if len(text) < 12 or SKIP_RE.search(text) or not TASK_RE.search(text):
        return
    conn = core.connect()
    p = core.project_for(conn, d.get("cwd") or os.getcwd())
    where = f" in project {p['slug']}" if p else ""
    print(f"[Agent HQ] This message may set a new task. If it does, record it before starting{where}: "
          f"MCP tool task_add, or {core.cli_hint()} t add \"<summary>\" (-d YYYY-MM-DD if there is a "
          "deadline). Split work bigger than one step into subtasks. Don't ask permission for this. "
          "If it's a follow-up on current work, just continue.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
