#!/usr/bin/env python3
"""Fill a separate database with a fictional studio, for screenshots and trying the dashboard.

    AGENTHQ_DB=/tmp/agent-hq-demo.db python3 demo/seed.py && AGENTHQ_DB=/tmp/agent-hq-demo.db bin/agent-hq ui

All names are made up. It never touches your real database unless you point AGENTHQ_DB at it,
and it refuses to write into a database that already has projects.
"""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

random.seed(4)
conn = core.connect()
if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]:
    sys.exit(f"{core.db_path()} already has projects; point AGENTHQ_DB at an empty file.")


def ts(days_ago, hour=11):
    return (datetime.now() - timedelta(days=days_ago)).replace(hour=hour, minute=random.randint(0, 59)) \
        .strftime("%Y-%m-%d %H:%M:%S")


def d(days):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


P = [  # slug, name, section, status, kind, client, summary
    ("northwind-site", "Northwind Coffee", "site", "active", "client", "Northwind",
     "Marketing site with online menu and pickup orders, Next.js on Vercel"),
    ("ledgerly", "Ledgerly", "app", "active", "own", "",
     "Invoicing for freelancers: recurring invoices, Stripe payouts, client portal"),
    ("fitpulse", "FitPulse", "mobile", "active", "client", "FitPulse Inc",
     "Workout tracker for iOS and Android, Expo + Supabase, App Store review next"),
    ("orbit-bot", "Orbit Support Bot", "bot", "active", "own", "",
     "Telegram support bot that answers from the docs and hands off to a human"),
    ("lantern", "Lantern", "game", "active", "own", "",
     "Co-op cave exploration game in Godot 4, Steam demo planned"),
    ("atlas-api", "Atlas API", "app", "paused", "client", "Atlas Freight",
     "Shipment tracking API and admin, waiting on the client's carrier keys"),
    ("bloom-shop", "Bloom Florist", "site", "done", "client", "Bloom",
     "Shopify theme and same-day delivery zones, launched"),
    ("docs-kit", "docs-kit", "lib", "active", "own", "",
     "Open-source MDX docs starter with search and versioning"),
    ("infra", "Studio infra", "infra", "active", "own", "",
     "Hetzner boxes, backups, uptime checks, deploy scripts"),
    ("weekly-letter", "Weekly letter", "content", "active", "own", "",
     "Newsletter about building with AI agents, 1 issue per week"),
]
ids = {}
for i, (slug, name, sec, st, kind, client, summ) in enumerate(P):
    cur = conn.execute("INSERT INTO projects (slug, name, path, status, section, kind, client, priority,"
                       " summary, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (slug, name, f"/Users/demo/code/{slug}", st, sec, kind, client, i % 3, summ,
                        ts(90), ts(random.randint(0, 9))))
    ids[slug] = cur.lastrowid

T = {
    "northwind-site": [("Pickup order flow with Stripe Checkout", "doing", 1, "claude", 3,
                        ["Cart drawer", "Checkout session API", "Order email", "Admin order list"]),
                       ("Menu CMS: let staff edit prices", "todo", 2, "", 9, []),
                       ("Lighthouse 95+ on mobile", "review", 2, "claude", None, [])],
    "ledgerly": [("Recurring invoices", "done", 1, "claude", None,
                  ["Schedule model", "Cron runner", "Email template"]),
                 ("Client portal: pay and download PDFs", "doing", 1, "claude", 6,
                  ["Magic-link login", "Invoice list", "PDF export"]),
                 ("Stripe Connect payouts", "blocked", 0, "me", -1, []),
                 ("Pricing page and trial limits", "todo", 2, "", 12, [])],
    "fitpulse": [("Submit build 1.0 to App Store review", "todo", 0, "me", 1, []),
                 ("Offline workout log sync", "doing", 1, "claude", 4,
                  ["Local queue", "Conflict rules", "Retry with backoff"]),
                 ("Fix crash on Android 12 when camera denied", "review", 1, "claude", None, [])],
    "orbit-bot": [("Answer from docs with citations", "done", 1, "claude", None, []),
                  ("Human handoff to a Slack channel", "doing", 2, "claude", 8, []),
                  ("Rate limit per chat", "todo", 3, "", None, [])],
    "lantern": [("Rope physics between players", "doing", 1, "claude", 10, ["Verlet rope", "Grab and climb"]),
                ("Steam demo build", "todo", 1, "me", 25, []),
                ("Cave generator v2: chasms and water", "todo", 2, "", None, [])],
    "atlas-api": [("Carrier webhooks", "blocked", 1, "me", -6, [])],
    "docs-kit": [("Versioned docs switcher", "review", 2, "claude", None, []),
                 ("Algolia-free local search", "done", 2, "claude", None, [])],
    "infra": [("Nightly Postgres backups to object storage", "done", 1, "claude", None, []),
              ("Uptime alerts to Telegram", "todo", 2, "", 5, [])],
    "weekly-letter": [("Issue #31: what our agents shipped in a month", "doing", 2, "me", 2, [])],
}
BLOCK = {"Stripe Connect payouts": "Stripe platform approval from the client",
         "Carrier webhooks": "API keys from Atlas Freight"}
for slug, tasks in T.items():
    pid = ids[slug]
    for title, st, pr, who, due, subs in tasks:
        tid = core.add_task(conn, title, pid, priority=pr, assignee=who, due=d(due) if due is not None else None,
                            body="Acceptance: works end to end on staging, covered by a smoke test.",
                            created_by=random.choice(["me", "claude"]), status=st)
        when = ts(random.randint(0, 12), random.randint(9, 20))
        conn.execute("UPDATE tasks SET created_at = ?, blocked_by = ?, done_at = ? WHERE id = ?",
                     (ts(random.randint(8, 30)), BLOCK.get(title, ""), when if st == "done" else None, tid))
        for j, s in enumerate(subs):
            sst = "done" if st == "done" or j < len(subs) // 2 + (1 if st == "doing" else 0) else "todo"
            sid = core.add_task(conn, s, parent_id=tid, assignee="claude", created_by="claude", status=sst)
            if sst == "done":
                conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (ts(random.randint(0, 6)), sid))

for n in range(26):
    tid = core.add_task(conn, random.choice(["Refactor auth middleware", "Fix flaky e2e test", "Update deps",
                                             "Add loading states", "Copy edits on landing", "Image optimisation",
                                             "Error tracking setup", "Accessibility pass"]),
                        random.choice(list(ids.values())), status="done", assignee="claude", created_by="claude")
    conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (ts(random.randint(0, 28)), tid))

E = [("ledgerly", "result", "claude", 0, "Recurring invoices are live on staging: schedule on the invoice, cron runs hourly, "
      "emails go through Postmark. Check: create an invoice with 'monthly' and run `make cron`. Next: client portal."),
     ("northwind-site", "decision", "claude", 1, "Using Stripe Checkout instead of Elements: less PCI scope, the client "
      "does not need a custom payment form. Revisit if they want Apple Pay on the menu page."),
     ("fitpulse", "result", "claude", 1, "Android 12 camera crash fixed: permission denial now shows a fallback screen. "
      "Verified on Pixel 6 emulator. Waiting for a human review before the release build."),
     ("atlas-api", "blocker", "me", 6, "Carrier sandbox keys still not shared by Atlas Freight. Project paused until they arrive."),
     ("lantern", "result", "claude", 2, "Rope prototype: Verlet integration with 24 segments, stable at 60 fps with 4 players. "
      "Grab works, climbing jitters on steep walls - next step."),
     ("infra", "result", "claude", 3, "Nightly pg_dump to object storage with 30-day retention. Restore tested on a scratch box: 4 min."),
     ("orbit-bot", "result", "claude", 4, "Docs answers now cite the page and section. Eval set of 40 questions: 36 correct, 4 partial."),
     ("docs-kit", "decision", "me", 5, "Dropping Algolia: local search index is 180 KB for 400 pages and needs no account.")]
for slug, kind, who, ago, text in E:
    eid = core.log(conn, text, kind, ids[slug], actor=who)
    conn.execute("UPDATE entries SET ts = ? WHERE id = ?", (ts(ago, 17), eid))

for slug in ids:
    for k in range(random.randint(2, 6)):
        st = ts(random.randint(0, 20), random.randint(8, 21))
        end = (datetime.strptime(st, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=random.randint(12, 140))) \
            .strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO sessions (project_id, session_id, cwd, started_at, ended_at) VALUES (?,?,?,?,?)",
                     (ids[slug], f"demo-{slug}-{k}", f"/Users/demo/code/{slug}", st, end))

D = [("Northwind", "Online ordering", 6400, "won", "Send invoice for milestone 2", 1, "northwind-site"),
     ("FitPulse Inc", "App Store launch", 12000, "invoiced", "Follow up on invoice #14", -2, "fitpulse"),
     ("Harbor Dental", "Booking site", 4800, "proposal", "Call to walk through the proposal", 2, None),
     ("Kite Labs", "Internal dashboard", 9000, "talk", "Send scope and two options", 0, None),
     ("Mira Studio", "Portfolio redesign", 3200, "lead", "Reply with questions", 3, None),
     ("Atlas Freight", "Tracking API phase 2", 15000, "talk", "Get carrier keys", -5, "atlas-api"),
     ("Bloom", "Shopify theme", 5600, "paid", "", None, "bloom-shop")]
for client, title, amt, stage, nxt, nd, slug in D:
    did = core.add_deal(conn, client, amt, title, stage, ids.get(slug), "USD", nxt, d(nd) if nd is not None else None)
    if stage == "paid":
        core.pay(conn, did, amt, "Final payment")
    if stage == "invoiced":
        core.pay(conn, did, 6000, "Deposit")
conn.execute("UPDATE payments SET paid_at = ?", (d(-9),))
# Fake transcripts so the agent-cost views have numbers. Use with AGENTHQ_TRANSCRIPTS.
tdir = os.path.splitext(core.db_path())[0] + "-transcripts"
os.makedirs(tdir, exist_ok=True)
weights = {"ledgerly": 5, "northwind-site": 4, "fitpulse": 4, "lantern": 3, "orbit-bot": 2,
           "docs-kit": 1, "infra": 1, "weekly-letter": 0.3}
with open(os.path.join(tdir, "demo.jsonl"), "w") as f:
    n = 0
    for ago in range(30):
        for slug, w in weights.items():
            for _ in range(int(random.random() * w * 6)):
                n += 1
                f.write(core.json.dumps({
                    "timestamp": (datetime.now() - timedelta(days=ago)).strftime("%Y-%m-%dT12:00:00Z"),
                    "cwd": f"/Users/demo/code/{slug}",
                    "message": {"id": f"m{n}", "model": "claude-sonnet-5-5", "usage": {
                        "input_tokens": random.randint(200, 3000), "output_tokens": random.randint(300, 4000),
                        "cache_read_input_tokens": random.randint(20000, 160000),
                        "cache_creation_input_tokens": random.randint(0, 20000)}}}) + "\n")
print(f"Demo transcripts: AGENTHQ_TRANSCRIPTS='{tdir}/*.jsonl'")
for pid in ids.values():
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ts(random.randint(0, 9)), pid))
conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('welcomed', 'demo')")
conn.commit()
print(f"Demo studio written to {core.db_path()}")
