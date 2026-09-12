"""Local administration entry point. Run from the repository root."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from . import config, deploy
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
