"""Codex exec adapter. Prompts use stdin; never shell interpolation."""
import json
import os
import selectors
import subprocess
import time
from pathlib import Path

from .config import GPT6_MODELS, atomic_json, private_dir
from .process import terminate
from .redact import redact
from .history import BLOCKERS
from . import strategy
from .progress import WORK_STATES, validate_plan
from .watchers import KINDS, validate_spec

DIAGNOSTIC = {"type": "object", "additionalProperties": False,
              "properties": {k: {"type": "string"} for k in
                             ("phase", "approach_key", "approach", "completed", "blocker_key", "blocker")}}
DIAGNOSTIC["properties"].update({"progress_made": {"type": "boolean"},
                                 "blocker_kind": {"type": "string", "enum": list(BLOCKERS)}})
DIAGNOSTIC["required"] = list(DIAGNOSTIC["properties"])
LEGACY_DIAGNOSTIC = frozenset(DIAGNOSTIC["required"])
DIAGNOSTIC["properties"].update({
    "observations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
    "next_check_at": {"type": "number"},
})
DIAGNOSTIC["required"] = list(DIAGNOSTIC["properties"])
WORK_ITEM = {"type": "object", "additionalProperties": False,
             "properties": {k: {"type": "string"} for k in ("key", "title", "criterion", "blocker_key", "evidence")}}
WORK_ITEM["properties"].update({"status": {"type": "string", "enum": list(WORK_STATES)},
                                  "depends_on": {"type": "array", "items": {"type": "string"}}})
WORK_ITEM["required"] = list(WORK_ITEM["properties"])
WATCHER = {"type": "object", "additionalProperties": False,
           "properties": {k: {"type": "string"} for k in ("key", "work_key", "path", "url", "field", "expected")}}
WATCHER["properties"].update({"kind": {"type": "string", "enum": list(KINDS)},
                                "predicate": {"type": "string", "enum": ["equals", "changed"]},
                                "interval_seconds": {"type": "integer"}, "lifetime_seconds": {"type": "integer"}})
WATCHER["required"] = list(WATCHER["properties"])

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["continue", "completed", "blocked"]},
        "summary": {"type": "string"},
        "progress": {"type": "integer", "minimum": 0, "maximum": 100},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
        "diagnostic": DIAGNOSTIC,
        "operator_reply": {"type": "string"},
        "work_plan": {"type": "array", "items": WORK_ITEM},
        "watchers": {"type": "array", "items": WATCHER},
        "strategies": {"type": "array", "items": strategy.SCHEMA},
    },
    "required": ["status", "summary", "progress", "evidence", "next_action", "diagnostic", "operator_reply", "work_plan", "watchers", "strategies"],
}


def validate_result(data):
    legacy = {"status", "summary", "progress", "evidence", "next_action"}
    if not isinstance(data, dict) or not legacy <= set(data) or set(data) - set(SCHEMA["required"]):
        raise ValueError("Incomplete Codex result")
    if data["status"] not in ("continue", "completed", "blocked"):
        raise ValueError("Invalid result status")
    if type(data["progress"]) is not int or not 0 <= data["progress"] <= 100:
        raise ValueError("Invalid result progress")
    if any(not isinstance(data[k], str) for k in ("summary", "next_action")):
        raise ValueError("Invalid result text")
    if not isinstance(data["evidence"], list) or any(not isinstance(e, str) for e in data["evidence"]):
        raise ValueError("Invalid result evidence")
    if "operator_reply" in data and (not isinstance(data["operator_reply"], str) or len(data["operator_reply"]) > 2000):
        raise ValueError("Invalid operator reply")
    if "diagnostic" in data:
        value = data["diagnostic"]
        if not isinstance(value, dict) or not LEGACY_DIAGNOSTIC <= set(value) or set(value) - set(DIAGNOSTIC["required"]):
            raise ValueError("Invalid diagnostic fields")
        if type(value["progress_made"]) is not bool or value["blocker_kind"] not in BLOCKERS:
            raise ValueError("Invalid diagnostic classification")
        if any(not isinstance(v, str) or len(v) > 2000 for k, v in value.items() if k in LEGACY_DIAGNOSTIC - {"progress_made"}):
            raise ValueError("Invalid diagnostic text")
        observations = value.get("observations", [])
        if not isinstance(observations, list) or len(observations) > 30 or any(
                not isinstance(o, dict) or set(o) != {"key", "value"} or
                any(not isinstance(v, str) or len(v) > 1000 for v in o.values()) for o in observations):
            raise ValueError("Invalid stable observations")
        import math
        next_check = value.get("next_check_at", 0)
        if type(next_check) not in (int, float) or not math.isfinite(next_check) or next_check < 0:
            raise ValueError("Invalid next useful check time")
    strategic = data.get("strategies", [])
    if not isinstance(strategic, list) or len(strategic) > 40:
        raise ValueError("Invalid strategic records")
    for record in strategic:
        strategy.validate(record)
    validate_plan(data.get("work_plan", []))
    watchers = data.get("watchers", [])
    if not isinstance(watchers, list) or len(watchers) > 10:
        raise ValueError("Invalid watchers")
    for watcher in watchers:
        validate_spec(watcher)
    return data


def command(config, root, schema, output, readonly=False, executable="codex"):
    if config.get("model") not in GPT6_MODELS:
        raise ValueError("Codex execution is restricted to supported GPT-6 models")
    args = [executable, "exec", "--json", "--color", "never", "--model", config["model"],
            "-c", 'model_reasoning_effort=' + json.dumps(config["reasoning"]),
            "-c", 'service_tier=' + json.dumps("fast" if config["fast"] else "default")]
    if readonly:
        args += ["--sandbox", "read-only", "-c", 'approval_policy="never"']
    else:
        args += ["--dangerously-bypass-approvals-and-sandbox"]
    return args + ["--cd", str(root), "--output-schema", str(schema), "--output-last-message", str(output), "-"]


def classify_error(text):
    lowered = text.lower()
    if any(s in lowered for s in ("usage limit", "rate limit", "quota", "insufficient_quota", "429", "credits")):
        return "quota"
    if any(s in lowered for s in ("unauthorized", "not logged in", "401", "authentication", "please log in")):
        return "authentication"
    if any(s in lowered for s in ("model not found", "not supported", "unsupported", "invalid model", "does not exist")):
        return "configuration"
    return "execution"


class Codex:
    def __init__(self, root, config, event, heartbeat=lambda: None, cancel=lambda: False, executable="codex"):
        self.root, self.config, self.event = Path(root), config, event
        self.heartbeat, self.cancel, self.executable = heartbeat, cancel, executable

    def run(self, prompt, run_id, readonly=False):
        directory = private_dir(self.root) / "runs" / run_id
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        schema, output = directory / "schema.json", directory / "result.json"
        atomic_json(schema, SCHEMA)
        output.unlink(missing_ok=True)
        args = command(self.config, self.root, schema, output, readonly, self.executable)
        usage = {}
        tail = bytearray()
        buffer = bytearray()
        error_messages = []
        timeout = self.config["verify_timeout_seconds"] if readonly else self.config["step_timeout_seconds"]
        last_beat = 0.0
        cancelled = timed_out = failed_event = False
        # Logs remain private, capped at 10 MiB per run. A small tail is kept for failure diagnosis.
        with (directory / "prompt.txt").open("w+") as stdin, (directory / "events.jsonl").open("wb") as log:
            os.chmod(directory / "prompt.txt", 0o600)
            os.chmod(directory / "events.jsonl", 0o600)
            stdin.write(prompt)
            stdin.flush()
            stdin.seek(0)
            process = subprocess.Popen(args, cwd=self.root, stdin=stdin, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            marker = private_dir(self.root) / "child.json"
            try:
                start_ticks = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                atomic_json(marker, {"pid": process.pid, "start_ticks": start_ticks})
            except OSError:
                pass
            selector = selectors.DefaultSelector()
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            start = time.monotonic()
            size = 0
            try:
                while selector.get_map():
                    cancelled = bool(self.cancel())
                    timed_out = time.monotonic() - start >= timeout
                    if cancelled or timed_out:
                        terminate(process)
                        break
                    if time.monotonic() - last_beat >= 2:
                        self.heartbeat()
                        last_beat = time.monotonic()
                    for key, _ in selector.select(timeout=0.2):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if size < 10 * 1024 * 1024:
                            log.write(chunk[:10 * 1024 * 1024 - size])
                            log.flush()
                        size += len(chunk)
                        tail.extend(chunk)
                        del tail[:-32000]
                        buffer.extend(chunk)
                        while b"\n" in buffer:
                            line, _, rest = buffer.partition(b"\n")
                            buffer = bytearray(rest)
                            try:
                                item = json.loads(line)
                                kind = item.get("type", "event")
                                if kind == "turn.completed":
                                    for k, v in item.get("usage", {}).items():
                                        if type(v) is int:
                                            usage[k] = usage.get(k, 0) + v
                                if kind in ("turn.failed", "error"):
                                    failed_event = True
                                    error_messages.append(json.dumps(item))
                                if kind.startswith("item."):
                                    subtype = item.get("item", {}).get("type", "activity")
                                    self.event(kind, subtype.replace("_", " "))
                                elif kind in ("turn.started", "turn.completed", "turn.failed", "thread.started"):
                                    self.event(kind, kind.replace(".", " "))
                            except (ValueError, AttributeError):
                                pass
                        if len(buffer) > 1024 * 1024:
                            buffer.clear()
                process.wait(timeout=5)
            finally:
                selector.close()
                if process.poll() is None:
                    terminate(process)
                process.stdout.close()
                marker.unlink(missing_ok=True)
        message = redact(("\n".join(error_messages) or tail.decode(errors="replace"))[-4000:])
        if cancelled:
            return {"ok": False, "error_kind": "cancelled", "error": "Execution interrupted by operator", "usage": usage}
        if timed_out:
            return {"ok": False, "error_kind": "timeout", "error": f"Iteration exceeded {timeout}s; goal will continue", "usage": usage}
        if process.returncode != 0 or failed_event:
            return {"ok": False, "error_kind": classify_error(message), "error": message, "usage": usage}
        try:
            result = validate_result(json.loads(output.read_text()))
        except (OSError, ValueError) as exc:
            return {"ok": False, "error_kind": "invalid_output", "error": str(exc), "usage": usage}
        return {"ok": True, "result": result, "usage": usage}
