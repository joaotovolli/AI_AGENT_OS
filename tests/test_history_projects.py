import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import config, deploy, history, projects
from agent_os.state import State


class HistoryProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = State(self.root)
        self.goal = self.state.add_goal("Build a report", "Create the report", "Verify totals", goal_id="report")

    def test_history_outlives_activity_and_compacts_repeated_attempts(self):
        for index in range(5):
            self.state.note("report", str(index), "attempt", {"phase": "Import", "blocker": "Input missing"}, attempt=index)
        with self.state.db() as db:
            db.executemany("INSERT INTO events (at,kind,message) VALUES (0,'noise','transient')", [()]*2010)
        self.state.event("activity", "Newest event")
        self.state.update_goal("report", status="cancelled")
        history.export(self.root, self.state)
        data = json.loads((self.root / "docs/history/report/0001.json").read_text())
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["count"], 5)
        self.assertEqual(len(self.state.history("report")), 5)
        self.assertEqual(self.state.dirty_histories(), [])

    def test_two_goals_restore_their_own_ranges_without_expanding_git_history(self):
        self.state.add_goal("Second", "Task", "Evidence", goal_id="second")
        for goal_id in ("report", "second"):
            for attempt in range(4):
                self.state.note(goal_id, goal_id+str(attempt), "attempt", {"summary": goal_id}, attempt=attempt, at=attempt+1)
        history.export(self.root, self.state)
        before = {p: p.read_text() for p in (self.root / "docs/history").glob("*/*.json")}
        with self.state.db() as db:
            db.execute("DELETE FROM history")
        history.restore(self.root, self.state)
        history.restore(self.root, self.state)
        for goal_id in ("report", "second"):
            self.assertEqual(len(self.state.history(goal_id)), 1)
            self.state.set("history_exported:"+goal_id, 0)
        history.export(self.root, self.state)
        self.assertEqual(before, {p: p.read_text() for p in before})

    def test_sanitization_deduplication_and_safe_goal_paths(self):
        secret = "ghp_" + "a"*30
        self.state.note("report", "one", "attempt", {"summary": secret, "raw": {"output": "excluded"}})
        self.state.note("report", "one", "attempt", {"summary": "duplicate"})
        data = self.state.history("report")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["data"], {"summary": "[REDACTED]"})
        with self.assertRaises(ValueError):
            self.state.add_goal("Bad", "Task", "Evidence", goal_id="../escape")

    def test_blocked_goal_preserves_queue_priority(self):
        self.state.update_goal("report", status="blocked")
        self.state.add_goal("Later", "Task", "Evidence")
        self.state.add_goal("Idle", "Task", "Evidence", kind="maintenance")
        self.assertIsNone(self.state.select_goal())
        self.state.ensure_bootstrap()
        self.state.update_goal("bootstrap", status="blocked")
        self.assertIsNone(self.state.select_goal())

    def test_project_registration_does_not_enter_core_runtime(self):
        directory = self.root / "workspace/viewer"
        directory.mkdir(parents=True)
        (self.root / "agent_os").mkdir()
        (self.root / "agent_os/__init__.py").write_text("VERSION=1\n")
        before = deploy.fingerprint(self.root)
        data = {"name": "Report viewer", "url": "http://localhost:8800", "status": "ready", "goal_id": "report"}
        projects.register(self.root, "workspace/viewer", data)
        (directory / "server.py").write_text("raise RuntimeError('must never import')\n")
        self.assertEqual(projects.discover(self.root)[0]["url"], data["url"])
        self.assertEqual(deploy.fingerprint(self.root), before)
        deploy.activate(self.root)
        self.assertFalse((config.private_dir(self.root) / "runtime/workspace").exists())

    def test_project_metadata_rejects_credentials_control_port_and_escapes(self):
        (self.root / "workspace/viewer").mkdir(parents=True)
        urls = ["javascript:alert(1)", "http://localhost:8765", "https://example.test/#private",
                "https://example.test/?key=value", "http://example.test", "http://localhost:bad",
                "https://" + "user:password" + "@example.test", "https://example.test/\n"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                projects.register(self.root, "workspace/viewer", {"name": "Viewer", "url": url})
        outside = self.root.parent / "outside"
        (self.root / "workspace/escape").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            projects.register(self.root, "workspace/escape", {"name": "Escape"})
        (self.root / "workspace/viewer/project.json").write_text("invalid JSON")
        self.assertEqual(projects.discover(self.root), [])

    def test_feature_settings_preserve_legacy_runtime_compatibility(self):
        settings = config.save(self.root, {"diagnostic_escalation": True, "github_followups": True})
        legacy = json.loads((config.private_dir(self.root) / "config.json").read_text())
        self.assertEqual(set(legacy), config.LEGACY_SETTINGS)
        self.assertEqual(config.load(self.root), settings)
        for bad in ({"diagnostic_escalation": "yes"}, {"github_operators": ["not/a/login"]},
                    {"diagnostic_models": [{"model": "worker"}]}, {"diagnostic_timeout_seconds": 900}):
            with self.assertRaises(ValueError):
                config.save(self.root, bad)

    def test_catalog_metadata_is_optional_and_malformed_cache_fails_closed(self):
        cache = self.root / "models_cache.json"
        with patch.dict("os.environ", {"CODEX_HOME": str(self.root)}):
            for value in ([], {"models": None}, {"models": [{"slug": "gpt-6-luna", "supported_reasoning_levels": None}]}):
                cache.write_text(json.dumps(value))
                choices = config.available_models()
                self.assertFalse(choices and choices[0]["reasoning"])
            cache.write_text(json.dumps({"models": [{"slug": "gpt-6-luna", "supported_reasoning_levels": [{"effort": "high"}],
                                                    "upgrade": {"model": "gpt-6-sol"}}]}))
            self.assertEqual(config.available_models()[0]["upgrade"], "gpt-6-sol")
            self.assertEqual(config.available_models()[0]["reasoning"], ["high"])
