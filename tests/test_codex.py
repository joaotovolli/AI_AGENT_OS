import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from agent_os.codex import Codex, command, classify_error, validate_result
from agent_os.config import DEFAULTS
from agent_os.process import run

FAKE = '''#!/usr/bin/env python3
import json, pathlib, sys, time
prompt = sys.stdin.read()
if prompt == "quota":
    print(json.dumps({"type":"error","message":"usage limit reached"}), flush=True)
    sys.exit(1)
if prompt == "slow":
    print(json.dumps({"type":"turn.started"}), flush=True)
    time.sleep(60)
if prompt == "invalid":
    pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text("{}")
    sys.exit(0)
print(json.dumps({"type":"item.completed","item":{"type":"command_execution","command":"private command","output":"private output"}}), flush=True)
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}), flush=True)
result = {"status":"completed","summary":"Verified test result","progress":100,"evidence":["report.md"],"next_action":""}
pathlib.Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(result))
'''


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fake = self.root / "fake-codex"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o700)
        self.events = []

    def adapter(self, **kw):
        return Codex(self.root, dict(DEFAULTS), lambda *e: self.events.append(e), executable=str(self.fake), **kw)

    def test_real_subprocess_jsonl_and_structured_completion(self):
        result = self.adapter().run("test", "normal")
        self.assertTrue(result["ok"])
        self.assertEqual(result["usage"]["input_tokens"], 12)
        self.assertEqual(result["result"]["status"], "completed")
        self.assertNotIn("private output", str(self.events))
        self.assertFalse((self.root / ".agent-os/child.json").exists())

    def test_quota_is_reported_for_scheduled_retry(self):
        result = self.adapter().run("quota", "quota")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "quota")

    def test_invalid_success_output_is_not_accepted(self):
        result = self.adapter().run("invalid", "invalid")
        self.assertEqual(result["error_kind"], "invalid_output")

    def test_pause_interrupts_running_child(self):
        started = time.monotonic()
        result = self.adapter(cancel=lambda: time.monotonic()-started > 0.3).run("slow", "slow")
        self.assertEqual(result["error_kind"], "cancelled")
        self.assertLess(time.monotonic()-started, 8)

    def test_timeout_kills_process_and_returns(self):
        started = time.monotonic()
        result = run([sys.executable, "-c", "import time;time.sleep(60)"], self.root, timeout=0.3)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic()-started, 8)

    def test_model_fast_and_permissions_are_explicit(self):
        settings = dict(DEFAULTS, model="gpt-6-astra", reasoning="high", fast=True)
        args = command(settings, self.root, "schema", "output")
        self.assertIn('service_tier="fast"', args)
        self.assertIn('model_reasoning_effort="high"', args)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", args)
        review = command(settings, self.root, "schema", "output", readonly=True)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", review)
        self.assertIn("read-only", review)
        self.assertEqual(args[-1], "-")
        settings["fast"] = False
        self.assertIn('service_tier="default"', command(settings, self.root, "schema", "output"))

    def test_execution_command_rejects_every_non_gpt6_model(self):
        settings = dict(DEFAULTS, model="gpt-5.6-luna")
        with self.assertRaisesRegex(ValueError, "GPT-6"):
            command(settings, self.root, "schema", "output")

    def test_failure_classification(self):
        self.assertEqual(classify_error("401 unauthorized"), "authentication")
        self.assertEqual(classify_error("Model not supported"), "configuration")

    def test_result_schema_rejects_boolean_progress(self):
        with self.assertRaises(ValueError):
            validate_result({"status":"completed","summary":"x","progress":True,"evidence":["x"],"next_action":""})
