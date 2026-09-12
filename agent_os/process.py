"""Bounded subprocesses with group cancellation, including descendants."""
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass


@dataclass
class ProcessResult:
    returncode: int
    output: str
    cancelled: bool = False
    timed_out: bool = False


def terminate(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The leader can exit before its descendants. Kill the group in either case.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run(args, cwd, timeout=120, input_text=None, cancel=lambda: False, heartbeat=lambda: None, env=None):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as stdin:
        if input_text is not None:
            stdin.write(input_text.encode())
            stdin.seek(0)
        process = subprocess.Popen(args, cwd=cwd, stdin=stdin, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True, env=env)
        started = time.monotonic()
        cancelled = timed_out = False
        try:
            while process.poll() is None:
                cancelled = bool(cancel())
                timed_out = time.monotonic() - started > timeout
                if cancelled or timed_out:
                    terminate(process)
                    break
                heartbeat()
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                terminate(process)
        output.seek(0, 2)
        length = output.tell()
        output.seek(max(0, length - 128000))
        return ProcessResult(process.returncode, output.read().decode(errors="replace"), cancelled, timed_out)
