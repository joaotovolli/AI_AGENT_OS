"""Discover upstream changes and validate three-way integration before activation."""
import json
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from . import checks, config, deploy
from .github import GitHub, repo_name
from .history import text
from .process import run

MANIFEST = ".agent-os-base.json"
ROOT_FILES = {"AGENTS.md", "README.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE", "pyproject.toml", ".gitignore"}


def managed(path):
    return (path in ROOT_FILES or path.startswith(("agent_os/", "scripts/", "tests/", ".github/"))
            or (path.startswith("docs/") and path not in ("docs/ACCESS.md", "docs/VALIDATION.md")
                and not path.startswith(("docs/evidence/", "docs/history/"))))


def provenance(root):
    path = Path(root) / MANIFEST
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError("Framework provenance must be a regular file")
    data = json.loads(path.read_text())
    if data.get("format_version") != 1 or not re.fullmatch(r"[0-9a-f]{40}", data.get("base_commit", "")):
        raise ValueError("Invalid framework provenance")
    repo_name("https://github.com/" + data["repository"] + ".git")
    if run(["git", "check-ref-format", "--branch", data["branch"]], root, timeout=10).returncode:
        raise ValueError("Invalid base branch")
    return data


def stamp(source, destination):
    from .state import State
    data = provenance(source)
    if data is None:
        github = GitHub(source, State(source))
        repo, _ = github.identity()
        data = {"format_version": 1, "repository": repo, "branch": "main",
                "base_commit": github.git("rev-parse", "HEAD").output.strip()}
    config.atomic_json(Path(destination) / MANIFEST, data)


class Framework:
    def __init__(self, root, state, heartbeat=lambda: None, cancel=lambda: False):
        self.root, self.state = Path(root), state
        self.github = GitHub(root, state)
        self.heartbeat, self.cancel = heartbeat, cancel

    def fetch(self, data):
        self.github.git("fetch", "--no-tags", "https://github.com/" + data["repository"] + ".git", data["branch"])
        return self.github.git("rev-parse", "FETCH_HEAD").output.strip()

    def check(self):
        data = provenance(self.root)
        if not data:
            result = {"status": "unconfigured", "checked_at": time.time(),
                      "message": "No base provenance. New instances record it automatically; older instances require explicit adoption."}
        else:
            target = self.fetch(data)
            if self.github.git("merge-base", "--is-ancestor", data["base_commit"], target, check=False).returncode:
                raise RuntimeError("Known base is not an ancestor of upstream. Review provenance before updating.")
            paths = [p for p in self.github.git("diff", "--name-only", data["base_commit"], target).output.splitlines() if managed(p)]
            result = dict(data, status="available" if paths else "current", target_commit=target,
                          checked_at=time.time(), changed_files=paths, message="Compatible changes still require integration and validation.")
        self.state.set("framework", result)
        return result

    def entry(self, revision, path):
        listing = self.github.git("ls-tree", revision, "--", path).output.strip()
        if not listing:
            return None
        metadata, _ = listing.split("\t", 1)
        mode, kind, sha = metadata.split()
        if mode not in ("100644", "100755") or kind != "blob":
            raise RuntimeError("Unsupported framework entry: " + path)
        size = int(self.github.git("cat-file", "-s", sha).output)
        if size > 5 * 1024 * 1024:
            raise RuntimeError("Framework file exceeds update size limit: " + path)
        # subprocess bytes preserve exact text; process.run decodes with replacement for diagnostics.
        content = subprocess.check_output(["git", "cat-file", "blob", sha], cwd=self.root)
        if b"\0" in content:
            raise RuntimeError("Binary framework changes need deliberate integration: " + path)
        return mode, content.decode("utf-8")

    def merge_entry(self, path, base, local, incoming):
        if local == base or local == incoming:
            return incoming
        if incoming == base:
            return local
        if None in (base, local, incoming):
            raise RuntimeError("Framework add/delete conflict: " + path)
        mode = local[0] if incoming[0] == base[0] else incoming[0] if local[0] in (base[0], incoming[0]) else None
        if mode is None:
            raise RuntimeError("Framework mode conflict: " + path)
        with tempfile.TemporaryDirectory(dir=config.private_dir(self.root)) as temp:
            files = [Path(temp) / name for name in ("local", "base", "incoming")]
            for file, value in zip(files, (local, base, incoming)):
                file.write_text(value[1], encoding="utf-8")
            # This output is source, so never pass it through the bounded diagnostic log tail.
            merged = subprocess.run(["git", "merge-file", "-p", *map(str, files)], cwd=self.root,
                                    capture_output=True, timeout=30, encoding="utf-8")
            if merged.returncode:
                raise RuntimeError("Framework content conflict: " + path)
            return mode, merged.stdout

    def clean(self):
        return not self.github.git("status", "--porcelain").output.strip()

    def prepare(self, target):
        data = provenance(self.root)
        if not data or not re.fullmatch(r"[0-9a-f]{40}", target or ""):
            raise ValueError("A recorded base and explicit 40-character target commit are required")
        if not self.clean():
            raise RuntimeError("Checkpoint local changes before applying a framework update")
        latest = self.fetch(data)
        if (self.github.git("merge-base", "--is-ancestor", data["base_commit"], target, check=False).returncode
                or self.github.git("merge-base", "--is-ancestor", target, latest, check=False).returncode):
            raise RuntimeError("Target is outside the recorded upstream history")
        head = self.github.git("rev-parse", "HEAD").output.strip()
        paths = [p for p in self.github.git("diff", "--name-only", data["base_commit"], target).output.splitlines() if managed(p)]
        candidate = config.private_dir(self.root) / "updates" / uuid.uuid4().hex
        candidate.parent.mkdir(exist_ok=True)
        self.github.git("worktree", "add", "--detach", str(candidate), head)
        try:
            for path in paths:
                file = candidate / path
                if any(p.is_symlink() for p in [file, *file.parents] if p.is_relative_to(candidate)):
                    raise RuntimeError("Framework update cannot traverse a symlink: " + path)
                value = self.merge_entry(path, self.entry(data["base_commit"], path), self.entry(head, path), self.entry(target, path))
                if value is None:
                    file.unlink(missing_ok=True)
                else:
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text(value[1], encoding="utf-8")
                    file.chmod(int(value[0], 8) & 0o777)
            config.atomic_json(candidate / MANIFEST, dict(data, base_commit=target))
            staged = GitHub(candidate, self.state)
            before = staged.workspace_digest()
            results, _ = checks.verify(candidate, {"commands": [], "kind": "framework"}, config.load(self.root), self.cancel, self.heartbeat)
            if not results or not all(r["passed"] for r in results) or self.cancel():
                raise RuntimeError("Framework candidate failed validation or was interrupted; source and runtime are unchanged")
            if before != staged.workspace_digest():
                raise RuntimeError("Validation modified the candidate source; review the tests before updating")
            staged.git("add", "-A")
            staged.scan_index()
            staged.git("commit", "-m", "feat: integrate base framework " + target[:12])
            return head, staged.git("rev-parse", "HEAD").output.strip(), results
        finally:
            self.github.git("worktree", "remove", "--force", str(candidate), check=False)

    def apply(self, target):
        if not self.state.get("paused", False) or self.state.get("active_run"):
            raise RuntimeError("Pause the instance and wait for its active attempt to stop before applying")
        head, candidate, results = self.prepare(target)
        if (self.cancel() or not self.state.get("paused", False) or self.state.get("active_run")
                or not self.clean() or self.github.git("rev-parse", "HEAD").output.strip() != head):
            raise RuntimeError("Instance changed while preparing the update; candidate was not activated")
        _, branch = self.github.identity()
        self.github.git("fetch", "origin", branch)
        if self.github.git("merge-base", "--is-ancestor", "FETCH_HEAD", candidate, check=False).returncode:
            raise RuntimeError("Remote instance branch diverged; reconcile before updating")
        # Confirm publication before touching the instance source or active runtime.
        self.github.git("push", "origin", f"{candidate}:refs/heads/{branch}")
        remote = self.github.git("ls-remote", "origin", f"refs/heads/{branch}").output.split()
        if not remote or remote[0] != candidate:
            raise RuntimeError("Framework checkpoint could not be confirmed; local runtime is unchanged")
        self.github.git("merge", "--ff-only", candidate)
        self.github.promote()
        release = deploy.activate(self.root)
        self.state.set("release", release)
        self.state.set("last_checks", results)
        self.state.set("framework", {"status": "current", "base_commit": target, "checked_at": time.time(),
                                    "commit": candidate, "message": "Validated update activated. Review the dashboard and resume when ready."})
        self.state.set("needs_checkpoint", True)
        return candidate

    def service(self):
        request = self.state.get("framework_request")
        last = self.state.get("framework_checked_at", 0)
        if not request and (time.time() - last < config.load(self.root)["framework_check_seconds"] or not (self.root / MANIFEST).exists()):
            return
        self.state.set("framework_checked_at", time.time())
        self.state.set("framework_request", None)  # Consume once, including interrupted apply requests.
        try:
            if request and request["action"] == "apply":
                self.state.set("framework", {"status": "applying", "target_commit": request["commit"],
                                              "message": "Preparing and validating a separate framework candidate."})
                self.apply(request["commit"])
            else:
                self.check()
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            self.state.set("framework", {"status": "attention", "checked_at": time.time(), "message": text(exc)})
