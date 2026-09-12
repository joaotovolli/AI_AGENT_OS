"""Independent deterministic gates, executed outside the working Codex turn."""
import json
import sys
import time
import urllib.request
from pathlib import Path

from .config import private_dir
from .process import run
from .redact import redact


def verify(root, goal, config, cancel=lambda: False, heartbeat=lambda: None):
    root = Path(root)
    checks = []
    log = private_dir(root) / "verification.txt"
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]]
    names = ["Regression suite"]
    for number, command in enumerate(goal["commands"], start=1):
        commands.append(["bash", "-lc", command])
        names.append(f"Goal acceptance command {number}")
    with log.open("w") as out:
        for name, command in zip(names, commands):
            result = run(command, root, timeout=config["verify_timeout_seconds"], cancel=cancel, heartbeat=heartbeat)
            passed = result.returncode == 0 and not result.cancelled and not result.timed_out
            if name == "Regression suite" and ("Ran 0 tests" in result.output or "Ran " not in result.output):
                passed = False
            checks.append({"name": name, "passed": passed, "at": time.time()})
            out.write(f"\n{name}\n{result.output}\n")
            if result.cancelled:
                break
    if goal["kind"] == "bootstrap":
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{config['port']}/healthz", timeout=5) as response:
                healthy = json.load(response).get("ok") is True
        except (OSError, ValueError):
            healthy = False
        checks.append({"name": "Live dashboard", "passed": healthy, "at": time.time()})
        # The stable launcher records both processes. Validate systemd, not just unit files.
        manifest = private_dir(root) / "installation.json"
        installed = json.loads(manifest.read_text()) if manifest.exists() else {}
        for service in installed.get("services", []):
            result = run(["systemctl", "--user", "is-active", service], root, timeout=10)
            checks.append({"name": service, "passed": result.returncode == 0, "at": time.time()})
        checks.append({"name": "Persistent service installation", "passed": len(installed.get("services", [])) == 2, "at": time.time()})
    return checks, redact(log.read_text()[-24000:])
