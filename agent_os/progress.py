"""Durable goal guidance, workstreams and evidence-based external waiting."""
import hashlib
import json
import math
import re
import time

from .history import text

TERMINAL = ("completed", "cancelled")
WORK_STATES = ("actionable", "waiting", "needs_input", "verified")
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def key(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise ValueError("Use a stable key of 1..64 letters, digits, dots, underscores or hyphens")
    return value


def validate_plan(items):
    if not isinstance(items, list) or len(items) > 40:
        raise ValueError("Work plan must contain up to 40 items")
    fields = {"key", "title", "criterion", "status", "blocker_key", "depends_on", "evidence"}
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Invalid work plan fields")
        key(item["key"])
        if item["status"] not in WORK_STATES:
            raise ValueError("Invalid work item status")
        for name in ("title", "criterion", "blocker_key", "evidence"):
            if not isinstance(item[name], str) or len(item[name]) > 2000:
                raise ValueError("Invalid work item text")
        if not item["title"].strip() or not item["criterion"].strip():
            raise ValueError("Work items must map to an existing acceptance criterion")
        if item["status"] in ("waiting", "needs_input") and not item["blocker_key"].strip():
            raise ValueError("Waiting work needs a stable blocker key")
        if item["status"] == "verified" and not item["evidence"].strip():
            raise ValueError("Verified work needs evidence")
        if not isinstance(item["depends_on"], list) or len(item["depends_on"]) > 40:
            raise ValueError("Invalid work dependencies")
        for dep in item["depends_on"]:
            key(dep)
    if len({i["key"] for i in items}) != len(items):
        raise ValueError("Duplicate work item keys")
    return items


def observation_digest(observations):
    """Only stable facts count: summaries, percentages and polling timestamps do not."""
    values = []
    for item in observations:
        name, value = item["key"].lower(), text(item["value"], 1000).lower()
        if re.search(r"(^|[_.-])(time|timestamp|date|checked|updated|progress|percent)([_.-]|$)", name):
            continue
        value = re.sub(r"\b\d{4}-\d\d-\d\d(?:[t ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:z|[+-]\d\d:\d\d)?)?\b", "<time>", value)
        value = re.sub(r"\b\d+(?:\.\d+)?\s*%", "<percent>", value)
        values.append((name, value))
    return hashlib.sha256(json.dumps(sorted(values)).encode()).hexdigest()


def guidance_command(body):
    first, _, content = body.strip().partition("\n")
    parts = first.split()
    if not parts or parts[0] not in ("/guide", "/guide-clear"):
        return None
    if len(parts) != 3 or (parts[0] == "/guide-clear" and content.strip()):
        raise ValueError("Use /guide <goal-id> <key> followed by text, or /guide-clear <goal-id> <key>")
    if parts[0] == "/guide" and not content.strip():
        raise ValueError("Persistent guidance requires text on the next line")
    return parts[1], key(parts[2]), content.strip() if parts[0] == "/guide" else None


class GoalProgress:
    def init_progress(self, db):
        db.executescript("""
          CREATE TABLE IF NOT EXISTS strategies (
            goal_id TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(goal_id,key));
          CREATE TABLE IF NOT EXISTS goal_control (
            goal_id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0, wait TEXT NOT NULL DEFAULT '{}');
          CREATE TABLE IF NOT EXISTS guidance (
            goal_id TEXT NOT NULL, key TEXT NOT NULL, body TEXT NOT NULL, active INTEGER NOT NULL,
            version INTEGER NOT NULL, updated REAL NOT NULL, source TEXT NOT NULL, PRIMARY KEY(goal_id,key));
          CREATE TABLE IF NOT EXISTS work_items (
            goal_id TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(goal_id,key));
          CREATE TABLE IF NOT EXISTS watchers (
            goal_id TEXT NOT NULL, key TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL,
            created REAL NOT NULL, expires REAL NOT NULL, next_check REAL NOT NULL, last_check REAL,
            observation TEXT, polls INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(goal_id,key));
        """)

    @staticmethod
    def _dirty(db):
        db.execute("INSERT OR REPLACE INTO meta VALUES ('needs_checkpoint','true')")

    def _wake(self, db, goal_id, reason, operator=True):
        goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not goal or goal[0] in TERMINAL:
            return False
        db.execute("INSERT OR IGNORE INTO goal_control(goal_id) VALUES (?)", (goal_id,))
        db.execute("UPDATE goal_control SET revision=revision+1,wait='{}' WHERE goal_id=?", (goal_id,))
        statuses = ("waiting", "blocked") if operator else ("waiting",)
        if goal[0] in statuses:
            db.execute("UPDATE goals SET status='queued',next_run=0,updated=? WHERE id=?", (time.time(), goal_id))
        db.execute("INSERT INTO events(at,goal_id,kind,message) VALUES (?,?,'goal.wake',?)", (time.time(), goal_id, text(reason)))
        self._dirty(db)
        return True

    def wake_goal(self, goal_id, reason="Operator requested another attempt", operator=True):
        with self.db() as db:
            return self._wake(db, goal_id, reason, operator)

    def context_revision(self, goal_id):
        with self.db() as db:
            row = db.execute("SELECT revision FROM goal_control WHERE goal_id=?", (goal_id,)).fetchone()
        return row[0] if row else 0

    def wait_state(self, goal_id):
        with self.db() as db:
            row = db.execute("SELECT wait FROM goal_control WHERE goal_id=?", (goal_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def _guidance(self, db, goal_id, item_key, body, source):
        key(item_key)
        goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not goal or goal[0] in TERMINAL:
            raise ValueError("Guidance requires an active goal")
        if body is not None and (not isinstance(body, str) or not body.strip() or len(body) > 4000):
            raise ValueError("Guidance must contain 1..4000 characters")
        count = db.execute("SELECT COUNT(*) FROM guidance WHERE goal_id=? AND active=1 AND key!=?", (goal_id, item_key)).fetchone()[0]
        if body is not None and count >= 20:
            raise ValueError("Clear an existing item before adding more than 20 active guidance items")
        previous = db.execute("SELECT * FROM guidance WHERE goal_id=? AND key=?", (goal_id, item_key)).fetchone()
        if body is None and not previous:
            raise ValueError("Guidance key does not exist")
        value = text(body, 4000) if body is not None else previous["body"]
        version = previous["version"] + 1 if previous else 1
        db.execute("INSERT OR REPLACE INTO guidance VALUES (?,?,?,?,?,?,?)",
                   (goal_id, item_key, value, int(body is not None), version, time.time(), text(source, 120)))
        self._wake(db, goal_id, "Persistent guidance updated: " + item_key)
        db.execute("INSERT INTO history(goal_id,event_key,at,kind,data) VALUES (?,?,?,'guidance',?)",
                   (goal_id, f"guidance:{goal_id}:{item_key}:{version}", time.time(),
                    json.dumps({"key": item_key, "version": version, "summary": value if body is not None else "Guidance cleared"})))

    def set_guidance(self, goal_id, item_key, body, source="dashboard"):
        with self.db() as db:
            self._guidance(db, goal_id, item_key, body, source)
        return self.guidance(goal_id)

    def guidance(self, goal_id, active=True):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM guidance WHERE goal_id=?" +
                     (" AND active=1" if active else "") + " ORDER BY key", (goal_id,))]

    def work_plan(self, goal_id):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM work_items WHERE goal_id=? ORDER BY key", (goal_id,))]

    def save_work_plan(self, goal_id, items):
        validate_plan(items)
        combined = {i["key"]: i for i in self.work_plan(goal_id)}
        combined.update({i["key"]: i for i in items})
        if len(combined) > 40:
            raise ValueError("A goal can have up to 40 work items")
        visited = set()
        def visit(name, chain):
            if name not in combined or name in chain:
                raise ValueError("Work dependencies must exist and contain no cycles")
            if name in visited:
                return
            for dep in combined[name]["depends_on"]:
                visit(dep, chain | {name})
            visited.add(name)
        for name in combined:
            visit(name, set())
        with self.db() as db:
            goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
            if not goal or goal[0] in TERMINAL:
                raise ValueError("Work plan requires an active goal")
            for item in items:
                cleaned = {k: text(v, 2000) if isinstance(v, str) else v for k, v in item.items()}
                db.execute("INSERT OR REPLACE INTO work_items VALUES (?,?,?)", (goal_id, item["key"], json.dumps(cleaned)))
                if item["status"] != "waiting":
                    for watcher in db.execute("SELECT key,spec FROM watchers WHERE goal_id=? AND status='active'", (goal_id,)).fetchall():
                        if json.loads(watcher["spec"])["work_key"] == item["key"]:
                            db.execute("UPDATE watchers SET status='cancelled' WHERE goal_id=? AND key=?", (goal_id, watcher["key"]))
            self._dirty(db)

    def actionable_work(self, goal_id):
        plan = self.work_plan(goal_id)
        verified = {i["key"] for i in plan if i["status"] == "verified"}
        return [i for i in plan if i["status"] == "actionable" and set(i["depends_on"]) <= verified]

    def plan_complete(self, goal_id):
        return all(i["status"] == "verified" for i in self.work_plan(goal_id))

    def schedule_external(self, goal_id, diagnostic, settings, now=None):
        from .strategy import scheduled_delay
        now = time.time() if now is None else now
        scheduled = scheduled_delay(self, goal_id, now)
        old = self.wait_state(goal_id)
        identity = {"blocker_key": diagnostic.get("blocker_key") or "external-unspecified",
                    "approach_key": diagnostic.get("approach_key") or "unspecified",
                    "evidence_digest": diagnostic.get("evidence_digest", observation_digest([]))}
        equivalent = bool(old) and all(old.get(k) == v for k, v in identity.items())
        count = old.get("equivalent_attempts", 0) + 1 if equivalent else 1
        threshold = settings["external_repeat_limit"]
        maximum = settings["external_wait_max_seconds"]
        stalled = count >= threshold
        delay = min(maximum, settings["external_wait_min_seconds"] * 2 ** min(max(count-threshold, 0), 16)) if stalled else 300
        if old and not equivalent:
            delay = 2  # A genuinely different method or observation is useful immediately.
        requested = diagnostic.get("next_check_at", 0)
        if isinstance(requested, (int, float)) and math.isfinite(requested) and requested > now:
            delay = min(maximum, max(delay, requested-now))
        active = [w for w in self.watchers(goal_id) if w["status"] == "active" and w["expires"] > now]
        waiting_keys = {i["key"] for i in self.work_plan(goal_id) if i["status"] == "waiting"}
        observed_keys = {w["spec"]["work_key"] for w in active}
        watching = bool(waiting_keys) and waiting_keys <= observed_keys
        if watching and not (old and not equivalent):
            delay = min(maximum, min(w["expires"] for w in active)-now)
        if scheduled is not None:
            delay = scheduled
        waiting = dict(identity, equivalent_attempts=count, stalled=stalled, next_run=now+delay,
                       reason=("Documented availability; next useful check scheduled" if scheduled is not None else "Background watchers are waiting; full model attempts deferred" if watching else
                               "Unchanged external dependency; full model attempts deferred" if stalled else "Waiting for an external dependency"),
                       wake_on="Operator context, a condition event, a different approach, or the next scheduled check")
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO goal_control(goal_id) VALUES (?)", (goal_id,))
            db.execute("UPDATE goal_control SET wait=? WHERE goal_id=?", (json.dumps(waiting), goal_id))
            self._dirty(db)
        return delay

    def complete_if_current(self, goal_id, revision):
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO goal_control(goal_id) VALUES (?)", (goal_id,))
            actual = db.execute("SELECT revision FROM goal_control WHERE goal_id=?", (goal_id,)).fetchone()[0]
            goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
            if actual != revision or not goal or goal[0] in TERMINAL:
                return False
            db.execute("UPDATE goals SET status='completed',progress=100,next_run=0,updated=? WHERE id=?", (time.time(), goal_id))
            self.cleanup_progress(db, goal_id)
            return True

    def clear_wait(self, goal_id):
        with self.db() as db:
            db.execute("UPDATE goal_control SET wait='{}' WHERE goal_id=?", (goal_id,))

    def cleanup_progress(self, db, goal_id):
        db.execute("UPDATE guidance SET active=0 WHERE goal_id=?", (goal_id,))
        db.execute("UPDATE watchers SET status='cancelled' WHERE goal_id=? AND status='active'", (goal_id,))
        db.execute("UPDATE goal_control SET wait='{}' WHERE goal_id=?", (goal_id,))
        self._dirty(db)

    def progress_snapshot(self, goals=None):
        from .strategy import all_records
        result = {}
        for goal in self.goals() if goals is None else goals:
            goal_id = goal["id"]
            plan = self.work_plan(goal_id)
            actionable = self.actionable_work(goal_id)
            result[goal_id] = {"guidance": self.guidance(goal_id), "work_plan": plan,
                               "actionable": [i["key"] for i in actionable], "wait": self.wait_state(goal_id),
                               "partial": bool(actionable) and any(i["status"] in ("waiting", "needs_input") for i in plan),
                               "watchers": self.watchers(goal_id), "strategies": all_records(self, goal_id)}
        return result

    def export_progress(self, completion=None):
        data = {}
        with self.db() as db:
            for table in ("goal_control", "guidance", "work_items", "watchers", "strategies"):
                data[table] = [dict(r) for r in db.execute("SELECT * FROM " + table)]
        if completion:
            for row in data["guidance"]:
                if row["goal_id"] == completion:
                    row["active"] = 0
            for row in data["watchers"]:
                if row["goal_id"] == completion and row["status"] == "active":
                    row["status"] = "cancelled"
            for row in data["goal_control"]:
                if row["goal_id"] == completion:
                    row["wait"] = "{}"
        return data

    def restore_progress(self, data):
        with self.db() as db:
            for table in ("goal_control", "guidance", "work_items", "watchers", "strategies"):
                columns = [r[1] for r in db.execute("PRAGMA table_info(" + table + ")")]
                for row in data.get(table, []):
                    if set(row) != set(columns) or not db.execute("SELECT 1 FROM goals WHERE id=?", (row["goal_id"],)).fetchone():
                        raise ValueError("Invalid goal progress checkpoint")
                    db.execute("INSERT OR REPLACE INTO " + table + " (" + ",".join(columns) + ") VALUES (" +
                               ",".join("?" for _ in columns) + ")", [row[c] for c in columns])
            for goal in db.execute("SELECT id,status FROM goals").fetchall():
                if goal["status"] in TERMINAL:
                    self.cleanup_progress(db, goal["id"])

    def watchers(self, goal_id=None):
        with self.db() as db:
            rows = db.execute("SELECT * FROM watchers" + (" WHERE goal_id=?" if goal_id else "") + " ORDER BY goal_id,key",
                              (goal_id,) if goal_id else ()).fetchall()
        return [dict(r, spec=json.loads(r["spec"]), observation=json.loads(r["observation"]) if r["observation"] else None) for r in rows]

    def register_watcher(self, goal_id, spec, now=None):
        from .watchers import validate_spec
        validate_spec(spec)
        now = time.time() if now is None else now
        with self.db() as db:
            goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
            row = db.execute("SELECT data FROM work_items WHERE goal_id=? AND key=?", (goal_id, spec["work_key"])).fetchone()
            if not goal or goal[0] in TERMINAL or not row or json.loads(row[0])["status"] != "waiting":
                raise ValueError("Watchers require an active goal and an externally waiting work item")
            previous = db.execute("SELECT spec FROM watchers WHERE goal_id=? AND key=?", (goal_id, spec["key"])).fetchone()
            if previous and json.loads(previous[0]) == spec:
                return  # Repeated registration cannot reset the baseline, backoff or expiry.
            count = db.execute("SELECT COUNT(*) FROM watchers WHERE goal_id=? AND status='active' AND key!=?", (goal_id, spec["key"])).fetchone()[0]
            if count >= 10:
                raise ValueError("At most ten active watchers per goal")
            db.execute("INSERT OR REPLACE INTO watchers(goal_id,key,spec,status,created,expires,next_check) VALUES (?,?,?,'active',?,?,?)",
                       (goal_id, spec["key"], json.dumps(spec), now, now+spec["lifetime_seconds"], now))
            self._dirty(db)

    def cancel_watcher(self, goal_id, item_key):
        with self.db() as db:
            db.execute("UPDATE watchers SET status='cancelled' WHERE goal_id=? AND key=? AND status='active'", (goal_id, item_key))
            self._dirty(db)
