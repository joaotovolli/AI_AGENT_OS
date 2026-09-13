"""Opt-in status-issue follow-ups. GitHub text is context, never a control API."""
import time
from datetime import datetime, timezone
from urllib.parse import quote

from .config import load
from .history import text

MARKER = "<!-- agent-os:followup:"


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def since(value):
    return quote(datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds"))


class OperatorChannel:
    def __init__(self, github, state):
        self.github, self.state = github, state

    def authorized(self, repo, comment, settings):
        user = comment.get("user") or {}
        login = user.get("login", "")
        allowed = settings["github_operators"] or [repo.split("/")[0]]
        if user.get("type") != "User" or login.casefold() not in {u.casefold() for u in allowed}:
            return False
        permission = self.github.gh(f"repos/{repo}/collaborators/{quote(login, safe='')}/permission")
        return (permission.get("permission") in ("admin", "maintain", "write")
                and type(user.get("id")) is int and permission.get("user", {}).get("id") == user["id"])

    def comment_once(self, repo, issue, marker, body):
        writer = self.github.gh("user")["id"]
        endpoint = f"repos/{repo}/issues/{issue}/comments"
        # Reconcile an earlier POST that succeeded remotely but timed out locally.
        for page in range(1, 101):
            comments = self.github.gh(f"{endpoint}?per_page=100&page={page}")
            if any(marker in (c.get("body") or "") and c.get("user", {}).get("id") == writer for c in comments):
                return
            if len(comments) < 100:
                self.github.gh(endpoint, "POST", {"body": marker + "\n\n" + body})
                return
        raise RuntimeError("Follow-up receipt reconciliation exceeded its page budget; inspect the status issue")

    def flush(self):
        for item in self.state.followups(pending=True):
            for field, phase in (("acknowledged", "received"), ("answered", "handled")):
                if item[field] or (phase == "handled" and item["status"] != "handled"):
                    continue
                marker = f"{MARKER}{item['comment']}:{phase} -->"
                body = ("Follow-up received. It is queued for the current or next appropriate goal turn. "
                        "Existing authentication, approval and acceptance requirements still apply.")
                if phase == "handled":
                    body = item["reply"] or "The agent incorporated this follow-up. See the goal status and diagnostic history for the outcome."
                body = text(body, 1200).replace("@", "＠").replace("<", "&lt;").replace(">", "&gt;")
                self.comment_once(item["repository"], item["issue"], marker, f"Follow-up #{item['comment']}: {body}")
                with self.state.db() as db:
                    db.execute(f"UPDATE followups SET {field}=1 WHERE id=?", (item["id"],))

    def poll(self):
        settings = load(self.state.root)
        now = time.time()
        if not settings["github_followups"] or now - self.state.get("operator_last_poll", 0) < settings["github_progress_seconds"]:
            return
        self.state.set("operator_last_poll", now)
        try:
            issue = self.state.get("status_issue")
            if not issue:
                return
            repo, _ = self.github.identity()
            enabled = self.state.get("operator_enabled_since")
            if enabled is None:
                enabled = now
                self.state.set("operator_enabled_since", enabled)
            cursor = self.state.get("operator_cursor") or {"since": enabled, "page": 1, "started": now}
            known = {item["id"] for item in self.state.followups()}
            for _ in range(5):
                comments = self.github.gh(f"repos/{repo}/issues/{issue}/comments?per_page=100&page={cursor['page']}&since={since(cursor['since'])}")
                for comment in comments:
                    identity = f"{repo}:{comment['id']}"
                    body = comment.get("body") or ""
                    if (identity in known or not body.strip() or body.lstrip().startswith(MARKER)
                            or timestamp(comment["created_at"]) < enabled or not self.authorized(repo, comment, settings)):
                        continue
                    goals = self.state.goals()
                    active = [g for g in goals if g["status"] not in ("completed", "cancelled")]
                    goal = next((g for g in active if g["kind"] == "bootstrap"),
                                next((g for g in active if g["kind"] == "user"), None))
                    goal_id = goal["id"] if goal else None
                    self.state.receive_followup(repo, issue, comment["id"], comment["user"]["login"], body, goal_id,
                                                received=timestamp(comment["created_at"]))
                    known.add(identity)
                    if goal and goal["status"] in ("waiting", "blocked"):
                        self.state.update_goal(goal_id, status="queued", next_run=0)
                cursor["page"] += 1
                if len(comments) < 100:
                    cursor = {"since": max(enabled, cursor["started"] - 2), "page": 1, "started": now}
                    break
            self.state.set("operator_cursor", cursor)
            self.flush()
            self.state.set("operator_channel", {"checked_at": now, "error": ""})
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            self.state.set("operator_channel", {"checked_at": now, "error": text(exc)})
