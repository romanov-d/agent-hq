"""Local dashboard server for Agent HQ. Standard library only.

Binds to 127.0.0.1. Writes require the X-AgentHQ header, which a cross-site page
cannot send without a preflight this server never approves, and the Host header
must be local, which blocks DNS-rebinding tricks.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
from agenthq import core  # noqa: E402

PAGE = os.path.join(core.HERE, "dashboard.html")
PORT = int(os.environ.get("AGENTHQ_PORT", 7788))
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
_cost = {"at": 0.0, "data": None, "busy": False}


def cost_cached(conn):
    """Transcript parsing can take seconds on a long history, so it never blocks a request:
    the first call starts a background job and returns a placeholder, later calls get the
    cached numbers, refreshed in the background every 5 minutes."""
    stale = _cost["data"] is None or time.time() - _cost["at"] > 300
    if stale and not _cost["busy"]:
        _cost["busy"] = True

        def refresh():
            try:
                _cost["data"] = core.agent_cost(core.connect(), 30)
                _cost["at"] = time.time()
            finally:
                _cost["busy"] = False
        threading.Thread(target=refresh, daemon=True).start()
    return _cost["data"] or {"days": 30, "total": 0, "calls": 0, "by_project": {}, "by_day": {},
                             "loading": True}


def do_action(a):
    conn = core.connect()
    act = a.get("action")
    pid = lambda: a.get("project_id") or None
    if act == "task_add":
        return {"id": core.add_task(conn, a["title"], pid(), a.get("parent_id"),
                                    int(a.get("priority", 2)), a.get("due") or None,
                                    a.get("assignee", ""), a.get("body", ""), "me",
                                    a.get("status", "todo"))}
    if act == "task_set":
        fields = {k: v for k, v in a.items() if k in core.TASK_FIELDS}
        return {"task": core.set_task(conn, int(a["id"]), **fields)}
    if act == "log":
        return {"id": core.log(conn, a["text"], a.get("kind", "note"), pid(), a.get("task_id"))}
    if act == "project_set":
        fields = {k: v for k, v in a.items() if k in core.PROJECT_FIELDS}
        core.set_project(conn, int(a["id"]), **fields)
        return {}
    if act == "project_forget":
        core.forget_project(conn, int(a["id"]))
        return {}
    if act == "deal_add":
        return {"id": core.add_deal(conn, a["client"], a.get("amount", 0), a.get("title", ""),
                                    a.get("stage", "lead"), pid(), a.get("currency", "USD"),
                                    a.get("next_action", ""), a.get("next_at") or None)}
    if act == "deal_set":
        fields = {k: v for k, v in a.items() if k in core.DEAL_FIELDS}
        core.set_deal(conn, int(a["id"]), **fields)
        return {}
    if act == "deal_delete":
        core.delete_deal(conn, int(a["id"]))
        return {}
    if act == "pay":
        core.pay(conn, int(a["id"]), float(a["amount"]), a.get("note", ""))
        return {}
    raise ValueError(f"unknown action {act}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' "
                         "'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in LOCAL_HOSTS

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden host"})
        path = self.path.split("?")[0]
        if path == "/api/state":
            conn = core.connect()
            st = core.state(conn)
            st["cost"] = cost_cached(conn)
            return self._send(200, st)
        if path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-AgentHQ") != "1":
            return self._send(403, {"error": "forbidden"})
        if self.path != "/api/action":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                return self._send(413, {"error": "too large"})
            payload = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, dict({"ok": True}, **do_action(payload)))
        except (ValueError, KeyError) as e:
            self._send(400, {"error": str(e)})


def running(port=PORT):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def serve(port=PORT, open_browser=True):
    url = f"http://localhost:{port}"
    if running(port):
        print(f"Agent HQ is already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Agent HQ dashboard: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def ensure_running(port=PORT):
    """Start the dashboard in a detached process if it is not up. Returns a message with the URL."""
    url = f"http://localhost:{port}"
    if running(port):
        return f"Dashboard is running at {url}"
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return f"Port {port} is taken by another program. Set AGENTHQ_PORT and try again."
    cli = os.path.join(os.path.dirname(core.HERE), "bin", "agent-hq")
    subprocess.Popen([sys.executable, cli, "ui", "--no-open", "--port", str(port)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(30):
        if running(port):
            return f"Dashboard started at {url}"
        time.sleep(0.1)
    return f"Dashboard is starting at {url}"


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else PORT)
