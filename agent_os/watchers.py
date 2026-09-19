"""Bounded deterministic observations. No shell, model calls or embedded credentials."""
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .history import text
from .progress import TERMINAL, key
from .redact import redact

KINDS = ("file_exists", "file_changed", "json_value", "http_status")
FIELDS = {"key", "work_key", "kind", "path", "url", "field", "expected", "predicate", "interval_seconds", "lifetime_seconds"}


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != FIELDS:
        raise ValueError("Invalid watcher fields")
    key(spec["key"])
    key(spec["work_key"])
    if spec["kind"] not in KINDS or spec["predicate"] not in ("equals", "changed"):
        raise ValueError("Invalid watcher kind or predicate")
    for name in ("path", "url", "field", "expected"):
        if not isinstance(spec[name], str) or len(spec[name]) > 1000 or redact(spec[name]) != spec[name]:
            raise ValueError("Watcher configuration must be short and contain no credentials")
    for name, low, high in (("interval_seconds", 30, 3600), ("lifetime_seconds", 60, 604800)):
        if type(spec[name]) is not int or not low <= spec[name] <= high:
            raise ValueError(f"{name} must be {low}..{high}")
    if spec["lifetime_seconds"] < spec["interval_seconds"]:
        raise ValueError("Watcher lifetime must cover at least one polling interval")
    if spec["kind"] == "http_status":
        url = urlsplit(spec["url"])
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in spec["url"])):
            raise ValueError("Use a credential-free HTTP(S) URL without query strings or fragments")
        if spec["predicate"] == "equals" and (not spec["expected"].isdigit() or not 100 <= int(spec["expected"]) <= 599):
            raise ValueError("Expected HTTP status must be 100..599")
        if spec["path"] or spec["field"]:
            raise ValueError("HTTP watchers do not use file fields")
    else:
        path = Path(spec["path"])
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "workspace" or len(path.parts) < 2:
            raise ValueError("Watch a relative file under workspace/")
        if spec["url"]:
            raise ValueError("File watchers do not use a URL")
        if spec["kind"] == "json_value" and not spec["field"]:
            raise ValueError("JSON watcher requires a dotted field path")
    if spec["kind"] == "file_changed" and spec["predicate"] != "changed":
        raise ValueError("file_changed uses the changed predicate")
    if spec["kind"] == "file_exists" and (spec["predicate"] != "equals" or spec["expected"] not in ("true", "false")):
        raise ValueError("file_exists compares to true or false")
    return spec


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def observe(root, spec):
    validate_spec(spec)
    if spec["kind"] == "http_status":
        request = Request(spec["url"], headers={"User-Agent": "AI-Agent-OS-condition-watcher"})
        try:
            with build_opener(NoRedirect).open(request, timeout=3) as response:
                return str(response.status)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (401, 403, 429):
                raise ValueError("Remote authorization or rate limit prevents this check")
            return str(status)
    base = Path(root).resolve() / "workspace"
    path = Path(root) / spec["path"]
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(base)):
        raise ValueError("Watcher files cannot traverse symlinks")
    if not path.resolve().is_relative_to(base):
        raise ValueError("Watcher path escapes workspace")
    if spec["kind"] == "file_exists":
        return "true" if path.is_file() else "false"
    if not path.is_file():
        return None
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Watcher file exceeds 1 MiB")
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Watcher file exceeds 1 MiB")
    if spec["kind"] == "file_changed":
        return hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    for part in spec["field"].split("."):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    if isinstance(data, (list, dict)) or (isinstance(data, float) and not math.isfinite(data)):
        raise ValueError("Watch a finite scalar JSON field")
    value = json.dumps(data, ensure_ascii=True, sort_keys=True)
    if len(value) > 1000 or redact(value) != value:
        raise ValueError("Observed field must be a short sanitized scalar")
    return value


class WatcherService:
    def __init__(self, root, state):
        self.root, self.state = root, state
        self.pool = None
        self.pending = {}

    def record(self, original, value=None, error="", now=None):
        now = time.time() if now is None else now
        goal_id, item_key = original["goal_id"], original["key"]
        with self.state.db() as db:
            row = db.execute("SELECT * FROM watchers WHERE goal_id=? AND key=?", (goal_id, item_key)).fetchone()
            goal = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
            if (not row or not goal or goal[0] in TERMINAL or row["status"] != "active"
                    or row["created"] != original["created"] or json.loads(row["spec"]) != original["spec"]):
                return
            spec = original["spec"]
            if now >= row["expires"]:
                db.execute("UPDATE watchers SET status='expired' WHERE goal_id=? AND key=?", (goal_id, item_key))
                self.state._wake(db, goal_id, "Condition watcher expired: " + item_key, operator=False)
                return
            previous = json.loads(row["observation"]) if row["observation"] else None
            meaningful = not error and value is not None
            matched = meaningful and ((spec["predicate"] == "equals" and value == spec["expected"])
                                      or (spec["predicate"] == "changed" and previous is not None and value != previous))
            count = row["polls"] + 1
            interval = min(3600, spec["interval_seconds"] * 2 ** min(count // 3, 6))
            # The first successful value is the durable baseline for a changed predicate.
            observed = json.dumps(value) if meaningful else row["observation"]
            db.execute("UPDATE watchers SET status=?,last_check=?,next_check=?,observation=?,polls=?,error=? WHERE goal_id=? AND key=?",
                       ("triggered" if matched else "active", now, min(row["expires"], now+interval), observed,
                        count, text(error, 200), goal_id, item_key))
            if matched:
                work = db.execute("SELECT data FROM work_items WHERE goal_id=? AND key=?", (goal_id, spec["work_key"])).fetchone()
                if work and json.loads(work[0])["status"] == "waiting":
                    data = dict(json.loads(work[0]), status="actionable", blocker_key="")
                    db.execute("UPDATE work_items SET data=? WHERE goal_id=? AND key=?", (json.dumps(data), goal_id, spec["work_key"]))
                    self.state._wake(db, goal_id, "Condition changed: " + item_key, operator=False)
                    db.execute("INSERT INTO events(at,goal_id,kind,message) VALUES (?,?,'watcher.changed',?)",
                               (now, goal_id, "Condition event for work item " + spec["work_key"]))
                    db.execute("INSERT OR IGNORE INTO history(goal_id,event_key,at,kind,data) VALUES (?,?,?,'watcher',?)",
                               (goal_id, f"watcher:{goal_id}:{item_key}:{row['created']}", now,
                                json.dumps({"summary": "Condition changed", "work_key": spec["work_key"], "watcher_key": item_key})))
                self.state._dirty(db)
            # Unchanged polls stay in SQLite and never create a checkpoint or model turn.

    def service(self, now=None):
        now = time.time() if now is None else now
        for identity, (future, watcher) in list(self.pending.items()):
            if future.done():
                try:
                    self.record(watcher, value=future.result(), now=now)
                except Exception as exc:
                    self.record(watcher, error=type(exc).__name__ + ": " + text(exc, 150), now=now)
                del self.pending[identity]
        for watcher in self.state.watchers():
            if watcher["status"] != "active":
                continue
            goal = self.state.goal(watcher["goal_id"])
            if not goal or goal["status"] in TERMINAL:
                self.state.cancel_watcher(watcher["goal_id"], watcher["key"])
                continue
            if now >= watcher["expires"]:
                self.record(watcher, now=now)
                continue
            identity = (watcher["goal_id"], watcher["key"])
            if watcher["next_check"] > now or identity in self.pending or len(self.pending) >= 4:
                continue
            if self.pool is None:
                self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="condition-watcher")
            self.pending[identity] = (self.pool.submit(observe, self.root, watcher["spec"]), watcher)

    def close(self):
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)
