import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os.config import DEFAULTS, save
from agent_os.worker import Worker


def success(status="completed"):
    return {"ok": True, "usage": {"input_tokens": 10, "output_tokens": 2},
            "result": {"status": status, "summary": "Evidence reviewed", "progress": 100,
                       "evidence": ["docs/evidence/test.md"], "next_action": ""}}


class FakeGitHub:
    def __init__(self, state):
        self.state = state
        self.fail = False
        self.digest = "unchanged"
        self.promoted = False
        self.checkpoints = []

    def publish_live(self, **_):
        pass

    def identity(self):
        return "owner/repo", "agent/instance"

    def gh(self, endpoint):
        return {}

    def checkpoint(self, message, completion=None):
        self.checkpoints.append((message, completion))
        if completion:
            assert self.state.goal(completion)["status"] != "completed"
        if self.fail:
            raise RuntimeError("Network unreachable")
        return "commit-sha"

    def workspace_digest(self):
        return self.digest

    def promote(self):
        self.promoted = True


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "agent_os").mkdir()
        (self.root / "agent_os/__init__.py").write_text("VERSION=1\n")
        self.worker = Worker(self.root)
        self.worker.github = FakeGitHub(self.worker.state)
        self.state = self.worker.state
        self.goal = self.state.add_goal("Test goal", "Complete task", "Prove the result")

    def test_work_review_publish_and_activation_complete_in_order(self):
        with patch("agent_os.worker.Codex.run", side_effect=[success(), success()]) as codex, patch("agent_os.worker.checks.verify", return_value=([{"name":"Test","passed":True}], "OK")):
            self.worker.tick()
        self.assertEqual(codex.call_count, 2)
        self.assertEqual(self.state.goal(self.goal["id"])["status"], "completed")
        self.assertTrue(self.worker.github.promoted)
        self.assertEqual(self.state.get("usage")["input_tokens"], 20)
        self.assertIsNone(self.state.get("active_run"))

    def test_failed_checks_continue_without_accepting_claim(self):
        with patch("agent_os.worker.Codex.run", return_value=success()) as codex, patch("agent_os.worker.checks.verify", return_value=([{"name":"Test","passed":False}], "FAIL")):
            self.worker.tick()
        self.assertEqual(codex.call_count, 1)
        self.assertEqual(self.state.goal(self.goal["id"])["status"], "waiting")
        self.assertFalse(self.worker.github.promoted)

    def test_quota_retains_goal_and_retries_later(self):
        with patch("agent_os.worker.Codex.run", return_value={"ok":False,"error_kind":"quota","error":"usage limit","usage":{}}):
            self.worker.tick()
        goal = self.state.goal(self.goal["id"])
        self.assertEqual(goal["status"], "waiting")
        self.assertGreater(goal["next_run"], time.time()+50)

    def test_github_failure_cannot_complete_a_verified_goal(self):
        self.worker.github.fail = True
        with patch("agent_os.worker.Codex.run", side_effect=[success(), success()]), patch("agent_os.worker.checks.verify", return_value=([{"name":"Test","passed":True}], "OK")):
            self.worker.tick()
        self.assertNotEqual(self.state.goal(self.goal["id"])["status"], "completed")
        self.assertEqual(self.state.get("pending_completion"), self.goal["id"])
        self.worker.github.fail = False
        self.state.update_goal(self.goal["id"], next_run=0)
        with patch("agent_os.worker.Codex.run") as codex:
            self.worker.tick()
            codex.assert_not_called()
        self.assertEqual(self.state.goal(self.goal["id"])["status"], "completed")

    def test_modified_evidence_invalidates_pending_completion(self):
        self.state.set("pending_completion", self.goal["id"])
        self.state.set("completion_digest", "old")
        self.worker.finish_completion(self.goal, DEFAULTS)
        self.assertIsNone(self.state.get("pending_completion"))
        self.assertNotEqual(self.state.goal(self.goal["id"])["status"], "completed")

    def test_idle_wakeup_and_user_priority(self):
        self.state.update_goal(self.goal["id"], status="completed")
        self.state.set("ready", True)
        self.state.set("next_maintenance", time.time()-1)
        self.worker.schedule_maintenance(DEFAULTS)
        self.assertEqual(self.state.select_goal()["kind"], "maintenance")
        self.worker.schedule_maintenance(DEFAULTS)
        self.assertEqual(len(self.state.goals()), 2)
        user = self.state.add_goal("User priority", "Task", "Evidence")
        self.assertEqual(self.state.select_goal()["id"], user["id"])

    def test_pause_never_launches_paid_work(self):
        self.state.set("paused", True)
        with patch("agent_os.worker.Codex.run") as codex:
            self.worker.tick()
            codex.assert_not_called()

    def test_operator_dependency_stops_paid_retries_and_blocks_later_goals(self):
        work = success("blocked")
        work["result"]["diagnostic"] = {"blocker_kind": "operator", "blocker": "Choose the data source", "next_action": "Use local setup"}
        self.state.add_goal("Later", "Task", "Evidence")
        with patch("agent_os.worker.Codex.run", return_value=work) as codex, patch("agent_os.worker.checks.verify", return_value=([{"passed": True}], "")):
            self.worker.tick()
            self.worker.tick()
        self.assertEqual(codex.call_count, 1)
        self.assertEqual(self.state.goal(self.goal["id"])["status"], "blocked")
        self.assertIsNone(self.state.select_goal())

    def test_success_clears_historical_provider_error(self):
        self.state.set("last_error", "usage limit reached")
        with patch("agent_os.worker.Codex.run", return_value=success("continue")), patch("agent_os.worker.checks.verify", return_value=([{"passed": True}], "")):
            self.worker.tick()
        self.assertEqual(self.state.get("last_error"), "")

    def test_followup_arriving_during_checks_prevents_premature_completion(self):
        def check(*_):
            self.state.receive_followup("owner/repo", 1, 12, "owner", "Check the revised fixture", self.goal["id"])
            return [{"passed": True}], ""
        with patch("agent_os.worker.Codex.run", return_value=success()), patch("agent_os.worker.checks.verify", side_effect=check):
            self.worker.tick()
        self.assertNotEqual(self.state.goal(self.goal["id"])["status"], "completed")
        self.assertTrue(self.state.pending_followups(self.goal["id"]))

    def test_disabling_intake_still_processes_already_accepted_followups(self):
        save(self.root, {"github_followups": False})
        self.state.receive_followup("owner/repo", 1, 12, "owner", "Use revised fixture", self.goal["id"])
        with patch("agent_os.worker.Codex.run", return_value=success()) as codex, patch("agent_os.worker.checks.verify", return_value=([{"passed": True}], "")):
            self.worker.tick()
        self.assertIn("Use revised fixture", codex.call_args_list[0].args[0])
        self.assertEqual(self.state.followups()[0]["status"], "handled")
        self.assertEqual(self.state.goal(self.goal["id"])["status"], "completed")
