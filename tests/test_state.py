import tempfile
import time
import unittest
from pathlib import Path

from agent_os import config
from agent_os.state import State
from agent_os.worker import completion_allowed, retry_delay


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = State(self.root)

    def test_bootstrap_gates_user_goals_and_is_idempotent(self):
        self.state.add_goal("User goal", "Do something", "Evidence exists")
        self.state.ensure_bootstrap()
        self.state.ensure_bootstrap()
        self.assertEqual(len(self.state.goals()), 2)
        self.assertEqual(self.state.select_goal()["id"], "bootstrap")
        self.state.update_goal("bootstrap", next_run=time.time() + 100)
        self.assertIsNone(self.state.select_goal())

    def test_crash_recovery_preserves_attempts(self):
        goal = self.state.add_goal("Goal", "Work", "Verified")
        run = self.state.begin_run(goal["id"])
        new = State(self.root)
        new.recover()
        self.assertEqual(new.goal(goal["id"])["status"], "queued")
        self.assertEqual(new.goal(goal["id"])["attempts"], 1)
        with new.db() as db:
            self.assertEqual(db.execute("SELECT status FROM runs WHERE id=?", (run,)).fetchone()[0], "interrupted")

    def test_active_user_backoff_blocks_idle_maintenance(self):
        user = self.state.add_goal("User", "Work", "Verify")
        self.state.update_goal(user["id"], status="waiting", next_run=time.time()+3600)
        self.state.add_goal("Maintenance", "Check", "Pass", kind="maintenance")
        self.assertIsNone(self.state.select_goal())

    def test_cancellation_is_persistent(self):
        goal = self.state.add_goal("Goal", "Work", "Verify")
        self.state.update_goal(goal["id"], status="cancelled")
        self.assertIsNone(State(self.root).select_goal())

    def test_invalid_goals_rejected(self):
        for title, commands in [("", []), ("Valid", "rm -rf x"), ("Valid", [5])]:
            with self.assertRaises(ValueError):
                self.state.add_goal(title, "Work", "Verify", commands)

    def test_settings_validation_and_roundtrip(self):
        self.assertEqual(config.load(self.root)["model"], "gpt-5.6-luna")
        config.save(self.root, {"model": "custom-model-2027", "reasoning": "medium", "fast": True})
        self.assertTrue(config.load(self.root)["fast"])
        for update in ({"port": True}, {"fast": "false"}, {"model": "abc; bad"}, {"unknown": 1}, {"idle_seconds": 0}):
            with self.assertRaises(ValueError):
                config.save(self.root, update)

    def test_no_completion_from_claim_alone(self):
        claim = {"ok": True, "result": {"status": "completed", "evidence": ["report.md"]}}
        passed = [{"passed": True}]
        self.assertTrue(completion_allowed(claim, claim, passed))
        self.assertFalse(completion_allowed(claim, {"ok": False}, passed))
        self.assertFalse(completion_allowed(claim, claim, [{"passed": False}]))
        self.assertFalse(completion_allowed(claim, claim, []))
        self.assertFalse(completion_allowed({"ok": True, "result": {"status": "completed", "evidence": []}}, claim, passed))

    def test_quota_backoff_is_bounded_and_never_exhausts_attempt_count(self):
        self.assertEqual(retry_delay(1, config.DEFAULTS, "quota"), 60)
        self.assertEqual(retry_delay(100000, config.DEFAULTS, "quota"), 3600)

    def test_token_stable_and_private(self):
        first = config.token(self.root)
        self.assertEqual(config.token(self.root), first)
        self.assertEqual((self.root / ".agent-os" / "dashboard.token").stat().st_mode & 0o777, 0o600)
