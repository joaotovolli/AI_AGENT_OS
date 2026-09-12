"""Conservative prevention of common credential leaks; not a universal DLP system."""
import re
from pathlib import PurePosixPath

PATTERNS = [
    re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"(?i)(?:bearer\s+)[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"(?i)(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[:=]\s*[\"']?[^\s\"',;]{8,}"),
    re.compile(r"https?://[^\s/:]+:[^\s/@]+@[^\s]+"),
]


def redact(text):
    for pattern in PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def secret_path(path):
    parts = PurePosixPath(path).parts
    name = parts[-1].lower() if parts else ""
    return (any(p in (".agent-os", ".ssh", ".aws", ".codex", "node_modules", ".venv") for p in parts)
            or (name.startswith(".env") and name != ".env.example")
            or name in ("auth.json", "credentials.json", "id_rsa", "id_ed25519")
            or name.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite3", ".db")))
