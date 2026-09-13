"""Discover project links without importing or executing generated project code."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .config import atomic_json, load
from .redact import PATTERNS


def validate(root, path, data):
    root, path = Path(root).resolve(), Path(path)
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "workspace" or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", path.name):
        raise ValueError("Project path must be workspace/<project-name>")
    directory = root / path
    if directory.is_symlink() or (root / "workspace").is_symlink() or not directory.is_dir() or not directory.resolve().is_relative_to(root):
        raise ValueError("Project must be an existing directory inside this instance")
    if not isinstance(data, dict) or set(data) - {"name", "description", "url", "goal_id", "status"}:
        raise ValueError("Invalid project metadata")
    for key, limit in (("name", 120), ("description", 500), ("url", 500), ("goal_id", 64), ("status", 20)):
        if not isinstance(data.get(key, ""), str) or len(data.get(key, "")) > limit:
            raise ValueError("Invalid project " + key)
    if not data.get("name", "").strip() or data.get("status", "building") not in ("building", "ready", "stopped"):
        raise ValueError("Project requires a name and building, ready or stopped status")
    if data.get("goal_id") and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", data["goal_id"]):
        raise ValueError("Invalid project goal ID")
    url = data.get("url", "")
    if url:
        parsed = urlsplit(url)
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(ord(c) < 33 for c in url) or "\\" in url
                or (not local and parsed.scheme != "https")
                or (local and parsed.port == load(root)["port"])):
            raise ValueError("Use a separate project URL without credentials, query parameters or fragments")
    if any(p.search(json.dumps(data)) for p in PATTERNS):
        raise ValueError("Project metadata must not contain credentials")
    return dict(data, path=path.as_posix())


def discover(root):
    found = []
    for manifest in sorted((Path(root) / "workspace").glob("*/project.json")):
        try:
            if manifest.is_symlink() or manifest.stat().st_size > 8192:
                continue
            found.append(validate(root, manifest.parent.relative_to(root), json.loads(manifest.read_text())))
        except (OSError, ValueError):
            continue
    return found


def register(root, path, data):
    result = validate(root, path, data)
    atomic_json(Path(root) / path / "project.json", data)
    return result
