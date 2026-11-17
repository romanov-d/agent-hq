"""Tests for Agent HQ. Standard library only: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, ROOT)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AGENTHQ_DB"] = os.path.join(self.tmp.name, "agent-hq.db")
        os.environ["AGENTHQ_TRANSCRIPTS"] = os.path.join(self.tmp.name, "tr", "*.jsonl")
        from agenthq import core
        self.core = core
        self.conn = core.connect()
        self.repo = os.path.join(self.tmp.name, "code", "shop")
        os.makedirs(os.path.join(self.repo, ".git"))
        with open(os.path.join(self.repo, "package.json"), "w") as f:
            json.dump({"description": "A flower shop", "dependencies": {"next": "15", "react": "19"}}, f)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def run_py(self, script, payload, env=None):
        e = dict(os.environ, **(env or {}))
        return subprocess.run([sys.executable, os.path.join(ROOT, script)], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=20, env=e)


class Core(Base):
    def test_auto_register_from_subfolder(self):
        sub = os.path.join(self.repo, "src", "app")
        os.makedirs(sub)
        p = self.core.ensure_project(self.conn, sub)
        self.assertEqual(p["path"], os.path.realpath(self.repo))
        self.assertEqual(p["section"], "site")
        self.assertEqual(p["summary"], "A flower shop")
        self.assertEqual(self.core.ensure_project(self.conn, sub)["id"], p["id"])

    def test_forgotten_folder_is_not_readded(self):
        p = self.core.ensure_project(self.conn, self.repo)
        self.core.forget_project(self.conn, p["id"])
        self.assertIsNone(self.core.ensure_project(self.conn, self.repo))

    def test_home_is_never_a_project(self):
        self.assertIsNone(self.core.project_root(os.path.expanduser("~")))

    def test_subtask_inherits_project_and_status_dates(self):
        p = self.core.register(self.conn, self.repo)
        parent = self.core.add_task(self.conn, "Checkout", p["id"])
        child = self.core.add_task(self.conn, "Cart", parent_id=parent)
        self.assertEqual(self.core.get_task(self.conn, child)["project_id"], p["id"])
        t = self.core.set_task(self.conn, child, status="doing")
        self.assertIsNotNone(t["started_at"])
        t = self.core.set_task(self.conn, child, status="done")
        self.assertIsNotNone(t["done_at"])
        t = self.core.set_task(self.conn, child, status="todo")
        self.assertIsNone(t["done_at"])

    def test_bad_input_is_rejected(self):
        with self.assertRaises(ValueError):
            self.core.add_task(self.conn, "  ")
        with self.assertRaises(ValueError):
            self.core.add_task(self.conn, "x", due="tomorrow")
        tid = self.core.add_task(self.conn, "x")
        with self.assertRaises(ValueError):
            self.core.set_task(self.conn, tid, status="finished")
        with self.assertRaises(ValueError):
            self.core.set_task(self.conn, tid, **{"title; DROP TABLE tasks": "x"})

    def test_result_entry_becomes_where_we_left_off(self):
        p = self.core.register(self.conn, self.repo)
        self.core.log(self.conn, "Checkout works on staging", "result", p["id"])
        brief = self.core.briefing(self.conn, self.core.resolve_project(self.conn, p["slug"]))
        self.assertIn("Where we left off: Checkout works on staging", brief)

    def test_deal_paid_when_fully_paid(self):
        did = self.core.add_deal(self.conn, "Acme", 1000, stage="invoiced")
        self.core.pay(self.conn, did, 400)
        self.assertEqual(self.conn.execute("SELECT stage FROM deals").fetchone()[0], "invoiced")
        self.core.pay(self.conn, did, 600)
        self.assertEqual(self.conn.execute("SELECT stage FROM deals").fetchone()[0], "paid")

    def test_agent_cost_attributed_by_cwd(self):
        p = self.core.register(self.conn, self.repo)
        os.makedirs(os.path.join(self.tmp.name, "tr"))
        from datetime import datetime
        line = {"timestamp": datetime.now().strftime("%Y-%m-%dT10:00:00Z"),
                "cwd": os.path.join(os.path.realpath(self.repo), "src"),
                "message": {"id": "m1", "model": "claude-sonnet-5-5",
                            "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}}
        with open(os.path.join(self.tmp.name, "tr", "a.jsonl"), "w") as f:
            f.write(json.dumps(line) + "\n" + json.dumps(line) + "\n")   # duplicate id counted once
        c = self.core.agent_cost(self.conn)
        self.assertEqual(c["calls"], 1)
        self.assertEqual(c["by_project"][str(p["id"])], c["total"])


class Hooks(Base):
    def test_session_start_registers_and_briefs(self):
        r = self.run_py("hooks/session_start.py", {"cwd": self.repo, "session_id": "s1"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("Agent HQ was just installed", r.stdout)
        self.assertIn("Project: shop", r.stdout)
        r = self.run_py("hooks/session_start.py", {"cwd": self.repo, "session_id": "s2"})
        self.assertNotIn("just installed", r.stdout)

    def test_prompt_hook_fires_only_on_tasks(self):
        r = self.run_py("hooks/prompt.py", {"cwd": self.repo, "prompt": "Please add dark mode to settings"})
        self.assertIn("record it before starting", r.stdout)
        r = self.run_py("hooks/prompt.py", {"cwd": self.repo, "prompt": "what does this regex match?"})
        self.assertEqual(r.stdout, "")

    def test_stop_blocks_silent_work_then_allows(self):
        tr = os.path.join(self.tmp.name, "t.jsonl")
        with open(tr, "w") as f:
            f.write('{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit"}]}}\n')
        self.run_py("hooks/session_start.py", {"cwd": self.repo, "session_id": "s1"})
        payload = {"cwd": self.repo, "session_id": "s1", "transcript_path": tr}
        r = self.run_py("hooks/stop.py", payload)
        self.assertEqual(r.returncode, 2)
        self.assertIn("nothing was recorded", r.stderr)
        self.assertEqual(self.run_py("hooks/stop.py", dict(payload, stop_hook_active=True)).returncode, 0)
        p = self.core.project_for(self.conn, self.repo)
        self.core.log(self.conn, "did things", "result", p["id"])
        self.assertEqual(self.run_py("hooks/stop.py", payload).returncode, 0)

    def test_hooks_survive_garbage_input(self):
        for h in ("hooks/session_start.py", "hooks/prompt.py", "hooks/stop.py", "hooks/session_end.py"):
            r = subprocess.run([sys.executable, os.path.join(ROOT, h)], input="not json",
                               capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, h)


class Mcp(Base):
    def call(self, *msgs):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "agenthq/mcp_server.py")],
                           input="\n".join(json.dumps(m) for m in msgs), capture_output=True,
                           text=True, timeout=20, cwd=self.repo)
        return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]

    def test_handshake_and_task_flow(self):
        out = self.call(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "task_add", "arguments": {"title": "Add search"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "task_update", "arguments": {"id": 1, "status": "done"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "task_update", "arguments": {"id": 1, "status": "nope"}}},
            {"jsonrpc": "2.0", "id": 6, "method": "nope"})
        self.assertEqual([m["id"] for m in out], [1, 2, 3, 4, 5, 6])
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "agent-hq")
        names = {t["name"] for t in out[1]["result"]["tools"]}
        self.assertTrue({"briefing", "task_add", "log", "import_projects"} <= names)
        self.assertIn("in shop", out[2]["result"]["content"][0]["text"])
        self.assertIn("[done]", out[3]["result"]["content"][0]["text"])
        self.assertTrue(out[4]["result"]["isError"])
        self.assertEqual(out[5]["error"]["code"], -32601)


class Server(Base):
    def test_actions_validate(self):
        from agenthq import server
        p = self.core.register(self.conn, self.repo)
        tid = server.do_action({"action": "task_add", "title": "x", "project_id": p["id"]})["id"]
        t = server.do_action({"action": "task_set", "id": tid, "priority": "0", "project_id": ""})["task"]
        self.assertEqual(t["priority"], 0)
        self.assertIsNone(t["project_id"])
        with self.assertRaises(ValueError):
            server.do_action({"action": "rm -rf"})


if __name__ == "__main__":
    unittest.main()
