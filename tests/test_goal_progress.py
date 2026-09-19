import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import config
from agent_os.codex import validate_result
from agent_os.progress import observation_digest
from agent_os.state import State
from agent_os.watchers import WatcherService, observe, validate_spec
from agent_os.worker import Worker
from test_worker import FakeGitHub, success


def item(name="verify", status="waiting", dependencies=None):
    return {"key": name, "title": "Verify the service" if name == "verify" else "Document the interface",
            "criterion": "Service health and documented access", "status": status,
            "blocker_key": "service-health" if status in ("waiting", "needs_input") else "",
            "depends_on": dependencies or [], "evidence": "docs/evidence/service.md" if status == "verified" else ""}


def watcher(kind="file_exists", **updates):
    return dict({"key": "health", "work_key": "verify", "kind": kind, "path": "workspace/ready.json",
                 "url": "", "field": "", "expected": "true", "predicate": "equals",
                 "interval_seconds": 30, "lifetime_seconds": 3600}, **updates)


def diagnostic(**updates):
    return dict({"phase": "Verify", "approach_key": "service-probe", "approach": "Inspect service state",
                 "completed": "", "progress_made": False, "blocker_kind": "external",
                 "blocker_key": "service-health", "blocker": "Service is starting",
                 "observations": [{"key": "service_state", "value": "starting"}], "next_check_at": 0}, **updates)


class ProgressFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = State(self.root)
        self.goal = self.state.add_goal("Service readiness", "Deploy and document service", "Service health and documented access")
        self.gid = self.goal["id"]


class ProgressTests(ProgressFixture, unittest.TestCase):
    def test_guidance_persists_supersedes_and_clears_without_mutating_criteria(self):
        self.state.set_guidance(self.gid, "method", "Use the health endpoint")
        self.state.receive_followup("owner/repo", 1, 1, "owner", "Check the sample", self.gid)
        self.state.claim_followups(self.gid, "run")
        self.state.finish_followups("run", True, "Done")
        fresh = State(self.root)
        fresh.recover()
        self.assertEqual(fresh.guidance(self.gid)[0]["body"], "Use the health endpoint")
        self.assertEqual(fresh.claim_followups(self.gid, "run2"), [])
        fresh.set_guidance(self.gid, "method", "Use the status file")
        self.assertEqual(fresh.guidance(self.gid)[0]["version"], 2)
        self.assertEqual(fresh.goal(self.gid)["acceptance"], self.goal["acceptance"])
        fresh.set_guidance(self.gid, "method", None)
        self.assertEqual(fresh.guidance(self.gid), [])
        self.assertEqual(len(fresh.history(self.gid, kinds=("guidance",))), 3)

    def test_github_guidance_is_explicit_goal_scoped_and_idempotent(self):
        self.state.receive_followup("owner/repo", 1, 11, "owner", f"/guide {self.gid} method\nWait for a condition event", self.gid)
        self.state.receive_followup("owner/repo", 1, 11, "owner", f"/guide {self.gid} method\nDuplicate", self.gid)
        self.assertEqual(self.state.guidance(self.gid)[0]["version"], 1)
        self.assertEqual(self.state.followups()[0]["status"], "handled")
        self.state.receive_followup("owner/repo", 1, 12, "owner", "Ordinary one-shot context", self.gid)
        self.assertEqual(len(self.state.claim_followups(self.gid, "run")), 1)
        self.state.receive_followup("owner/repo", 1, 13, "owner", f"/guide-clear {self.gid} method", self.gid)
        self.assertEqual(self.state.guidance(self.gid), [])
        self.state.receive_followup("owner/repo", 1, 14, "owner", "/guide missing key\nBad target", self.gid)
        self.assertIn("active goal", self.state.followups()[-1]["reply"])

    def test_work_plan_preserves_omitted_verified_work_and_dependencies(self):
        self.state.save_work_plan(self.gid, [item(), item("docs", "actionable"), item("release", "actionable", ["verify"])])
        self.assertEqual([i["key"] for i in self.state.actionable_work(self.gid)], ["docs"])
        self.assertTrue(self.state.progress_snapshot()[self.gid]["partial"])
        self.state.save_work_plan(self.gid, [item("docs", "verified")])
        fresh = State(self.root)
        self.assertEqual(len(fresh.work_plan(self.gid)), 3)
        self.assertFalse(fresh.plan_complete(self.gid))
        self.assertEqual(fresh.actionable_work(self.gid), [])
        fresh.save_work_plan(self.gid, [item(status="verified")])
        self.assertEqual([i["key"] for i in fresh.actionable_work(self.gid)], ["release"])
        with self.assertRaises(ValueError):
            fresh.save_work_plan(self.gid, [item("cycle", "actionable", ["cycle"])])
        self.assertEqual(len(fresh.work_plan(self.gid)), 3)

    def test_external_equivalence_evidence_approach_and_bounded_backoff(self):
        facts = {"blocker_key": "service", "approach_key": "probe", "evidence_digest": observation_digest([{ "key": "state", "value": "starting"}])}
        delays = [self.state.schedule_external(self.gid, facts, config.DEFAULTS, now=1000) for _ in range(5)]
        self.assertEqual(delays, [300, 300, 900, 1800, 3600])
        fresh = State(self.root)
        self.assertEqual(fresh.wait_state(self.gid)["equivalent_attempts"], 5)
        self.assertEqual(fresh.schedule_external(self.gid, dict(facts, approach_key="different"), config.DEFAULTS, now=1000), 2)
        self.assertEqual(fresh.schedule_external(self.gid, dict(facts, evidence_digest="new-observation"), config.DEFAULTS, now=1000), 2)
        self.assertEqual(fresh.schedule_external(self.gid, dict(facts, next_check_at=1e12), config.DEFAULTS, now=1000), config.DEFAULTS["external_wait_max_seconds"])
        fresh.update_goal(self.gid, status="waiting", next_run=99999)
        fresh.receive_followup("owner/repo", 1, 50, "owner", "Try the fallback endpoint", self.gid)
        self.assertEqual(fresh.goal(self.gid)["next_run"], 0)
        self.assertEqual(fresh.wait_state(self.gid), {})

    def test_timestamp_percentage_and_summary_changes_do_not_count(self):
        a = [{"key": "state", "value": "starting"}, {"key": "checked_at", "value": "1000"}]
        b = [{"key": "state", "value": "starting"}, {"key": "checked_at", "value": "2000"}]
        self.assertEqual(observation_digest(a), observation_digest(b))
        self.assertEqual(observation_digest([{"key": "status", "value": "pending 2026-09-18T12:30:00Z 40%"}]),
                         observation_digest([{"key": "status", "value": "pending 2026-09-19T12:30:00Z 99%"}]))

    def test_restart_checkpoint_and_terminal_cleanup(self):
        self.state.set_guidance(self.gid, "method", "Observe the file")
        self.state.save_work_plan(self.gid, [item(), item("docs", "verified")])
        self.state.register_watcher(self.gid, watcher())
        self.state.schedule_external(self.gid, {}, config.DEFAULTS)
        exported = self.state.export_progress()
        fresh_root = self.root / "fresh"
        fresh_root.mkdir()
        fresh = State(fresh_root)
        fresh.add_goal("Service", "Work", "Criteria", goal_id=self.gid)
        fresh.restore_progress(exported)
        self.assertEqual(fresh.export_progress(), exported)
        fresh.recover()
        self.assertEqual(fresh.export_progress(), exported)
        fresh.update_goal(self.gid, status="completed")
        self.assertEqual(fresh.guidance(self.gid), [])
        self.assertEqual(fresh.watchers(self.gid)[0]["status"], "cancelled")
        self.assertEqual(fresh.wait_state(self.gid), {})
        self.assertEqual(len(fresh.work_plan(self.gid)), 2)

    def test_completion_requires_current_context_even_during_publication(self):
        revision = self.state.context_revision(self.gid)
        self.state.set_guidance(self.gid, "method", "Inspect the new fixture")
        self.assertFalse(self.state.complete_if_current(self.gid, revision))
        self.assertNotEqual(self.state.goal(self.gid)["status"], "completed")

    def test_new_settings_leave_retained_runtime_config_readable(self):
        config.save(self.root, {"external_repeat_limit": 4, "model": "custom"})
        legacy = json.loads((self.root/".agent-os/config.json").read_text())
        features = json.loads((self.root/".agent-os/features.json").read_text())
        self.assertNotIn("external_repeat_limit", legacy)
        self.assertNotIn("external_repeat_limit", features)
        self.assertEqual(config.load(self.root)["external_repeat_limit"], 4)
        with self.assertRaises(ValueError):
            config.save(self.root, {"external_wait_min_seconds": 80000, "external_wait_max_seconds": 600})
        self.assertEqual(config.load(self.root)["external_repeat_limit"], 4)


class WatcherTests(ProgressFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.state.save_work_plan(self.gid, [item()])
        self.service = WatcherService(self.root, self.state)
        self.addCleanup(self.service.close)

    def test_unchanged_polls_back_off_without_waking_or_publishing(self):
        self.state.register_watcher(self.gid, watcher(), now=1000)
        self.state.update_goal(self.gid, status="waiting", next_run=5000)
        self.state.set("needs_checkpoint", False)
        first = self.state.watchers(self.gid)[0]
        for offset in (0, 30, 60):
            self.service.record(first, value="false", now=1000+offset)
        current = self.state.watchers(self.gid)[0]
        self.assertEqual(current["next_check"], 1120)
        self.assertEqual(current["status"], "active")
        self.assertEqual(self.state.goal(self.gid)["next_run"], 5000)
        self.assertFalse(self.state.get("needs_checkpoint"))

    def test_change_wakes_only_the_linked_work_and_preserves_pause(self):
        self.state.save_work_plan(self.gid, [item("docs", "verified")])
        self.state.register_watcher(self.gid, watcher("file_changed", expected="", predicate="changed"), now=1000)
        self.state.update_goal(self.gid, status="waiting", next_run=9999)
        first = self.state.watchers(self.gid)[0]
        self.service.record(first, value="old", now=1000)
        self.state.recover()
        self.state.set("paused", True)
        self.service.record(first, value="new", now=1030)
        self.assertEqual(self.state.goal(self.gid)["status"], "queued")
        self.assertTrue(self.state.get("paused"))
        self.assertEqual(self.state.watchers(self.gid)[0]["status"], "triggered")
        self.assertEqual([i["key"] for i in self.state.actionable_work(self.gid)], ["verify"])
        self.assertEqual(next(i for i in self.state.work_plan(self.gid) if i["key"] == "docs")["status"], "verified")
        revision = self.state.context_revision(self.gid)
        self.service.record(first, value="again", now=1060)
        self.assertEqual(self.state.context_revision(self.gid), revision)

    def test_cancel_expiry_and_completion_ignore_late_results(self):
        self.state.register_watcher(self.gid, watcher(), now=1000)
        first = self.state.watchers(self.gid)[0]
        self.state.cancel_watcher(self.gid, "health")
        self.service.record(first, value="true", now=1030)
        self.assertEqual(self.state.watchers(self.gid)[0]["status"], "cancelled")
        self.state.register_watcher(self.gid, watcher(key="expiry"), now=1000)
        expiring = next(w for w in self.state.watchers(self.gid) if w["key"] == "expiry")
        self.service.record(expiring, now=4600)
        self.assertEqual(next(w for w in self.state.watchers(self.gid) if w["key"] == "expiry")["status"], "expired")
        self.state.register_watcher(self.gid, watcher(key="last"), now=1000)
        self.state.update_goal(self.gid, status="cancelled")
        self.service.service(now=1100)
        self.assertFalse(any(w["status"] == "active" for w in self.state.watchers(self.gid)))

    def test_poll_errors_are_not_condition_transitions_or_approval(self):
        self.state.register_watcher(self.gid, watcher(), now=1000)
        original = self.state.watchers(self.gid)[0]
        self.state.update_goal(self.gid, status="blocked")
        self.service.record(original, error="Remote authorization prevents check", now=1000)
        self.assertEqual(self.state.goal(self.gid)["status"], "blocked")
        self.assertEqual(self.state.watchers(self.gid)[0]["status"], "active")
        self.service.record(original, value="true", now=1030)
        self.assertEqual(self.state.goal(self.gid)["status"], "blocked")
        self.assertNotEqual(self.state.goal(self.gid)["status"], "completed")
        self.state.save_work_plan(self.gid, [item(status="needs_input")])
        with self.assertRaises(ValueError):
            self.state.register_watcher(self.gid, watcher(key="approval"))

    def test_real_file_json_and_change_observers_and_path_boundaries(self):
        (self.root/"workspace").mkdir()
        path = self.root/"workspace/ready.json"
        self.assertEqual(observe(self.root, watcher()), "false")
        path.write_text('{"service":{"healthy":true}}')
        self.assertEqual(observe(self.root, watcher()), "true")
        self.assertEqual(observe(self.root, watcher("json_value", field="service.healthy")), "true")
        changed = watcher("file_changed", predicate="changed", expected="")
        before = observe(self.root, changed)
        path.write_text('{"service":{"healthy":false}}')
        self.assertNotEqual(observe(self.root, changed), before)
        path.unlink()
        path.symlink_to(self.root/".agent-os/state.sqlite3")
        with self.assertRaises(ValueError):
            observe(self.root, watcher())
        for invalid in (watcher(path="../secret"), watcher(interval_seconds=1),
                        watcher("http_status", path="", url="https://" + "user:password" + "@example.invalid", expected="200")):
            with self.assertRaises(ValueError):
                validate_spec(invalid)

    def test_identical_registration_preserves_baseline_backoff_and_deadline(self):
        spec = watcher("file_changed", predicate="changed", expected="")
        self.state.register_watcher(self.gid, spec, now=1000)
        first = self.state.watchers(self.gid)[0]
        self.service.record(first, value="one", now=1000)
        self.state.register_watcher(self.gid, spec, now=2000)
        current = self.state.watchers(self.gid)[0]
        self.assertEqual(current["created"], 1000)
        self.assertEqual(current["observation"], "one")
        self.assertEqual(current["polls"], 1)
        self.service.record(first, value="two", now=2030)
        self.assertEqual(self.state.watchers(self.gid)[0]["status"], "triggered")


class WorkerProgressTests(ProgressFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        (self.root/"agent_os").mkdir()
        (self.root/"agent_os/__init__.py").write_text("VERSION=1\n")
        self.worker = Worker(self.root)
        self.worker.github = FakeGitHub(self.state)
        self.addCleanup(self.worker.watchers.close)
        self.checks = patch("agent_os.worker.checks.verify", return_value=([{"passed": True}], "Passed"))
        self.checks.start()
        self.addCleanup(self.checks.stop)

    def test_guidance_is_in_every_attempt_while_one_shot_is_consumed(self):
        self.state.set_guidance(self.gid, "method", "Use the condition watcher")
        self.state.receive_followup("owner/repo", 1, 1, "owner", "One shot only", self.gid)
        with patch("agent_os.worker.Codex.run", return_value=success("continue")) as codex:
            self.worker.tick()
            self.state.update_goal(self.gid, next_run=0)
            self.worker.tick()
        self.assertEqual(codex.call_count, 2)
        for call in codex.call_args_list:
            self.assertIn("Use the condition watcher", call.args[0])
        self.assertIn("One shot only", codex.call_args_list[0].args[0])
        self.assertNotIn("One shot only", codex.call_args_list[1].args[0])

    def test_repeated_external_result_suppresses_full_turns_across_recovery(self):
        work = success("blocked")
        work["result"]["diagnostic"] = diagnostic()
        with patch("agent_os.worker.Codex.run", return_value=work) as codex:
            for _ in range(3):
                self.state.update_goal(self.gid, next_run=0)
                self.worker.tick()
            self.state.recover()
            self.worker.tick()
        self.assertEqual(codex.call_count, 3)
        self.assertGreater(self.state.goal(self.gid)["next_run"], time.time()+890)
        self.assertTrue(self.state.wait_state(self.gid)["stalled"])

    def test_independent_work_then_condition_event_then_verified_completion(self):
        work = success("blocked")
        work["result"].update(diagnostic=diagnostic(), work_plan=[item(), item("docs", "actionable")], watchers=[watcher()])
        with patch("agent_os.worker.Codex.run", return_value=work):
            self.worker.tick()
        self.assertLess(self.state.goal(self.gid)["next_run"], time.time()+3)
        self.assertTrue(self.state.progress_snapshot()[self.gid]["partial"])
        work["result"].update(work_plan=[item("docs", "verified")], watchers=[])
        self.state.update_goal(self.gid, next_run=0)
        with patch("agent_os.worker.Codex.run", return_value=work):
            self.worker.tick()
        self.assertGreater(self.state.goal(self.gid)["next_run"], time.time()+3500)
        self.worker.watchers.record(self.state.watchers(self.gid)[0], value="true")
        self.assertEqual(self.state.goal(self.gid)["status"], "queued")
        final = success()
        final["result"]["work_plan"] = [item(status="verified")]
        with patch("agent_os.worker.Codex.run", side_effect=[final, success()]):
            self.worker.tick()
        self.assertEqual(self.state.goal(self.gid)["status"], "completed")
        self.assertTrue(self.state.plan_complete(self.gid))

    def test_guidance_during_checks_invalidates_completion_and_wakes(self):
        def check(*_):
            self.state.set_guidance(self.gid, "method", "Review the alternative fixture")
            return [{"passed": True}], "OK"
        with patch("agent_os.worker.Codex.run", return_value=success()), patch("agent_os.worker.checks.verify", side_effect=check):
            self.worker.tick()
        self.assertEqual(self.state.goal(self.gid)["status"], "queued")
        self.assertEqual(self.state.guidance(self.gid)[0]["body"], "Review the alternative fixture")

    def test_incomplete_plan_cannot_complete_even_when_claimed(self):
        work = success()
        work["result"].update(work_plan=[item()], diagnostic=diagnostic())
        with patch("agent_os.worker.Codex.run", return_value=work) as codex:
            self.worker.tick()
        self.assertEqual(codex.call_count, 1)
        self.assertNotEqual(self.state.goal(self.gid)["status"], "completed")

    def test_result_schema_accepts_legacy_and_rejects_unbounded_watchers(self):
        result = success()["result"]
        self.assertEqual(validate_result(result), result)
        result = dict(result, work_plan=[item()], diagnostic=diagnostic(), watchers=[watcher()])
        self.assertEqual(validate_result(result), result)
        with self.assertRaises(ValueError):
            validate_result(dict(result, watchers=[watcher(interval_seconds=0)]))
