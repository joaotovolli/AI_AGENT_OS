#!/usr/bin/env python3
"""Create a fresh private GitHub repository from tracked template files."""
import argparse
import io
import re
import shutil
import subprocess
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", help="owner/AI_AGENT_OS_1")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise SystemExit("Use owner/repository")
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise SystemExit("Destination already exists; choose an empty new path")
    source = Path(__file__).resolve().parent.parent
    subprocess.run(["gh", "auth", "status"], check=True)
    archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=source)
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")
    for folder in ("state", "docs/evidence"):
        shutil.rmtree(destination / folder, ignore_errors=True)
    (destination / "STATUS.md").write_text("# Instance status\n\nFresh instance. WSL2 bootstrap has not run yet.\n")
    (destination / "docs" / "ACCESS.md").write_text("# Access\n\nRun the WSL2 installer; it generates access instructions for this instance.\n")
    for command in (["git", "init", "-b", "main"], ["git", "add", "."],
                    ["git", "commit", "-m", "feat: initialize reusable AI Agent OS instance"],
                    ["gh", "repo", "create", args.repository, "--private", "--source", ".", "--remote", "origin", "--push"]):
        subprocess.run(command, cwd=destination, check=True)
    print(f"Created https://github.com/{args.repository}")
    print(f"Install from {destination} with a distinct port, for example: bash scripts/install-wsl.sh 8766")


if __name__ == "__main__":
    main()
