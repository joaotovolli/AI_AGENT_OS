"""Transactional goal state; SQLite stays local, sanitized checkpoints go to Git."""
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .config import private_dir
from .progress import GoalProgress, guidance_command

BOOTSTRAP = """Make this instance operational on its target WSL2 host. Inspect the system,
fix defects, exercise the dashboard and goal lifecycle, validate the selected Codex model,
verify GitHub publishing and automatic services, and improve concrete usability issues.
Document access and recovery in docs/ACCESS.md. Record reproducible host changes in infra/.
Do not claim perfection. Finish only when the actual readiness checks and independent
review pass. Do not weaken tests or acceptance criteria to pass."""


class State(GoalProgress):
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
              CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL,
                event_key TEXT UNIQUE NOT NULL, at REAL NOT NULL, attempt INTEGER,
                kind TEXT NOT NULL, data TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS history_goal ON history(goal_id, id);
              CREATE TABLE IF NOT EXISTS followups (
                id TEXT PRIMARY KEY, repository TEXT NOT NULL, issue INTEGER NOT NULL,
                comment INTEGER NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL,
                goal_id TEXT, status TEXT NOT NULL DEFAULT 'queued', run_id TEXT,
                received REAL NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0,
                answered INTEGER NOT NULL DEFAULT 0, reply TEXT NOT NULL DEFAULT '');
            """)

            self.init_progress(db)

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
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", goal_id):
            raise ValueError("Invalid goal ID")
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

            if updates.get("status") in ("completed", "cancelled"):
                self.cleanup_progress(db, goal_id)

    def select_goal(self, now=None):
        now = time.time() if now is None else now
        goals = self.goals()
        bootstrap = next((g for g in goals if g["kind"] == "bootstrap"), None)
        if bootstrap and bootstrap["status"] != "completed":
            return bootstrap if bootstrap["next_run"] <= now and bootstrap["status"] not in ("cancelled", "blocked") else None
        active = [g for g in goals if g["status"] in ("queued", "running", "waiting", "blocked")]
        # An active user goal retains priority through backoff; maintenance cannot consume its quota.
        users = [g for g in active if g["kind"] == "user"]
        if users:
            goal = users[0]
            return goal if goal["next_run"] <= now and goal["status"] != "blocked" else None
        return next((g for g in active if g["next_run"] <= now and g["status"] != "blocked"), None)

    def note(self, goal_id, event_key, kind, data, attempt=None, at=None):
        from .history import text
        if not self.goal(goal_id):
            raise ValueError("History requires an existing goal")
        clean = {text(k, 60): text(v) if isinstance(v, str) else v for k, v in data.items()
                 if isinstance(v, (str, int, float, bool)) or v is None}
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO history (goal_id,event_key,at,attempt,kind,data) VALUES (?,?,?,?,?,?)",
                       (goal_id, event_key, time.time() if at is None else at, attempt, text(kind, 60), json.dumps(clean)))
        self.set("needs_checkpoint", True)

    def history(self, goal_id, limit=12, kinds=()):
        clause = " AND kind IN (" + ",".join("?" for _ in kinds) + ")" if kinds else ""
        with self.db() as db:
            rows = db.execute("SELECT * FROM history WHERE goal_id=?" + clause + " ORDER BY id DESC LIMIT ?",
                              (goal_id, *kinds, -1 if limit is None else limit)).fetchall()
        return [dict(row, data=json.loads(row["data"])) for row in reversed(rows)]

    def dirty_histories(self):
        with self.db() as db:
            rows = db.execute("SELECT goal_id,MAX(id) AS last FROM history GROUP BY goal_id").fetchall()
        return [r["goal_id"] for r in rows if r["last"] > self.get("history_exported:" + r["goal_id"], 0)]

    def receive_followup(self, repository, issue, comment, author, body, goal_id=None, received=None):
        from .redact import redact
        identity = f"{repository}:{comment}"
        with self.db() as db:
            inserted = db.execute("""INSERT OR IGNORE INTO followups
                (id,repository,issue,comment,author,body,goal_id,received) VALUES (?,?,?,?,?,?,?,?)""",
                (identity, repository, issue, comment, author, redact(body)[:8000], goal_id,
                 time.time() if received is None else received)).rowcount
            if inserted:
                try:
                    command = guidance_command(body)
                    if command:
                        target, item_key, instruction = command
                        self._guidance(db, target, item_key, instruction, identity)
                        db.execute("UPDATE followups SET goal_id=?,status='handled',reply=? WHERE id=?",
                                   (target, "Persistent guidance " + ("saved: " if instruction else "cleared: ") + item_key, identity))
                    elif goal_id:
                        self._wake(db, goal_id, "Authorized operator follow-up received")
                except ValueError as exc:
                    db.execute("UPDATE followups SET status='handled',reply=? WHERE id=?", (str(exc), identity))
        if inserted:
            self.event("operator.received", "Authorized GitHub follow-up queued", goal_id)
            self.set("needs_checkpoint", True)
        return bool(inserted)

    def followups(self, pending=False):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM followups " +
                ("WHERE status!='handled' OR acknowledged=0 OR answered=0 " if pending else "") + "ORDER BY received,comment")]

    def claim_followups(self, goal_id, run_id):
        goal = self.goal(goal_id)
        with self.db() as db:
            db.execute("UPDATE followups SET status='delivered',run_id=?,goal_id=? WHERE status='queued' "
                       "AND (goal_id=? OR (goal_id IS NULL AND ?='user'))", (run_id, goal_id, goal_id, goal["kind"]))
            return [dict(r) for r in db.execute("SELECT * FROM followups WHERE run_id=? AND status='delivered' ORDER BY received,comment", (run_id,))]

    def finish_followups(self, run_id, success, reply=""):
        from .history import text
        with self.db() as db:
            db.execute("UPDATE followups SET status=?,reply=?,run_id=NULL WHERE run_id=? AND status='delivered'",
                       ("handled" if success else "queued", text(reply, 1200) if success else "", run_id))
        self.set("needs_checkpoint", True)

    def pending_followups(self, goal_id):
        return any(f["status"] == "queued" and f["goal_id"] == goal_id for f in self.followups())

    def cancel_followups(self, goal_id):
        with self.db() as db:
            db.execute("UPDATE followups SET status='handled',run_id=NULL,reply=? WHERE goal_id=? AND status!='handled'",
                       ("The target goal was cancelled before this follow-up could be completed.", goal_id))

    def followup_receipts(self):
        keys = ("id", "repository", "issue", "comment", "goal_id", "status", "received")
        return [{k: item[k] for k in keys} for item in self.followups()]

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
            db.execute("UPDATE followups SET status='queued',run_id=NULL WHERE status='delivered'")
        if count:
            self.event("worker.recovered", f"Recovered {count} interrupted goal(s); persisted attempts retained")
        self.set("active_run", None)
        if self.get("framework", {}).get("status") == "applying":
            self.set("framework", {"status": "attention", "message": "Framework update was interrupted. Inspect source and remote state before retrying."})

    def snapshot(self):
        return {"goals": self.goals(), "events": self.events(), "goal_progress": self.progress_snapshot(),
                "diagnostics": {g["id"]: self.history(g["id"], 1) for g in self.goals()},
                "followups": self.followup_receipts()[-50:], "operator_channel": self.get("operator_channel", {}),
                "framework": self.get("framework", {}),
                "ready": self.get("ready", False), "paused": self.get("paused", False),
                "active_run": self.get("active_run"), "worker_heartbeat": self.get("worker_heartbeat"),
                "next_maintenance": self.get("next_maintenance"),
                "github": self.get("github", {}), "last_checks": self.get("last_checks", []),
                "usage": self.get("usage", {}), "last_error": self.get("last_error", "")}
