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
LEGACY_SETTINGS = frozenset(DEFAULTS)
DEFAULTS.update({
    "github_followups": False, "github_operators": [],
    "diagnostic_escalation": False, "diagnostic_models": [],
    "diagnostic_min_attempts": 3, "diagnostic_cooldown_seconds": 3600,
    "diagnostic_timeout_seconds": 180, "framework_check_seconds": 86400,
})
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
    for key in ("fast", "github_followups", "diagnostic_escalation"):
        if key in data and type(data[key]) is not bool:
            raise ValueError(f"{key} must be true or false")
    if "github_operators" in data:
        users = data["github_operators"]
        if not isinstance(users, list) or len(users) > 20 or any(
                not isinstance(u, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", u) for u in users):
            raise ValueError("github_operators must contain up to 20 GitHub logins")
    if "diagnostic_models" in data:
        models = data["diagnostic_models"]
        if not isinstance(models, list) or len(models) > 5:
            raise ValueError("Use up to five ordered diagnostic model preferences")
        for model in models:
            if not isinstance(model, dict) or set(model) != {"model", "reasoning"}:
                raise ValueError("Each diagnostic preference requires model and reasoning")
            validate(model)
    limits = {"port": (1024, 65535), "idle_seconds": (60, 86400),
              "step_timeout_seconds": (30, 86400), "verify_timeout_seconds": (10, 7200),
              "retry_base_seconds": (1, 3600), "retry_max_seconds": (60, 86400),
              "github_progress_seconds": (30, 3600), "diagnostic_min_attempts": (3, 20),
              "diagnostic_cooldown_seconds": (300, 86400), "diagnostic_timeout_seconds": (30, 600),
              "framework_check_seconds": (3600, 604800)}
    for key, (low, high) in limits.items():
        if key in data and (type(data[key]) is not int or not low <= data[key] <= high):
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    return data


def load(root):
    path = private_dir(root) / "config.json"
    with _LOCK:
        overrides = json.loads(path.read_text()) if path.exists() else {}
        features = private_dir(root) / "features.json"
        if features.exists():
            overrides.update(json.loads(features.read_text()))
        return dict(DEFAULTS, **validate(overrides))


def save(root, updates):
    with _LOCK:
        config = load(root)
        config.update(validate(updates))
        # Retained pre-feature runtimes reject unknown keys. Keep their configuration readable.
        atomic_json(private_dir(root) / "config.json", {k: v for k, v in config.items() if k in LEGACY_SETTINGS})
        atomic_json(private_dir(root) / "features.json", {k: v for k, v in config.items() if k not in LEGACY_SETTINGS})
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
        models = data.get("models", []) if isinstance(data, dict) else []
        if not isinstance(models, list):
            return []
        result = []
        for m in models:
            if not isinstance(m, dict) or not (m.get("slug") or m.get("id")):
                continue
            levels = m.get("supported_reasoning_levels", m.get("supported_reasoning_efforts", []))
            if not isinstance(levels, list):
                levels = []
            upgrade = m.get("upgrade") or {}
            result.append({"id": m.get("slug", m.get("id")),
                           "name": m.get("display_name", m.get("slug", m.get("id"))),
                           "reasoning": [v.get("effort") if isinstance(v, dict) else v for v in levels
                                         if isinstance(v, (dict, str))],
                           "default_reasoning": m.get("default_reasoning_level", "medium"),
                           "upgrade": upgrade.get("model") if isinstance(upgrade, dict) else None})
        return result
    except (OSError, ValueError, AttributeError):
        return []
