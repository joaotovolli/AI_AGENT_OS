import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import advisor, config, strategy
from test_strategy import record
from test_goal_progress import item
from agent_os.worker import Worker


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = Worker(self.root)
        self.goal = self.worker.state.add_goal("Goal", "Task", "Evidence")
        self.settings = config.save(self.root, {"diagnostic_escalation": True,
                      "diagnostic_models": [{"model": "gpt-6-sol", "reasoning": "high"}]})
        self.catalog = [{"id": "gpt-6-sol", "reasoning": ["high"]}]
        for i, method in enumerate(("trace", "minimal-reproduction", "dependency-review")):
            self.worker.state.note(self.goal["id"], str(i), "attempt", {"phase": "Import", "blocker_kind": "technical",
                        "blocker_key": "parser", "approach_key": method, "completed": "Input loaded", "progress_made": False})

        self.worker.state.save_work_plan(self.goal["id"], [item(status="actionable")])
        strategy.save(self.worker.state, self.goal["id"], [record("consult_model")])
        self.addCleanup(self.worker.watchers.close)

    def entries(self):
        return self.worker.state.history(self.goal["id"])

    def test_same_blocker_with_distinct_attempts_qualifies(self):
        self.assertEqual(advisor.stalled(self.entries(), self.settings), "parser")

    def test_progress_dependencies_repeated_methods_and_changed_blockers_do_not_qualify(self):
        for modification in ({"progress_made": True}, {"blocker_key": "network"}, {"completed": "Parsed input"},
                             *({"blocker_kind": kind} for kind in ("operator", "external", "quota", "authentication", "configuration"))):
            entries = self.entries()
            entries[-1]["data"].update(modification)
            self.assertIsNone(advisor.stalled(entries, self.settings))
        entries = self.entries()
        for e in entries:
            e["data"]["approach_key"] = "same-method"
        self.assertIsNone(advisor.stalled(entries, self.settings))

    def test_readonly_bounded_advice_returns_to_worker_without_changing_settings(self):
        answer = {"ok": True, "result": {"summary": "Inspect the input contract", "next_action": "Validate encoding before parsing"}, "usage": {"input_tokens": 12}}
        with patch("agent_os.advisor.config.available_models", return_value=self.catalog), patch("agent_os.advisor.Codex") as cli:
            cli.return_value.run.return_value = answer
            advisor.consult(self.worker, self.goal, self.settings)
            self.assertTrue(cli.return_value.run.call_args.kwargs["readonly"])
            run_settings = cli.call_args.args[1]
            self.assertFalse(run_settings["fast"])
            self.assertEqual(run_settings["verify_timeout_seconds"], 180)
        self.assertEqual(config.load(self.root), self.settings)
        self.assertEqual(self.worker.state.get("usage")["input_tokens"], 12)
        self.assertIn("Validate encoding before parsing", self.worker.prompt(self.goal))
        self.assertIsNone(self.worker.state.get("active_run"))

    def test_off_unavailable_and_reserved_consultations_do_not_call_models(self):
        with patch("agent_os.advisor.Codex") as cli, patch("agent_os.advisor.config.available_models", return_value=[]):
            advisor.consult(self.worker, self.goal, dict(self.settings, diagnostic_escalation=False))
            advisor.consult(self.worker, self.goal, self.settings)
            cli.assert_not_called()
        self.worker.state.note(self.goal["id"], "reserved", "advisor_started", {"blocker_key": "parser"})
        with patch("agent_os.advisor.Codex") as cli, patch("agent_os.advisor.config.available_models", return_value=self.catalog):
            advisor.consult(self.worker, self.goal, self.settings)
            cli.assert_not_called()

    def test_no_guessed_ranking_and_same_model_requires_higher_reasoning(self):
        self.assertEqual(advisor.candidates(dict(self.settings, diagnostic_models=[]), self.catalog), [])
        self.assertEqual(advisor.candidates(self.settings, [{"id": "gpt-6-sol", "reasoning": ["low"]}]), [])
        preferences = [{"model": self.settings["model"], "reasoning": "low"}, {"model": self.settings["model"], "reasoning": "high"}]
        choices = advisor.candidates(dict(self.settings, diagnostic_models=preferences), [{"id": self.settings["model"], "reasoning": ["low", "high"]}])
        self.assertEqual(choices, preferences[1:])

    def test_duplicate_advice_is_not_reintroduced(self):
        self.worker.state.note(self.goal["id"], "old-advice", "advisor_advice", {"blocker_key": "parser", "next_action": "Try encoding"}, at=time.time()-5000)
        value = record("consult_model", advice_outcomes=[dict(key="trial", advice_id="old-advice", action="Try encoding", result="No change", evidence="docs/evidence/trial.md")])
        strategy.save(self.worker.state, self.goal["id"], [value])
        with patch("agent_os.advisor.config.available_models", return_value=self.catalog), patch("agent_os.advisor.Codex") as cli:
            cli.return_value.run.return_value = {"ok": True, "result": {"summary": "Same advice", "next_action": "Try encoding"}}
            advisor.consult(self.worker, self.goal, self.settings)
        self.assertEqual([e["kind"] for e in self.entries()].count("advisor_advice"), 1)
        self.assertEqual(self.entries()[-1]["kind"], "advisor_failed")

    def test_used_advisor_is_remembered_beyond_the_recent_history_window(self):
        self.worker.state.note(self.goal["id"], "old-reservation", "advisor_started",
                               {"blocker_key": "parser", "model": "gpt-6-sol", "reasoning": "high"}, at=time.time()-5000)
        for i in range(130):
            self.worker.state.note(self.goal["id"], "later"+str(i), "attempt",
                       {"blocker_kind": "technical", "blocker_key": "parser", "approach_key": "method"+str(i%3),
                        "completed": "Input loaded", "progress_made": False})
        with patch("agent_os.advisor.config.available_models", return_value=self.catalog), patch("agent_os.advisor.Codex") as cli:
            advisor.consult(self.worker, self.goal, self.settings)
            cli.assert_not_called()
