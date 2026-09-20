"""Git checkpoints and one live GitHub issue per instance."""
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import atomic_json, load, private_dir
from .process import run
from .redact import PATTERNS, redact, secret_path


def repo_name(url):
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?", url.strip())
    if not match:
        raise ValueError("origin must be a GitHub HTTPS or SSH URL without embedded credentials")
    return match.group(1)


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


class GitHub:
    def __init__(self, root, state):
        self.root, self.state = Path(root), state

    def git(self, *args, check=True):
        result = run(["git", *args], self.root, timeout=90, env={**__import__('os').environ, "GIT_TERMINAL_PROMPT": "0"})
        if check and result.returncode:
            raise RuntimeError(redact(result.output[-2000:]))
        return result

    def identity(self):
        repo = repo_name(self.git("remote", "get-url", "origin").output.strip())
        branch = self.git("symbolic-ref", "--short", "HEAD").output.strip()
        if not branch:
            raise RuntimeError("A named Git branch is required")
        return repo, branch

    def gh(self, endpoint, method="GET", body=None):
        args = ["gh", "api", endpoint, "--method", method]
        if body is not None:
            args += ["--input", "-"]
        result = run(args, self.root, timeout=30, input_text=json.dumps(body) if body is not None else None)
        if result.returncode:
            raise RuntimeError(redact(result.output[-2000:]))
        return json.loads(result.output) if result.output.strip() else {}

    def render(self, snapshot=None):
        from .projects import discover
        snapshot = snapshot if snapshot is not None else self.state.snapshot()
        lines = ["# Instance status", "", f"Updated: {utc(time.time())}", "",
                 f"Instance: `{self.root.name}`", f"Ready: **{snapshot['ready']}**",
                 f"Paused: **{snapshot['paused']}**", "",
                 "[Dashboard and operations](docs/ACCESS.md)", "", "## Goals", ""]
        for goal in snapshot["goals"][-50:]:
            lines += [f"### {redact(goal['title']).replace(chr(10), ' ')}",
                      f"`{goal['id']}` · {goal['status']} · {goal['progress']}% · attempts: {goal['attempts']}",
                      "", redact(goal["summary"]), ""]
            progress = snapshot.get("goal_progress", {}).get(goal["id"], {})
            for decision in progress.get("strategies", []):
                lines += ["Strategy: " + redact(decision["work_key"] + " / " + decision["action"] + " — " + decision["reason"]),
                          "Next: " + redact(decision["next_action"]), ""]
            waiting = progress.get("wait", {})
            if progress.get("partial"):
                lines += ["Partially blocked; independent work remains actionable.", ""]
            if waiting:
                lines += [waiting["reason"] + ". Next model check: " + utc(waiting["next_run"]) + ".", waiting["wake_on"], ""]
            for item in progress.get("work_plan", []):
                lines += [f"- {item['key']}: {item['status']} | {item['title']}"]
            for item in progress.get("guidance", []):
                lines += [f"- Active guidance {item['key']} (v{item['version']}): {item['body']}"]
            for watcher in progress.get("watchers", []):
                lines += [f"- Watcher {watcher['key']}: {watcher['status']}; last check " +
                          (utc(watcher['last_check']) if watcher['last_check'] else "pending") +
                          "; observation " + str(watcher['observation']) +
                          ("; error " + watcher['error'] if watcher['error'] else "")]
            if self.state.history(goal["id"], 1):
                lines += [f"[Diagnostic history](docs/history/{goal['id']}/README.md)", ""]
        projects = discover(self.root)
        if projects:
            lines += ["## Projects", ""]
            for project in projects:
                name = redact(project["name"]).replace("[", "").replace("]", "")
                lines += [f"- {name}: {project.get('url') or project['path']} ({project.get('status', 'building')})"]
            lines += [""]
        lines += ["## Recent activity", ""]
        lines += [f"- {utc(e['at'])}: {redact(e['message'])}" for e in reversed(snapshot["events"][:15])]
        lines += ["", "Progress percentages are estimates. Completion requires verification and a successful GitHub checkpoint.",
                  "Private command output and credentials are not published.", ""]
        return "\n".join(lines)

    def publish_live(self, force=False):
        config = load(self.root)
        if not force and time.time() - self.state.get("last_live_update", 0) < config["github_progress_seconds"]:
            return
        # Persist throttle before I/O so an outage does not hammer GitHub.
        self.state.set("last_live_update", time.time())
        try:
            repo, branch = self.identity()
            number = self.state.get("status_issue")
            body = re.sub(r"\(docs/([^)]*)\)", lambda m: f"(https://github.com/{repo}/blob/{branch}/docs/{m[1]})", self.render())
            if number:
                self.gh(f"repos/{repo}/issues/{number}", "PATCH", {"body": body})
            else:
                title = f"Agent OS status: {self.root.name}"
                # Recover an existing status issue after a local database loss.
                issues = self.gh(f"repos/{repo}/issues?state=open&per_page=100")
                found = next((i for i in issues if i.get("title") == title and "pull_request" not in i), None)
                if found:
                    number = found["number"]
                    self.gh(f"repos/{repo}/issues/{number}", "PATCH", {"body": body})
                else:
                    number = self.gh(f"repos/{repo}/issues", "POST", {"title": title, "body": body})["number"]
                self.state.set("status_issue", number)
            info = self.state.get("github", {})
            info.update({"live_url": f"https://github.com/{repo}/issues/{number}", "live_updated": time.time(), "live_error": ""})
            self.state.set("github", info)
        except (OSError, RuntimeError, ValueError) as exc:
            info = self.state.get("github", {})
            info["live_error"] = redact(str(exc))[:1000]
            self.state.set("github", info)

    def scan_index(self):
        """Check staged contents, including files force-added by a subprocess."""
        paths = self.git("ls-files", "-z").output.split("\0")
        for path in filter(None, paths):
            if secret_path(path):
                raise RuntimeError("Refusing to publish credential/runtime path: " + path)
            blob = subprocess.run(["git", "show", ":" + path], cwd=self.root, capture_output=True, timeout=30)
            if blob.returncode:
                raise RuntimeError("Cannot inspect staged file: " + path)
            if len(blob.stdout) > 5 * 1024 * 1024:
                raise RuntimeError("Artifact exceeds automatic Git limit (5 MiB): " + path)
            # Binary files cannot be scanned reliably and require explicit artifact handling.
            if b"\0" in blob.stdout:
                raise RuntimeError("Move binary artifacts to a documented release workflow: " + path)
            text = blob.stdout.decode(errors="replace")
            if any(pattern.search(text) for pattern in PATTERNS):
                raise RuntimeError("Possible credential in staged content: " + path)

    def workspace_digest(self):
        files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=self.root)
        digest = hashlib.sha256()
        for name in sorted(set(files.decode().split("\0"))):
            if not name or name in ("STATUS.md", "state/checkpoint.json") or name.startswith((".agent-os/", "docs/history/")):
                continue
            path = self.root / name
            digest.update(name.encode())
            if path.is_symlink():
                digest.update(str(path.readlink()).encode())
            elif path.is_file():
                digest.update(path.read_bytes())
            else:
                digest.update(b"<deleted>")
        return digest.hexdigest()

    def checkpoint(self, message, completion=None):
        from .history import export
        repo, branch = self.identity()
        export(self.root, self.state)
        snapshot = self.state.snapshot()
        if completion:
            for goal in snapshot["goals"]:
                if goal["id"] == completion:
                    goal.update(status="completed", progress=100, next_run=0)
                    if goal["kind"] == "bootstrap":
                        snapshot["ready"] = True
        self.root.joinpath("STATUS.md").write_text(self.render(snapshot), encoding="utf-8")
        public = {"format_version": 3, "repository": repo, "settings": load(self.root),
                  "checkpoint_at": time.time(), "followup_receipts": self.state.followup_receipts(),
                  "goals": snapshot["goals"], "ready": snapshot["ready"],
                  "goal_progress": self.state.export_progress(completion)}
        # Checkpoint is a recovery aid, never a store for tokens or raw model output.
        public = json.loads(redact(json.dumps(public, ensure_ascii=False)))
        atomic_json(self.root / "state" / "checkpoint.json", public)
        self.git("add", "-A")
        self.scan_index()
        if self.git("diff", "--cached", "--quiet", check=False).returncode:
            self.git("commit", "-m", message)
        # Never force push or discard divergence. A repair iteration can reconcile conflicts.
        self.git("fetch", "origin", branch)
        head = self.git("rev-parse", "HEAD").output.strip()
        remote = self.git("rev-parse", "FETCH_HEAD").output.strip()
        if self.git("merge-base", "--is-ancestor", remote, head, check=False).returncode:
            raise RuntimeError("GitHub has commits absent locally. Reconcile the branches without force push.")
        # Scan every unpushed commit, including commits made directly by Codex.
        for commit in self.git("rev-list", f"{remote}..HEAD").output.splitlines():
            changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "--diff-filter=ACMRT", "-r", "-z", commit], cwd=self.root).decode().split("\0")
            for path in changed:
                if not path:
                    continue
                if secret_path(path):
                    raise RuntimeError("Unpushed commit includes private path: " + path)
                blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=self.root)
                if len(blob) > 5 * 1024 * 1024 or b"\0" in blob:
                    raise RuntimeError("Unpushed commit includes a large or binary artifact: " + path)
                if any(pattern.search(blob.decode(errors="replace")) for pattern in PATTERNS):
                    raise RuntimeError("Possible credential in an unpushed commit; remove it before publishing")
        self.git("push", "origin", f"HEAD:refs/heads/{branch}")
        confirmed = self.git("ls-remote", "origin", f"refs/heads/{branch}").output.split()
        if not confirmed or confirmed[0] != head:
            raise RuntimeError("GitHub branch verification did not match the local checkpoint")
        info = self.state.get("github", {})
        info.update({"synced": True, "commit": head, "last_push": time.time(), "error": "", "repository": repo})
        self.state.set("github", info)
        self.state.set("needs_checkpoint", False)
        return head

    def promote(self):
        """Advance the stable branch only after checks have passed."""
        _, branch = self.identity()
        stable = self.state.get("stable_branch", "main")
        if branch == stable:
            return
        self.git("fetch", "origin", stable)
        if self.git("merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD", check=False).returncode:
            raise RuntimeError("Stable branch has diverged; reconcile it before activation")
        self.git("push", "origin", f"HEAD:refs/heads/{stable}")
