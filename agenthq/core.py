"""Agent HQ core: database access and domain logic.

Shared by the CLI (bin/agent-hq), the MCP server, the hooks and the dashboard server.
Pure Python standard library, so it runs anywhere Claude Code runs.
"""
import glob
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.realpath(__file__))
SCHEMA = os.path.join(HERE, "schema.sql")
SCHEMA_VERSION = "1"

TASK_STATUSES = ("todo", "doing", "review", "blocked", "done", "drop")
OPEN_STATUSES = ("todo", "doing", "review", "blocked")
ENTRY_KINDS = ("note", "result", "decision", "blocker")
PROJECT_STATUSES = ("active", "paused", "done", "archive")
SECTIONS = ("site", "app", "mobile", "bot", "game", "lib", "infra", "content", "other")
DEAL_STAGES = ("lead", "talk", "proposal", "won", "invoiced", "paid", "lost")

# Files that mark a folder as a project worth tracking.
MARKERS = (".git", "package.json", "pyproject.toml", "requirements.txt", "Cargo.toml",
           "go.mod", "project.godot", "pubspec.yaml", "Gemfile", "composer.json",
           "deno.json", "CLAUDE.md", "setup.py", "build.gradle", "Package.swift")


# ---------------------------------------------------------------- basics

def db_path():
    return os.path.expanduser(os.environ.get("AGENTHQ_DB") or "~/.agent-hq/agent-hq.db")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def connect(path=None):
    path = path or db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ver = None
    try:
        ver = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
    except sqlite3.OperationalError:
        pass
    if not ver:
        with open(SCHEMA, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema', ?)",
                     (SCHEMA_VERSION,))
        conn.commit()
    return conn


def rows(conn, sql, *args):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "project"


# ---------------------------------------------------------------- projects

def _norm(path):
    return os.path.realpath(os.path.expanduser(path)).rstrip("/") if path else ""


def project_for(conn, cwd):
    """The deepest tracked project whose folder contains cwd."""
    cwd = _norm(cwd)
    best = None
    for r in conn.execute("SELECT * FROM projects WHERE path IS NOT NULL AND path != ''"):
        p = r["path"].rstrip("/")
        if cwd == p or cwd.startswith(p + "/"):
            if best is None or len(p) > len(best["path"]):
                best = r
    return dict(best) if best else None


def _too_broad(path):
    home = _norm("~")
    broad = {"/", home, *(os.path.join(home, d) for d in
                          ("Desktop", "Documents", "Downloads", "Library", "Projects",
                           "GitHub", "code", "dev", "src", "repos", "work"))}
    return path in broad or not path.startswith("/")


def is_project_dir(path):
    if _too_broad(path):
        return False
    if any(os.path.exists(os.path.join(path, m)) for m in MARKERS):
        return True
    return bool(glob.glob(os.path.join(path, "*.xcodeproj")))


def project_root(cwd):
    """Nearest folder at or above cwd that looks like a project (git root wins)."""
    path = _norm(cwd)
    first = None
    while path and path != "/" and not _too_broad(path):
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        if first is None and is_project_dir(path):
            first = path
        path = os.path.dirname(path)
    return first


def _deps(path):
    deps = {}
    for p in [os.path.join(path, "package.json")] + glob.glob(os.path.join(path, "*/package.json"))[:5]:
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            deps.update(d.get("dependencies") or {})
            deps.update(d.get("devDependencies") or {})
        except Exception:
            pass
    return deps


def detect_section(path):
    """Guess what kind of product lives in the folder, from its files."""
    ex = lambda *n: any(os.path.exists(os.path.join(path, x)) for x in n)
    if ex("project.godot", "ProjectSettings") or glob.glob(os.path.join(path, "*/project.godot")):
        return "game"
    deps = _deps(path)
    if "expo" in deps or "react-native" in deps or ex("pubspec.yaml") or \
            glob.glob(os.path.join(path, "*.xcodeproj")):
        return "mobile"
    if any(k in deps for k in ("telegraf", "grammy", "node-telegram-bot-api", "discord.js")):
        return "bot"
    py = ""
    for f in glob.glob(os.path.join(path, "requirements*.txt")) + \
            glob.glob(os.path.join(path, "pyproject.toml")):
        try:
            py += open(f, encoding="utf-8", errors="ignore").read().lower()
        except Exception:
            pass
    if any(k in py for k in ("aiogram", "python-telegram-bot", "discord.py")):
        return "bot"
    if any(k in deps for k in ("next", "react", "vue", "svelte", "@sveltejs/kit", "nuxt", "astro")):
        return "app" if any(k in deps for k in ("prisma", "@supabase/supabase-js", "drizzle-orm",
                                                 "mongoose", "pg", "express")) else "site"
    if ex("index.html"):
        return "site"
    if ex("Dockerfile", "docker-compose.yml", "terraform", "ansible.cfg"):
        return "infra"
    if ex("setup.py", "Cargo.toml", "go.mod") or "[project]" in py:
        return "lib"
    return "other"


def detect_summary(path):
    """One line about the project: package description or first README sentence."""
    try:
        with open(os.path.join(path, "package.json"), encoding="utf-8") as f:
            d = json.load(f).get("description")
            if d:
                return d.strip()[:160]
    except Exception:
        pass
    for name in ("README.md", "readme.md", "README", "CLAUDE.md"):
        p = os.path.join(path, name)
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith(("#", "!", "[", "<", "```", "|", "---", ">")):
                        continue
                    return re.sub(r"[*_`]", "", s)[:160]
        except Exception:
            pass
    return ""


def git_recent(path, n=5):
    try:
        out = subprocess.run(["git", "-C", path, "log", f"-{n}", "--pretty=%ad %s",
                              "--date=short"], capture_output=True, text=True, timeout=5)
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def register(conn, path, name=None, status="active"):
    """Add a folder as a project. Returns the project dict (existing one if already there)."""
    path = _norm(path)
    have = conn.execute("SELECT * FROM projects WHERE path = ?", (path,)).fetchone()
    if have:
        return dict(have)
    name = name or os.path.basename(path)
    base = slugify(name)
    slug, i = base, 2
    while conn.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone():
        slug, i = f"{base}-{i}", i + 1
    commits = git_recent(path, 3)
    note = ("Imported. Recent commits: " + " | ".join(commits)) if commits else ""
    t = now()
    cur = conn.execute(
        "INSERT INTO projects (slug, name, path, status, section, summary, note, created_at,"
        " updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (slug, name, path, status, detect_section(path), detect_summary(path), note, t, t))
    conn.commit()
    return dict(conn.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone())


def ensure_project(conn, cwd, auto=True):
    """Project for cwd; registers the folder on first sight if it looks like a project."""
    p = project_for(conn, cwd)
    if p or not auto:
        return p
    root = project_root(cwd)
    if not root:
        return None
    if conn.execute("SELECT 1 FROM ignored WHERE path = ?", (root,)).fetchone():
        return None
    return register(conn, root)


def resolve_project(conn, ref):
    if ref is None or ref == "":
        return None
    ref = str(ref)
    r = None
    if ref.isdigit():
        r = conn.execute("SELECT * FROM projects WHERE id = ?", (int(ref),)).fetchone()
    r = r or conn.execute("SELECT * FROM projects WHERE slug = ?", (ref,)).fetchone()
    r = r or conn.execute("SELECT * FROM projects WHERE lower(name) = lower(?)", (ref,)).fetchone()
    if not r:
        raise ValueError(f"unknown project: {ref}")
    return dict(r)


PROJECT_FIELDS = ("name", "status", "section", "kind", "client", "priority", "summary", "note",
                  "parent_id", "path")


def set_project(conn, pid, **fields):
    for k, v in fields.items():
        if k not in PROJECT_FIELDS:
            raise ValueError(f"cannot set project field: {k}")
        if k == "status" and v not in PROJECT_STATUSES:
            raise ValueError(f"status must be one of {PROJECT_STATUSES}")
        if k == "section" and v not in SECTIONS:
            raise ValueError(f"section must be one of {SECTIONS}")
        if k in ("priority", "parent_id") and v not in (None, ""):
            v = int(v)
        if k == "parent_id" and v and int(v) == int(pid):
            raise ValueError("a project cannot be its own parent")
        conn.execute(f"UPDATE projects SET {k} = ?, updated_at = ? WHERE id = ?",
                     (v if v != "" or k not in ("parent_id",) else None, now(), pid))
    conn.commit()


def forget_project(conn, pid):
    """Remove a project from Agent HQ and remember not to auto-add its folder again."""
    p = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if not p:
        raise ValueError("no such project")
    if p["path"]:
        conn.execute("INSERT OR REPLACE INTO ignored (path, at) VALUES (?, ?)", (p["path"], now()))
    conn.execute("UPDATE tasks SET project_id = NULL WHERE project_id = ?", (pid,))
    conn.execute("UPDATE entries SET project_id = NULL WHERE project_id = ?", (pid,))
    conn.execute("UPDATE projects SET parent_id = NULL WHERE parent_id = ?", (pid,))
    conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    conn.commit()


def scan(roots, depth=3):
    """Find project folders under the given roots. Does not touch the database."""
    found = []
    skip = {"node_modules", ".venv", "venv", "dist", "build", ".next", "Library", ".cache",
            "Pods", "target", "vendor", "__pycache__"}
    for root in roots:
        root = _norm(root)
        if not os.path.isdir(root):
            continue
        stack = [(root, 0)]
        while stack:
            d, lvl = stack.pop()
            if lvl > 0 and is_project_dir(d):
                found.append(d)
                continue
            if lvl >= depth:
                continue
            try:
                for e in os.scandir(d):
                    if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") \
                            and e.name not in skip:
                        stack.append((e.path, lvl + 1))
            except (PermissionError, FileNotFoundError):
                pass
    return sorted(set(found))


# ---------------------------------------------------------------- tasks

def add_task(conn, title, project_id=None, parent_id=None, priority=2, due=None,
             assignee="", body="", created_by="me", status="todo"):
    title = (title or "").strip()
    if not title:
        raise ValueError("task title is empty")
    if status not in TASK_STATUSES:
        raise ValueError(f"status must be one of {TASK_STATUSES}")
    if parent_id:
        par = conn.execute("SELECT project_id FROM tasks WHERE id = ?", (parent_id,)).fetchone()
        if not par:
            raise ValueError(f"no parent task #{parent_id}")
        project_id = project_id or par["project_id"]
    if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        raise ValueError("due must be YYYY-MM-DD")
    t = now()
    cur = conn.execute(
        "INSERT INTO tasks (project_id, parent_id, title, body, status, priority, assignee, due,"
        " created_by, created_at, started_at, position) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (project_id, parent_id, title[:500], body or "", status, int(priority), assignee or "",
         due, created_by, t, t if status == "doing" else None,
         datetime.now().timestamp()))
    conn.commit()
    return cur.lastrowid


TASK_FIELDS = ("title", "body", "status", "priority", "assignee", "due", "blocked_by",
               "project_id", "parent_id", "position")


def get_task(conn, tid):
    r = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not r:
        raise ValueError(f"no task #{tid}")
    return dict(r)


def set_task(conn, tid, **fields):
    t = get_task(conn, tid)
    for k, v in fields.items():
        if k not in TASK_FIELDS:
            raise ValueError(f"cannot set task field: {k}")
        if k == "status":
            if v not in TASK_STATUSES:
                raise ValueError(f"status must be one of {TASK_STATUSES}")
            if v == "doing" and not t["started_at"]:
                conn.execute("UPDATE tasks SET started_at = ? WHERE id = ?", (now(), tid))
            done_at = now() if v in ("done", "drop") else None
            conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (done_at, tid))
            if v != "blocked":
                conn.execute("UPDATE tasks SET blocked_by = '' WHERE id = ?", (tid,))
        if k == "due" and v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("due must be YYYY-MM-DD")
        if k in ("priority", "project_id", "parent_id") and v not in (None, ""):
            v = int(v)
        if k == "parent_id" and v == tid:
            raise ValueError("a task cannot be its own parent")
        conn.execute(f"UPDATE tasks SET {k} = ? WHERE id = ?", (v if v != "" or k in (
            "body", "assignee", "blocked_by") else None, tid))
    conn.commit()
    return get_task(conn, tid)


def list_tasks(conn, project_id=None, statuses=OPEN_STATUSES, limit=200):
    q = "SELECT t.*, p.slug AS project_slug, p.name AS project_name FROM tasks t" \
        " LEFT JOIN projects p ON p.id = t.project_id WHERE t.status IN (%s)" % \
        ",".join("?" * len(statuses))
    args = list(statuses)
    if project_id:
        q += " AND t.project_id = ?"
        args.append(project_id)
    q += " ORDER BY CASE t.status WHEN 'doing' THEN 0 WHEN 'review' THEN 1 WHEN 'blocked'" \
         " THEN 2 ELSE 3 END, t.priority, COALESCE(t.due, '9999'), t.id LIMIT ?"
    args.append(limit)
    return rows(conn, q, *args)


# ---------------------------------------------------------------- journal

def log(conn, text, kind="note", project_id=None, task_id=None, actor="me", session_id=""):
    text = (text or "").strip()
    if not text:
        raise ValueError("entry text is empty")
    if kind not in ENTRY_KINDS:
        raise ValueError(f"kind must be one of {ENTRY_KINDS}")
    if task_id and not project_id:
        r = conn.execute("SELECT project_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        project_id = r["project_id"] if r else None
    t = now()
    cur = conn.execute("INSERT INTO entries (ts, project_id, task_id, kind, text, actor, session_id)"
                       " VALUES (?,?,?,?,?,?,?)",
                       (t, project_id, task_id, kind, text, actor, session_id or ""))
    if project_id:
        if kind == "result":
            conn.execute("UPDATE projects SET note = ?, updated_at = ? WHERE id = ?",
                         (text[:800], t, project_id))
        else:
            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (t, project_id))
    conn.commit()
    return cur.lastrowid


def briefing(conn, project, limit_tasks=12, limit_log=4):
    """Plain-text state of a project, written for the agent at session start."""
    p = project
    out = [f"[Agent HQ] Project: {p['name']} ({p['slug']}) - {p['status']}"]
    if p.get("summary"):
        out.append(p["summary"])
    if p.get("note"):
        out.append(f"Where we left off: {p['note']}")
    tasks = list_tasks(conn, p["id"], limit=limit_tasks)
    tasks = [t for t in tasks if not t["parent_id"]] or tasks
    if tasks:
        out.append("\nOpen tasks:")
        for t in tasks:
            mark = {"doing": "->", "review": "??", "blocked": "XX"}.get(t["status"], " -")
            extra = []
            if t["due"]:
                extra.append(f"due {t['due']}")
            if t["assignee"]:
                extra.append(f"@{t['assignee']}")
            if t["blocked_by"]:
                extra.append(f"waiting: {t['blocked_by']}")
            out.append(f"  {mark} #{t['id']} {t['title']}" + (f" ({', '.join(extra)})" if extra else ""))
    else:
        out.append("\nNo open tasks.")
    log_rows = rows(conn, "SELECT ts, kind, actor, text FROM entries WHERE project_id = ?"
                          " ORDER BY id DESC LIMIT ?", p["id"], limit_log)
    if log_rows:
        out.append("\nRecent journal:")
        for e in log_rows:
            out.append(f"  [{e['ts'][:16]}] {e['kind']}/{e['actor']}: {e['text'].splitlines()[0][:220]}")
    return "\n".join(out)


# ---------------------------------------------------------------- deals

def add_deal(conn, client, amount=0, title="", stage="lead", project_id=None, currency="USD",
             next_action="", next_at=None):
    if stage not in DEAL_STAGES:
        raise ValueError(f"stage must be one of {DEAL_STAGES}")
    t = now()
    cur = conn.execute(
        "INSERT INTO deals (client, title, project_id, amount, currency, stage, next_action,"
        " next_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (client.strip(), title, project_id, float(amount or 0), currency, stage, next_action,
         next_at, t, t))
    conn.commit()
    return cur.lastrowid


DEAL_FIELDS = ("client", "title", "project_id", "amount", "currency", "stage", "next_action",
               "next_at")


def set_deal(conn, did, **fields):
    for k, v in fields.items():
        if k not in DEAL_FIELDS:
            raise ValueError(f"cannot set deal field: {k}")
        if k == "stage" and v not in DEAL_STAGES:
            raise ValueError(f"stage must be one of {DEAL_STAGES}")
        if k == "amount":
            v = float(v or 0)
        if k in ("project_id",) and v in ("",):
            v = None
        conn.execute(f"UPDATE deals SET {k} = ?, updated_at = ? WHERE id = ?", (v, now(), did))
    conn.commit()


def pay(conn, deal_id, amount, note="", paid_at=None):
    d = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    if not d:
        raise ValueError(f"no deal #{deal_id}")
    conn.execute("INSERT INTO payments (deal_id, amount, currency, paid_at, note) VALUES (?,?,?,?,?)",
                 (deal_id, float(amount), d["currency"], paid_at or today(), note))
    paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE deal_id = ?",
                        (deal_id,)).fetchone()[0]
    if paid >= d["amount"] > 0:
        conn.execute("UPDATE deals SET stage = 'paid', updated_at = ? WHERE id = ?", (now(), deal_id))
    conn.commit()


# ---------------------------------------------------------------- agent cost

def _prices():
    with open(os.path.join(HERE, "prices.json"), encoding="utf-8") as f:
        return json.load(f)


def agent_cost(conn, days=30, transcripts=None):
    """USD spent on model calls per project, from Claude Code transcripts (~/.claude/projects).

    Each transcript line carries the cwd it ran in, so cost is attributed to the
    tracked project that contains that cwd. Prices live in agenthq/prices.json.
    """
    prices = _prices()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    projects = [(r["path"].rstrip("/"), r["id"]) for r in
                conn.execute("SELECT id, path FROM projects WHERE path IS NOT NULL AND path != ''")]
    projects.sort(key=lambda x: -len(x[0]))
    pattern = transcripts or os.environ.get("AGENTHQ_TRANSCRIPTS") or \
        os.path.expanduser("~/.claude/projects/*/*.jsonl")
    seen, per, per_day, total = set(), {}, {}, 0.0
    for f in glob.glob(pattern):
        try:
            if datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d") < since:
                continue
            fh = open(f, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                ts = (o.get("timestamp") or "")[:10]
                if ts < since:
                    continue
                m = o.get("message") or {}
                u = m.get("usage") or {}
                mid = m.get("id")
                if not u or not mid or mid in seen:
                    continue
                seen.add(mid)
                pin, pout = prices.get(m.get("model", ""), prices.get("default", [0, 0]))
                usd = (u.get("cache_read_input_tokens", 0) * pin * 0.1
                       + u.get("cache_creation_input_tokens", 0) * pin * 1.25
                       + u.get("input_tokens", 0) * pin
                       + u.get("output_tokens", 0) * pout) / 1e6
                total += usd
                per_day[ts] = per_day.get(ts, 0.0) + usd
                cwd = _norm(o.get("cwd") or "")
                for path, pid in projects:
                    if cwd == path or cwd.startswith(path + "/"):
                        per[pid] = per.get(pid, 0.0) + usd
                        break
    return {"days": days, "total": round(total, 2), "calls": len(seen),
            "by_project": {str(k): round(v, 2) for k, v in per.items()},
            "by_day": {k: round(v, 2) for k, v in sorted(per_day.items())}}


# ---------------------------------------------------------------- dashboard state

def state(conn):
    return {
        "today": today(),
        "projects": rows(conn, "SELECT * FROM projects ORDER BY priority, updated_at DESC"),
        "tasks": rows(conn, "SELECT * FROM tasks WHERE status IN ('todo','doing','review','blocked')"
                            " OR done_at >= date('now','-60 day') ORDER BY position, id"),
        "entries": rows(conn, "SELECT * FROM entries ORDER BY id DESC LIMIT 300"),
        "sessions": rows(conn, "SELECT * FROM sessions ORDER BY id DESC LIMIT 200"),
        "deals": rows(conn, "SELECT d.*, COALESCE((SELECT SUM(amount) FROM payments"
                            " WHERE deal_id = d.id), 0) AS paid FROM deals d ORDER BY updated_at DESC"),
        "payments": rows(conn, "SELECT p.*, d.client FROM payments p LEFT JOIN deals d"
                               " ON d.id = p.deal_id ORDER BY paid_at DESC"),
        "enums": {"task": TASK_STATUSES, "project": PROJECT_STATUSES, "section": SECTIONS,
                  "stage": DEAL_STAGES, "kind": ENTRY_KINDS},
    }


# ---------------------------------------------------------------- hook helpers

CLI = os.path.join(os.path.dirname(HERE), "bin", "agent-hq")


def cli_hint():
    """How the agent should call the CLI from Bash: short name if on PATH, full path if not."""
    import shutil
    found = shutil.which("agent-hq")
    return "agent-hq" if found and os.path.realpath(found) == os.path.realpath(CLI) else f'"{CLI}"'


def hook_input():
    import sys
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}
