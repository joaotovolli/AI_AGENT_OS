#!/usr/bin/env python3
"""Stable, dependency-free service launcher, copied outside editable source on install."""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def clean_orphan(root):
    marker = root / ".agent-os" / "child.json"
    try:
        child = json.loads(marker.read_text())
        stat = Path(f"/proc/{child['pid']}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[19] == child["start_ticks"]:
            os.killpg(child["pid"], signal.SIGKILL)
    except (OSError, ValueError, KeyError, IndexError):
        pass
    marker.unlink(missing_ok=True)


def main():
    root = Path(sys.argv[1]).resolve()
    mode = sys.argv[2]
    if mode not in ("worker", "serve"):
        raise SystemExit("Expected worker or serve")
    local = root / ".agent-os"
    lock = (local / ("launcher-" + mode + ".lock")).open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopping = False
    child = None
    def stop(*_):
        nonlocal stopping
        stopping = True
        if child and child.poll() is None:
            child.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    failures = 0
    while not stopping:
        if mode == "worker":
            clean_orphan(root)
        release = (local / "runtime").resolve()
        started = time.monotonic()
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONUNBUFFERED"] = "1"
        child = subprocess.Popen([sys.executable, "-m", "agent_os", "--root", str(root), mode], cwd=release, env=environment)
        while child.poll() is None:
            if stopping:
                try:
                    child.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    child.kill()
                break
            time.sleep(0.5)
        code = child.wait()
        if mode == "worker":
            clean_orphan(root)
        if stopping:
            break
        failures = failures + 1 if code and time.monotonic() - started < 30 else 0
        if failures >= 3 and (local / "previous-runtime").is_symlink():
            previous = (local / "previous-runtime").resolve()
            if previous != release and previous.exists():
                temp = local / ("rollback-" + mode)
                temp.unlink(missing_ok=True)
                temp.symlink_to(previous, target_is_directory=True)
                os.replace(temp, local / "runtime")
                with (local / "recovery.log").open("a") as out:
                    out.write(f"{time.time()}: {mode} startup failed; restored runtime {previous.name}\n")
            failures = 0
        for _ in range(3):
            if stopping:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
