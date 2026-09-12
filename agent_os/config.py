"""Instance-local configuration. No changes to the user's global Codex config."""
import json
import os
import re
import secrets
import threading
from pathlib import Path

DEFAULTS = {
    "model": "gpt-5.6-luna", "reasoning": "medium", "fast": False,
    "port": 8765, "idle_seconds": 3600, "step_timeout_seconds": 1800,
    "verify_timeout_seconds": 600, "retry_base_seconds": 15,
    "retry_max_seconds": 3600, "github_progress_seconds": 60,
}
_LOCK = threading.RLock()


def private_dir(root):
    path = Path(root) / ".agent-os"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(5) + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as out:
            os.chmod(temp, 0o600)
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate(data):
    unknown = set(data) - set(DEFAULTS)
    if unknown:
        raise ValueError("Unknown settings: " + ", ".join(sorted(unknown)))
    for key in ("model", "reasoning"):
        if key in data and (not isinstance(data[key], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}", data[key])):
            raise ValueError(f"Invalid {key}")
    if "fast" in data and type(data["fast"]) is not bool:
        raise ValueError("fast must be true or false")
    limits = {"port": (1024, 65535), "idle_seconds": (60, 86400),
              "step_timeout_seconds": (30, 86400), "verify_timeout_seconds": (10, 7200),
              "retry_base_seconds": (1, 3600), "retry_max_seconds": (60, 86400),
              "github_progress_seconds": (30, 3600)}
    for key, (low, high) in limits.items():
        if key in data and (type(data[key]) is not int or not low <= data[key] <= high):
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    return data


def load(root):
    path = private_dir(root) / "config.json"
    with _LOCK:
        overrides = json.loads(path.read_text()) if path.exists() else {}
        return dict(DEFAULTS, **validate(overrides))


def save(root, updates):
    with _LOCK:
        config = load(root)
        config.update(validate(updates))
        atomic_json(private_dir(root) / "config.json", config)
        return config


def token(root):
    path = private_dir(root) / "dashboard.token"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    value = secrets.token_urlsafe(32)
    with os.fdopen(fd, "w") as out:
        out.write(value)
    return value


def available_models():
    """Read only the non-secret Codex catalog cache; never read auth.json."""
    codex_dir = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    try:
        data = json.loads((codex_dir / "models_cache.json").read_text())
        models = data.get("models", [])
        return [{"id": m.get("slug", m.get("id")),
                 "name": m.get("display_name", m.get("slug", m.get("id")))}
                for m in models if isinstance(m, dict) and (m.get("slug") or m.get("id"))]
    except (OSError, ValueError, AttributeError):
        return []
