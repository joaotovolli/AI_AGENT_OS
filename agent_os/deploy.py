"""Activate tested runtime snapshots without executing half-written source files."""
import hashlib
import os
import shutil
from pathlib import Path

from .config import private_dir


def fingerprint(root):
    digest = hashlib.sha256()
    for path in sorted((Path(root) / "agent_os").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:20]


def activate(root):
    root = Path(root)
    local = private_dir(root)
    digest = fingerprint(root)
    release = local / "releases" / digest
    active = local / "runtime"
    if active.is_symlink() and active.resolve() == release:
        return digest
    release.parent.mkdir(exist_ok=True)
    if not release.exists():
        staging = release.with_name(digest + ".tmp")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        shutil.copytree(root / "agent_os", staging / "agent_os", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        os.replace(staging, release)
    if active.is_symlink():
        old = active.resolve()
        previous = local / "previous-runtime"
        previous_temp = local / "previous-runtime.tmp"
        previous_temp.unlink(missing_ok=True)
        previous_temp.symlink_to(old, target_is_directory=True)
        os.replace(previous_temp, previous)
    temp = local / "runtime.tmp"
    temp.unlink(missing_ok=True)
    temp.symlink_to(release, target_is_directory=True)
    os.replace(temp, active)
    return digest


def current(root):
    return str((private_dir(root) / "runtime").resolve())
