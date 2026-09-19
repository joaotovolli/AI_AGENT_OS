"""Loopback dashboard with token authentication and browser-origin checks."""
import hmac
import json
import re
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import config, deploy, projects
from .state import State

STATIC = Path(__file__).parent / "static"


def make_server(root, port=None):
    root = Path(root).resolve()
    settings = config.load(root)
    secret = config.token(root)
    state = State(root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never put authorization or URL tokens in access logs.

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A browser may disconnect during refresh or runtime activation.

        def valid_host(self):
            port_actual = self.server.server_address[1]
            host = self.headers.get("Host", "")
            return host in (f"127.0.0.1:{port_actual}", f"localhost:{port_actual}")

        def authorized(self):
            if not self.valid_host():
                self.respond(403, {"error": "Unrecognized host"})
                return False
            expected = "Bearer " + secret
            if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
                self.respond(401, {"error": "Unlock the dashboard with the local access token"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.valid_host():
                self.respond(403, {"error": "Unrecognized host"})
                return
            if path == "/healthz":
                self.respond(200, {"ok": True})
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in assets:
                name, mime = assets[path]
                self.respond(200, (STATIC / name).read_bytes(), mime)
                return
            if not self.authorized():
                return
            if path == "/api/state":
                data = state.snapshot()
                data.update({"settings": config.load(root), "instance": root.name,
                             "projects": projects.discover(root),
                             "models": config.available_models(), "release": state.get("release", "initial")})
                self.respond(200, data)
            elif path.startswith("/api/history/"):
                goal_id = path.removeprefix("/api/history/")
                if not state.goal(goal_id):
                    self.respond(404, {"error": "Goal not found"})
                else:
                    self.respond(200, state.history(goal_id, 100))
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.authorized():
                return
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_address[1]}", f"http://localhost:{self.server.server_address[1]}"):
                self.respond(403, {"error": "Cross-origin request rejected"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.respond(415, {"error": "Use application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 65536:
                    raise ValueError("Request must be between 1 and 65536 bytes")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                path = urlsplit(self.path).path
                if path == "/api/goals":
                    result = state.add_goal(data.get("title"), data.get("description"), data.get("acceptance"), data.get("commands"))
                    self.respond(201, result)
                elif path == "/api/guidance":
                    if set(data) - {"goal_id", "key", "body", "action"} or data.get("action") not in ("set", "clear"):
                        raise ValueError("Use set or clear with a goal ID, key and guidance text")
                    result = state.set_guidance(data.get("goal_id"), data.get("key"),
                                                data.get("body") if data["action"] == "set" else None)
                    self.respond(200, result)
                elif path == "/api/watchers/cancel":
                    if not state.goal(data.get("goal_id")) or not isinstance(data.get("key"), str):
                        raise ValueError("Select a goal and watcher key")
                    state.cancel_watcher(data["goal_id"], data["key"])
                    self.respond(200, {"ok": True})
                elif path == "/api/settings":
                    # Port changes require reinstalling service links; the dashboard edits execution settings only.
                    allowed = {"model", "reasoning", "fast", "idle_seconds", "step_timeout_seconds",
                               "github_followups", "github_operators", "diagnostic_escalation", "diagnostic_models",
                               "diagnostic_min_attempts", "diagnostic_cooldown_seconds", "diagnostic_timeout_seconds",
                               "external_repeat_limit", "external_wait_min_seconds", "external_wait_max_seconds"}
                    if set(data) - allowed:
                        raise ValueError("These settings must be changed with the installation CLI")
                    was_enabled = config.load(root)["github_followups"]
                    result = config.save(root, data)
                    if result["github_followups"] and not was_enabled:
                        state.set("operator_enabled_since", time.time())
                        state.set("operator_cursor", None)
                    state.set("needs_checkpoint", True)
                    state.set("failures", 0)
                    for goal in state.goals():
                        if goal["status"] == "waiting":
                            state.wake_goal(goal["id"], "Operator requested a fresh attempt")
                    state.event("settings.updated", f"Execution settings saved: {result['model']} / {result['reasoning']} / Fast {result['fast']}")
                    self.respond(200, result)
                elif path == "/api/framework":
                    action = data.get("action")
                    if action not in ("check", "apply"):
                        raise ValueError("Select check or apply")
                    if action == "apply":
                        if not state.get("paused", False) or state.get("active_run"):
                            raise ValueError("Pause the instance and wait for its attempt to stop")
                        if not re.fullmatch(r"[0-9a-f]{40}", data.get("commit", "")):
                            raise ValueError("Select an explicit framework commit")
                    if state.get("framework_request") or state.get("framework", {}).get("status") == "applying":
                        raise ValueError("A framework request is already queued")
                    state.set("framework_request", {"action": action, "commit": data.get("commit")})
                    self.respond(202, {"ok": True})
                elif path == "/api/control":
                    action = data.get("action")
                    if action in ("pause", "resume"):
                        state.set("paused", action == "pause")
                        state.event("operator." + action, "Operator " + action)
                    elif action == "wake":
                        state.set("next_maintenance", 0)
                        for goal in state.goals():
                            if goal["status"] == "waiting":
                                state.wake_goal(goal["id"], "Operator requested a fresh attempt")
                    elif action == "retry":
                        goal = state.goal(data.get("goal_id"))
                        if not goal or goal["status"] not in ("blocked", "waiting"):
                            raise ValueError("Select a blocked or waiting goal")
                        state.wake_goal(goal["id"])
                        state.event("operator.retry", "Operator requested another attempt", goal["id"])
                    elif action == "cancel":
                        goal = state.goal(data.get("goal_id"))
                        if not goal or goal["kind"] == "bootstrap":
                            raise ValueError("Select an existing user or maintenance goal; bootstrap can be paused")
                        if goal["status"] == "completed":
                            raise ValueError("A completed goal cannot be cancelled")
                        state.update_goal(goal["id"], status="cancelled")
                        state.cancel_followups(goal["id"])
                        state.event("goal.cancelled", "Cancelled by operator", goal["id"])
                        state.note(goal["id"], "cancelled:" + goal["id"], "cancelled", {"summary": "Cancelled by operator"}, attempt=goal["attempts"])
                    else:
                        raise ValueError("Unknown control action")
                    state.set("needs_checkpoint", True)
                    self.respond(200, {"ok": True})
                else:
                    self.respond(404, {"error": "Not found"})
            except (ValueError, TypeError, KeyError) as exc:
                self.respond(400, {"error": str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", settings["port"] if port is None else port), Handler)
    server.daemon_threads = True
    return server


def serve(root):
    server = make_server(root)
    stopped = threading.Event()
    release = deploy.current(root)
    def stop(*_):
        stopped.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def monitor():
        while not stopped.wait(2):
            if deploy.current(root) != release:
                break
        server.shutdown()
    threading.Thread(target=monitor, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.3)
    finally:
        stopped.set()
        server.server_close()
