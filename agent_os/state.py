"""Transactional goal state; SQLite stays local, sanitized checkpoints go to Git."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .config import private_dir

BOOTSTRAP = """Make this instance operational on its target WSL2 host. Inspect the system,
fix defects, exercise the dashboard and goal lifecycle, validate the selected Codex model,
verify GitHub publishing and automatic services, and improve concrete usability issues.
Document access and recovery in docs/ACCESS.md. Record reproducible host changes in infra/.
Do not claim perfection. Finish only when the actual readiness checks and independent
review pass. Do not weaken tests or acceptance criteria to pass."""


class State:
    def __init__(self, root):
        self.root = root
        self.path = private_dir(root) / "state.sqlite3"
        with self.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
                acceptance TEXT NOT NULL, commands TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                progress INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL, updated REAL NOT NULL, next_run REAL NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                goal_id TEXT, kind TEXT NOT NULL, message TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, started REAL NOT NULL,
                finished REAL, status TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}');
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.db() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))

    @staticmethod
    def decode(row):
        if not row:
            return None
        result = dict(row)
        result["commands"] = json.loads(result["commands"])
        return result

    def goals(self):
        with self.db() as db:
            return [self.decode(row) for row in db.execute("SELECT * FROM goals ORDER BY created")]

    def goal(self, goal_id):
        with self.db() as db:
            return self.decode(db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone())

    def add_goal(self, title, description, acceptance, commands=None, kind="user", goal_id=None):
        for value in (title, description, acceptance):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Title, description and acceptance criteria are required")
        if len(title) > 200 or len(description) > 20000 or len(acceptance) > 10000:
            raise ValueError("Goal text is too long")
        commands = commands or []
        if not isinstance(commands, list) or len(commands) > 20 or any(not isinstance(c, str) or not c.strip() or len(c) > 2000 for c in commands):
            raise ValueError("Verification commands must be a list of up to 20 commands")
        goal_id = goal_id or uuid.uuid4().hex[:12]
        now = time.time()
        with self.db() as db:
            db.execute("""INSERT INTO goals
                (id,title,description,acceptance,commands,kind,status,created,updated)
                VALUES (?,?,?,?,?,?,'queued',?,?)""",
                (goal_id, title.strip(), description.strip(), acceptance.strip(), json.dumps(commands), kind, now, now))
        self.event("goal.created", title, goal_id)
        self.set("needs_checkpoint", True)
        return self.goal(goal_id)

    def ensure_bootstrap(self):
        if not self.goal("bootstrap"):
            self.add_goal("Prepare this instance for its first goal", BOOTSTRAP,
                          "The regression suite, authenticated Codex execution, independent review, "
                          "GitHub push, local dashboard health, and installed services all work. "
                          "Access and recovery instructions accurately describe this host.",
                          kind="bootstrap", goal_id="bootstrap")

    def update_goal(self, goal_id, **updates):
        allowed = {"status", "attempts", "progress", "summary", "next_run"}
        if not updates or set(updates) - allowed:
            raise ValueError("Invalid goal update")
        updates["updated"] = time.time()
        with self.db() as db:
            db.execute("UPDATE goals SET " + ",".join(k + "=?" for k in updates) + " WHERE id=?", [*updates.values(), goal_id])

    def select_goal(self, now=None):
        now = time.time() if now is None else now
        goals = self.goals()
        bootstrap = next((g for g in goals if g["kind"] == "bootstrap"), None)
        if bootstrap and bootstrap["status"] != "completed":
            return bootstrap if bootstrap["next_run"] <= now and bootstrap["status"] != "cancelled" else None
        active = [g for g in goals if g["status"] in ("queued", "running", "waiting")]
        # An active user goal retains priority through backoff; maintenance cannot consume its quota.
        users = [g for g in active if g["kind"] == "user"]
        if users:
            goal = users[0]
            return goal if goal["next_run"] <= now else None
        return next((g for g in active if g["next_run"] <= now), None)

    def event(self, kind, message, goal_id=None):
        # Raw model/tool output is never written into the public event stream.
        from .redact import redact
        with self.db() as db:
            db.execute("INSERT INTO events (at,goal_id,kind,message) VALUES (?,?,?,?)",
                       (time.time(), goal_id, kind, redact(str(message))[:4000]))
            db.execute("DELETE FROM events WHERE id < (SELECT COALESCE(MAX(id),0)-2000 FROM events)")

    def events(self, limit=100):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def begin_run(self, goal_id):
        run_id = uuid.uuid4().hex
        with self.db() as db:
            db.execute("INSERT INTO runs (id,goal_id,started,status) VALUES (?,?,?,'running')", (run_id, goal_id, time.time()))
            db.execute("UPDATE goals SET status='running',attempts=attempts+1,updated=? WHERE id=?", (time.time(), goal_id))
        return run_id

    def finish_run(self, run_id, status, result):
        with self.db() as db:
            db.execute("UPDATE runs SET finished=?,status=?,result=? WHERE id=?", (time.time(), status, json.dumps(result), run_id))

    def recover(self):
        with self.db() as db:
            count = db.execute("UPDATE goals SET status='queued',next_run=0 WHERE status='running'").rowcount
            db.execute("UPDATE runs SET status='interrupted',finished=? WHERE status='running'", (time.time(),))
        if count:
            self.event("worker.recovered", f"Recovered {count} interrupted goal(s); persisted attempts retained")
        self.set("active_run", None)

    def snapshot(self):
        return {"goals": self.goals(), "events": self.events(),
                "ready": self.get("ready", False), "paused": self.get("paused", False),
                "active_run": self.get("active_run"), "worker_heartbeat": self.get("worker_heartbeat"),
                "next_maintenance": self.get("next_maintenance"),
                "github": self.get("github", {}), "last_checks": self.get("last_checks", []),
                "usage": self.get("usage", {}), "last_error": self.get("last_error", "")}
