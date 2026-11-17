#!/usr/bin/env python3
"""Agent HQ MCP server (stdio, JSON-RPC 2.0, standard library only).

Exposes projects, tasks, the journal and deals as tools, so the agent works with
Agent HQ directly instead of shelling out. Works in Claude Code, Claude Desktop and any
other MCP client.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

SERVER = {"name": "agent-hq", "version": "0.1.0"}
ACTOR = os.environ.get("AGENTHQ_ACTOR", "claude")


def cwd():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def S(t, desc, **extra):
    return dict({"type": t, "description": desc}, **extra)


PROJECT = S("string", "Project slug or id. Omit to use the project of the current folder.")

TOOLS = [
    {"name": "briefing",
     "description": "State of a project: where we left off, open tasks, recent journal. "
                    "Call this before exploring code in a session.",
     "inputSchema": {"type": "object", "properties": {"project": PROJECT}}},
    {"name": "task_add",
     "description": "Record a task the moment the user asks for work. Split work bigger than "
                    "one step into subtasks with parent_id. Put context and acceptance "
                    "criteria in body.",
     "inputSchema": {"type": "object", "required": ["title"], "properties": {
         "title": S("string", "Short imperative title"),
         "project": PROJECT,
         "parent_id": S("integer", "Parent task id, to create a subtask"),
         "priority": S("integer", "0 urgent, 1 this week, 2 normal, 3 someday", minimum=0, maximum=3),
         "due": S("string", "Deadline YYYY-MM-DD"),
         "assignee": S("string", "me, claude, or an agent name"),
         "body": S("string", "Where things are, what is known, acceptance criteria")}}},
    {"name": "task_update",
     "description": "Change a task: status (todo, doing, review, blocked, done, drop), fields, "
                    "or append to its body. Use status=doing when starting, done when the "
                    "acceptance criteria are met, blocked with blocked_by when waiting on the user.",
     "inputSchema": {"type": "object", "required": ["id"], "properties": {
         "id": S("integer", "Task id"),
         "status": S("string", "New status", enum=list(core.TASK_STATUSES)),
         "title": S("string", "New title"),
         "body": S("string", "Replace the body"),
         "append_body": S("string", "Append a paragraph to the body"),
         "priority": S("integer", "0..3", minimum=0, maximum=3),
         "due": S("string", "YYYY-MM-DD, empty string to clear"),
         "assignee": S("string", "me, claude, or an agent name"),
         "blocked_by": S("string", "What we are waiting for")}}},
    {"name": "task_list",
     "description": "Open tasks of a project, or of every project with all_projects=true.",
     "inputSchema": {"type": "object", "properties": {
         "project": PROJECT,
         "all_projects": S("boolean", "List across all projects"),
         "include_done": S("boolean", "Include done and dropped tasks")}}},
    {"name": "log",
     "description": "Write to the project journal. kind=result after a finished chunk of work "
                    "(what changed, how to verify, what's next) - it becomes 'where we left off'. "
                    "kind=decision for choices and their reasons, kind=blocker for what stops work.",
     "inputSchema": {"type": "object", "required": ["text"], "properties": {
         "text": S("string", "Plain text, enough for a teammate to continue without reading code"),
         "kind": S("string", "Entry kind", enum=list(core.ENTRY_KINDS)),
         "project": PROJECT,
         "task_id": S("integer", "Related task id")}}},
    {"name": "project_list",
     "description": "Projects tracked in Agent HQ with status, section and open task counts.",
     "inputSchema": {"type": "object", "properties": {
         "include_archived": S("boolean", "Also list done and archived projects")}}},
    {"name": "project_update",
     "description": "Change project fields: status (active, paused, done, archive), section, "
                    "summary, name, client, priority.",
     "inputSchema": {"type": "object", "properties": {
         "project": PROJECT,
         "status": S("string", "Project status", enum=list(core.PROJECT_STATUSES)),
         "section": S("string", "Product type", enum=list(core.SECTIONS)),
         "summary": S("string", "One line shown in lists"),
         "name": S("string", "Display name"),
         "client": S("string", "Client name for client work"),
         "priority": S("integer", "0..3", minimum=0, maximum=3)}}},
    {"name": "import_projects",
     "description": "Find project folders (git repos, package.json, pyproject, Godot...) under "
                    "the given roots. With add=true registers them in Agent HQ. Default roots are the "
                    "usual code folders in the home directory.",
     "inputSchema": {"type": "object", "properties": {
         "roots": S("array", "Folders to scan", items={"type": "string"}),
         "add": S("boolean", "Register what was found"),
         "depth": S("integer", "How deep to look, default 3")}}},
    {"name": "deal_add",
     "description": "Add a client deal to the pipeline.",
     "inputSchema": {"type": "object", "required": ["client"], "properties": {
         "client": S("string", "Client name"),
         "amount": S("number", "Deal size"),
         "currency": S("string", "USD, EUR, RUB..."),
         "title": S("string", "What is sold"),
         "stage": S("string", "Pipeline stage", enum=list(core.DEAL_STAGES)),
         "project": PROJECT,
         "next_action": S("string", "Next step with this client"),
         "next_at": S("string", "When, YYYY-MM-DD")}}},
    {"name": "deal_update",
     "description": "Move a deal or change its next action. Record money with payment.",
     "inputSchema": {"type": "object", "required": ["id"], "properties": {
         "id": S("integer", "Deal id"),
         "stage": S("string", "Pipeline stage", enum=list(core.DEAL_STAGES)),
         "amount": S("number", "Deal size"),
         "next_action": S("string", "Next step"),
         "next_at": S("string", "YYYY-MM-DD"),
         "payment": S("number", "Money received now; marks the deal paid when fully paid")}}},
    {"name": "dashboard",
     "description": "Start the local Agent HQ dashboard (projects, task board, clients, agent cost) "
                    "and return its URL.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "agent_cost",
     "description": "USD spent on Claude models per project, read from local Claude Code "
                    "transcripts.",
     "inputSchema": {"type": "object", "properties": {"days": S("integer", "Period, default 30")}}},
]


def project(conn, ref, required=True):
    p = core.resolve_project(conn, ref) if ref else core.ensure_project(conn, cwd())
    if required and not p:
        raise ValueError("No Agent HQ project for the current folder. Pass project, or register the "
                         "folder with import_projects.")
    return p


def call(name, a):
    conn = core.connect()
    if name == "briefing":
        return core.briefing(conn, project(conn, a.get("project")))
    if name == "task_add":
        p = None if a.get("parent_id") else project(conn, a.get("project"), required=False)
        tid = core.add_task(conn, a["title"], p["id"] if p else None, a.get("parent_id"),
                            a.get("priority", 2), a.get("due") or None, a.get("assignee", ""),
                            a.get("body", ""), ACTOR)
        return f"Task #{tid} created" + (f" in {p['slug']}" if p else "")
    if name == "task_update":
        tid = int(a["id"])
        fields = {k: a[k] for k in ("status", "title", "body", "priority", "due", "assignee",
                                    "blocked_by") if k in a}
        if a.get("append_body"):
            fields["body"] = (core.get_task(conn, tid)["body"] + "\n\n" + a["append_body"]).strip()
        t = core.set_task(conn, tid, **fields)
        if fields.get("status") == "blocked" and t.get("blocked_by"):
            core.log(conn, f"Blocked #{tid} {t['title']}: {t['blocked_by']}", "blocker",
                     t["project_id"], tid, ACTOR)
        return f"Task #{tid} [{t['status']}] {t['title']}"
    if name == "task_list":
        p = None if a.get("all_projects") else project(conn, a.get("project"), required=False)
        sts = core.TASK_STATUSES if a.get("include_done") else core.OPEN_STATUSES
        ts = core.list_tasks(conn, p["id"] if p else None, sts)
        if not ts:
            return "No tasks."
        return "\n".join(f"#{t['id']} [{t['status']}] P{t['priority']} {t['title']}"
                         + (f" (due {t['due']})" if t["due"] else "")
                         + (f" <- #{t['parent_id']}" if t["parent_id"] else "")
                         + ("" if p else f" · {t['project_slug'] or 'inbox'}") for t in ts)
    if name == "log":
        p = None
        if a.get("task_id"):
            p = {"id": core.get_task(conn, a["task_id"])["project_id"]}
        p = p or project(conn, a.get("project"), required=False)
        core.log(conn, a["text"], a.get("kind", "note"), p["id"] if p else None, a.get("task_id"),
                 ACTOR, os.environ.get("CLAUDE_SESSION_ID", ""))
        return f"Logged ({a.get('kind', 'note')})"
    if name == "project_list":
        q = "SELECT p.*, (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status IN" \
            " ('todo','doing','review','blocked')) AS open FROM projects p"
        if not a.get("include_archived"):
            q += " WHERE p.status IN ('active','paused')"
        rs = core.rows(conn, q + " ORDER BY p.section, p.slug")
        return "\n".join(f"{r['slug']} [{r['status']}/{r['section']}] {r['open']} open"
                         + (f" - {r['summary']}" if r["summary"] else "") for r in rs) or "No projects."
    if name == "project_update":
        p = project(conn, a.get("project"))
        fields = {k: a[k] for k in ("status", "section", "summary", "name", "client", "priority")
                  if k in a}
        core.set_project(conn, p["id"], **fields)
        return f"{p['slug']} updated: {', '.join(fields) or 'nothing'}"
    if name == "import_projects":
        roots = a.get("roots") or [os.path.expanduser(d) for d in (
            "~/GitHub", "~/Projects", "~/code", "~/dev", "~/src", "~/repos", "~/work",
            "~/Desktop", "~/Documents")]
        known = {r["path"] for r in conn.execute("SELECT path FROM projects")} | \
                {r["path"] for r in conn.execute("SELECT path FROM ignored")}
        found = [d for d in core.scan(roots, int(a.get("depth") or 3)) if d not in known]
        if not a.get("add"):
            return (f"{len(found)} new project folders:\n" +
                    "\n".join(f"  {core.detect_section(d):<8} {d}" for d in found)) if found \
                else "No new project folders found."
        added = [core.register(conn, d) for d in found]
        return f"Registered {len(added)} projects:\n" + "\n".join(
            f"  {p['slug']} [{p['section']}] {p['summary'][:80]}" for p in added)
    if name == "deal_add":
        p = core.resolve_project(conn, a["project"]) if a.get("project") else None
        did = core.add_deal(conn, a["client"], a.get("amount", 0), a.get("title", ""),
                            a.get("stage", "lead"), p["id"] if p else None, a.get("currency", "USD"),
                            a.get("next_action", ""), a.get("next_at"))
        return f"Deal #{did} added"
    if name == "deal_update":
        did = int(a["id"])
        core.set_deal(conn, did, **{k: a[k] for k in ("stage", "amount", "next_action", "next_at")
                                    if k in a})
        if a.get("payment"):
            core.pay(conn, did, a["payment"])
        return f"Deal #{did} updated"
    if name == "agent_cost":
        c = core.agent_cost(conn, int(a.get("days") or 30))
        names = {str(r["id"]): r["slug"] for r in conn.execute("SELECT id, slug FROM projects")}
        lines = [f"${c['total']:,.2f} on {c['calls']:,} model calls in {c['days']} days"]
        lines += [f"  ${v:,.2f} {names.get(k, k)}" for k, v in
                  sorted(c["by_project"].items(), key=lambda x: -x[1])[:15]]
        return "\n".join(lines)
    if name == "dashboard":
        from agenthq import server
        return server.ensure_running()
    raise ValueError(f"unknown tool {name}")


def reply(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req):
    method, mid, params = req.get("method"), req.get("id"), req.get("params") or {}
    if mid is None:                       # notification: nothing to answer
        return
    if method == "initialize":
        reply(mid, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER,
                    "instructions": "Agent HQ keeps project memory and tasks across sessions. "
                                    "Call briefing at the start of work, task_add when the user "
                                    "asks for work, task_update as status changes, and log with "
                                    "kind=result after finishing a chunk of work."})
    elif method == "ping":
        reply(mid, {})
    elif method == "tools/list":
        reply(mid, {"tools": TOOLS})
    elif method == "tools/call":
        try:
            text = call(params.get("name"), params.get("arguments") or {})
            reply(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except (ValueError, KeyError) as e:
            reply(mid, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
        except Exception:
            reply(mid, {"content": [{"type": "text", "text": traceback.format_exc(limit=2)}],
                        "isError": True})
    else:
        reply(mid, error={"code": -32601, "message": f"Method not found: {method}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            reply(None, error={"code": -32700, "message": "Parse error"})
            continue
        for r in (req if isinstance(req, list) else [req]):
            handle(r)


if __name__ == "__main__":
    main()
