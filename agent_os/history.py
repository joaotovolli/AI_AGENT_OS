"""Bounded operational summaries, with compact per-goal Git exports."""
import json

from .config import atomic_json
from .redact import redact

BLOCKERS = ("none", "technical", "operator", "external", "quota", "authentication", "configuration", "unknown")


def text(value, limit=600):
    return " ".join(redact(str(value)).split())[:limit]


def diagnostic(work, checks=(), review=None):
    result = work.get("result", {})
    data = result.get("diagnostic", {})
    kind = data.get("blocker_kind", work.get("error_kind", "unknown"))
    if kind not in BLOCKERS:
        kind = "unknown"
    return {"phase": text(data.get("phase", "Unspecified"), 100),
            "approach_key": text(data.get("approach_key", ""), 100).lower(),
            "approach": text(data.get("approach", "")),
            "completed": text(data.get("completed", "")),
            "progress_made": data.get("progress_made") is True,
            "blocker_kind": kind, "blocker_key": text(data.get("blocker_key", ""), 100).lower(),
            "blocker": text(data.get("blocker", "")),
            "summary": text(result.get("summary", "Execution did not produce a valid result; inspect private diagnostics locally.")),
            "next_action": text(result.get("next_action", "Inspect the local execution error before retrying.")),
            "verification": ("review_passed" if review and review.get("ok") and review["result"]["status"] == "completed"
                             else "passed" if checks and all(c["passed"] for c in checks)
                             else "failed" if checks else "not_run")}


def export(root, state):
    for goal_id in state.dirty_histories():
        entries = state.history(goal_id, limit=None)
        groups = []
        for entry in entries:
            data = dict(entry["data"])
            count = data.pop("_range_count", 1)
            first_at = data.pop("_range_first_at", entry["at"])
            first_attempt = data.pop("_range_first_attempt", entry["attempt"])
            value = {"kind": entry["kind"], "data": data}
            if groups and groups[-1]["value"] == value:
                groups[-1].update(last_at=entry["at"], last_attempt=entry["attempt"], count=groups[-1]["count"] + count)
            else:
                groups.append({"value": value, "first_at": first_at, "last_at": entry["at"],
                               "first_attempt": first_attempt, "last_attempt": entry["attempt"], "count": count})
        directory = root / "docs" / "history" / goal_id
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for start in range(0, len(groups), 100):
            path = directory / f"{start // 100 + 1:04d}.json"
            value = {"format_version": 1, "goal_id": goal_id, "entries": groups[start:start + 100]}
            if not path.exists() or json.loads(path.read_text()) != value:
                atomic_json(path, value)
            files.append(path.name)
        (directory / "README.md").write_text(
            f"# Diagnostic history: {goal_id}\n\nOperational summaries in chronological order. "
            "Consecutive identical attempts are grouped with their count and time/attempt range. "
            "Raw commands, transcripts and reasoning traces are excluded.\n\n" +
            "\n".join(f"- [{name}]({name})" for name in files) + "\n", encoding="utf-8")
        state.set("history_exported:" + goal_id, entries[-1]["id"])


def restore(root, state):
    for goal in state.goals():
        for path in sorted((root / "docs" / "history" / goal["id"]).glob("[0-9]*.json")):
            chunk = json.loads(path.read_text())
            if chunk.get("format_version") != 1 or chunk.get("goal_id") != goal["id"]:
                raise ValueError("Invalid goal history: " + path.name)
            for index, group in enumerate(chunk["entries"]):
                data = dict(group["value"]["data"], _range_count=group["count"],
                            _range_first_at=group["first_at"], _range_first_attempt=group["first_attempt"])
                state.note(goal["id"], f"restored:{goal['id']}:{path.name}:{index}", group["value"]["kind"],
                           data, attempt=group["last_attempt"], at=group["last_at"])
