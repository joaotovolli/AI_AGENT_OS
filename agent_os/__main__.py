"""Local administration entry point. Run from the repository root."""
import argparse
import fcntl
import json
import os
import subprocess
from pathlib import Path

from . import config, deploy, history, projects
from .state import State


def initialize(root, port=None):
    from .github import GitHub
    root = Path(root).resolve()
    state = State(root)
    if port is not None:
        config.save(root, {"port": port})
    else:
        config.save(root, {})
    config.token(root)
    github = GitHub(root, state)
    repo, branch = github.identity()
    stable = github.gh(f"repos/{repo}")["default_branch"]
    state.set("stable_branch", stable)
    # A dedicated branch stores every attempt, including experiments that fail checks.
    if branch == stable:
        work_branch = "agent/" + root.name
        exists = github.git("show-ref", "--verify", "--quiet", "refs/heads/" + work_branch, check=False).returncode == 0
        github.git("switch", work_branch) if exists else github.git("switch", "-c", work_branch)
        github.git("push", "-u", "origin", work_branch)
    state.ensure_bootstrap()
    state.set("release", deploy.activate(root))
    return state


def main():
    parser = argparse.ArgumentParser(description="AI Agent OS")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--port", type=int)
    commands.add_parser("worker")
    commands.add_parser("serve")
    commands.add_parser("status")
    commands.add_parser("open")
    commands.add_parser("doctor")
    commands.add_parser("restore")
    settings = commands.add_parser("settings")
    settings.add_argument("--json", help="JSON object of instance settings to save")
    project = commands.add_parser("project")
    project.add_argument("action", choices=("list", "register"))
    project.add_argument("--path")
    project.add_argument("--name")
    project.add_argument("--description", default="")
    project.add_argument("--url", default="")
    project.add_argument("--goal", default="")
    project.add_argument("--status", default="building", choices=("building", "ready", "stopped"))
    framework = commands.add_parser("framework")
    framework.add_argument("action", choices=("check", "apply", "adopt"))
    framework.add_argument("--commit")
    framework.add_argument("--repository")
    framework.add_argument("--branch", default="main")
    progress = commands.add_parser("progress")
    progress.add_argument("--goal", required=True)
    progress.add_argument("--percent", type=int, required=True)
    progress.add_argument("--summary", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "init":
        initialize(root, args.port)
        print("Initialized. Install the two services with scripts/install-wsl.sh.")
    elif args.command == "worker":
        from .worker import Worker
        Worker(root).run()
    elif args.command == "serve":
        from .server import serve
        serve(root)
    elif args.command == "status":
        print(json.dumps(State(root).snapshot(), indent=2))
    elif args.command == "settings":
        before = config.load(root)
        value = config.save(root, json.loads(args.json)) if args.json else before
        state = State(root)
        if value["github_followups"] and not before["github_followups"]:
            import time
            state.set("operator_enabled_since", time.time())
            state.set("operator_cursor", None)
        state.set("needs_checkpoint", True)
        print(json.dumps(value, indent=2))
    elif args.command == "project":
        if args.action == "list":
            print(json.dumps(projects.discover(root), indent=2))
        else:
            if not args.path or not args.name:
                raise SystemExit("Project registration requires --path and --name")
            state = State(root)
            if args.goal and not state.goal(args.goal):
                raise SystemExit("Project goal does not exist")
            value = projects.register(root, args.path, {"name": args.name, "description": args.description,
                                      "url": args.url, "goal_id": args.goal, "status": args.status})
            state.set("needs_checkpoint", True)
            print(json.dumps(value, indent=2))
    elif args.command == "framework":
        from .framework import Framework, MANIFEST, provenance
        from .github import GitHub, repo_name
        with (config.private_dir(root) / "worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit("The worker owns this instance. Use the dashboard or stop the worker service first.")
            state = State(root)
            updater = Framework(root, state)
            if args.action == "adopt":
                import re
                if provenance(root) or not args.repository or not re.fullmatch(r"[0-9a-f]{40}", args.commit or ""):
                    raise SystemExit("Adoption requires an unconfigured instance, --repository and its known original --commit")
                repo_name("https://github.com/" + args.repository + ".git")
                git = GitHub(root, state)
                git.git("check-ref-format", "--branch", args.branch)
                data = {"format_version": 1, "repository": args.repository, "base_commit": args.commit, "branch": args.branch}
                latest = updater.fetch(data)
                git.git("merge-base", "--is-ancestor", args.commit, latest)
                config.atomic_json(root / MANIFEST, data)
                state.set("needs_checkpoint", True)
                print("Provenance recorded. Review and checkpoint this file before applying an update.")
            elif args.action == "check":
                print(json.dumps(updater.check(), indent=2))
            else:
                state.set("paused", True)
                print("Activated framework checkpoint " + updater.apply(args.commit) + ". Review the dashboard before resuming.")
    elif args.command == "open":
        settings = config.load(root)
        url = f"http://localhost:{settings['port']}/#token={config.token(root)}"
        # Fragment is consumed by browser JavaScript and never sent in an HTTP request.
        if os.environ.get("WSL_DISTRO_NAME"):
            import base64
            script = "Start-Process '" + url + "'"
            encoded = base64.b64encode(script.encode("utf-16le")).decode()
            subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded], check=True)
        else:
            import webbrowser
            webbrowser.open(url)
    elif args.command == "progress":
        from .redact import redact
        state = State(root)
        goal = state.goal(args.goal)
        if not goal or goal["status"] != "running":
            raise SystemExit("Progress requires a currently running goal")
        if not 0 <= args.percent <= 100:
            raise SystemExit("Percentage must be 0..100")
        state.update_goal(args.goal, progress=min(99, args.percent), summary=redact(args.summary)[:4000])
        state.event("goal.progress", args.summary, args.goal)
    elif args.command == "restore":
        from .github import GitHub
        state = State(root)
        data = json.loads((root / "state" / "checkpoint.json").read_text())
        repo, _ = GitHub(root, state).identity()
        if data.get("repository") != repo:
            raise SystemExit("Checkpoint belongs to a different repository; start a fresh instance")
        if state.goals():
            raise SystemExit("Restore requires an empty local database")
        config.save(root, data["settings"])
        for item in data["goals"]:
            state.add_goal(item["title"], item["description"], item["acceptance"], item["commands"], item["kind"], item["id"])
            status = item["status"] if item["status"] in ("completed", "cancelled") else "queued"
            if item["kind"] == "bootstrap":
                status = "queued"  # A recovered host must prove readiness again.
            state.update_goal(item["id"], status=status, attempts=item["attempts"], progress=min(item["progress"], 99) if status == "queued" else item["progress"], summary=item["summary"])
        state.set("ready", False)
        history.restore(root, state)
        pending = []
        for receipt in data.get("followup_receipts", []):
            if receipt["status"] != "handled":
                pending.append(receipt["received"])
                continue
            state.receive_followup(repo, receipt["issue"], receipt["comment"], "", "", receipt.get("goal_id"), receipt["received"])
            with state.db() as db:
                db.execute("UPDATE followups SET status='handled',acknowledged=1,answered=1 WHERE id=?", (receipt["id"],))
        if data.get("checkpoint_at"):
            state.set("operator_enabled_since", min(pending) - 1 if pending else data["checkpoint_at"])
            state.set("operator_cursor", None)
        print("Checkpoint restored; bootstrap will validate this host again.")
    elif args.command == "doctor":
        from .process import run
        settings = config.load(root)
        failures = []
        for name, argv in [("Python", ["python3", "--version"]), ("Git", ["git", "--version"]),
                           ("GitHub authentication", ["gh", "auth", "status"]),
                           ("Codex CLI", ["codex", "--version"]), ("Codex authentication", ["codex", "login", "status"]),
                           ("Unattended sudo", ["sudo", "-n", "true"])]:
            try:
                ok = run(argv, root, timeout=20).returncode == 0
            except OSError:
                ok = False
            print(("PASS " if ok else "FAIL ") + name)
            if not ok:
                failures.append(name)
        print(f"Model: {settings['model']}, reasoning: {settings['reasoning']}, Fast: {settings['fast']}")
        print("Dashboard: http://localhost:" + str(settings["port"]))
        raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
