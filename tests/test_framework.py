import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import config, deploy
from agent_os.framework import Framework, MANIFEST, managed, provenance, stamp
from agent_os.state import State


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE).decode().strip()


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.base = self.home / "base"
        self.root = self.home / "instance"
        self.remote = self.home / "instance.git"
        for path in (self.base, self.root):
            path.mkdir()
            git(path, "init", "-b", "main")
            git(path, "config", "user.name", "Framework Test")
            git(path, "config", "user.email", "test@example.invalid")
        for name, content in {
            ".gitignore": ".agent-os/\n__pycache__/\n*.pyc\n",
            "README.md": "Framework fixture\n",
            "agent_os/__init__.py": "VERSION = 1\n",
            "agent_os/core.py": "VALUE = 1\n" + "# Context\n"*12 + "DESCRIPTION = 'base'\n",
            "tests/test_fixture.py": "import unittest\nclass Check(unittest.TestCase):\n    def test_core(self):\n        from agent_os.core import VALUE\n        self.assertGreater(VALUE, 0)\n",
            "docs/ACCESS.md": "Base access instructions\n",
            "workspace/template.txt": "Base workspace\n",
            "infra/host.md": "Base host instructions\n",
        }.items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.commit(self.base, "Base version")
        self.base_commit = git(self.base, "rev-parse", "HEAD")
        archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=self.base)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(self.root, filter="data")
        config.atomic_json(self.root / MANIFEST, {"format_version": 1, "repository": "fixture/template",
                          "base_commit": self.base_commit, "branch": "main"})
        (self.root / "workspace/project.txt").write_text("Instance project\n")
        (self.root / "docs/ACCESS.md").write_text("Instance access\n")
        self.commit(self.root, "Fresh independent instance")
        git(self.home, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "origin", "main")
        git(self.root, "config", "url."+str(self.base)+".insteadOf", "https://github.com/fixture/template.git")
        self.state = State(self.root)
        self.state.set("paused", True)
        self.goal = self.state.add_goal("Preserve this goal", "Task", "Evidence")
        self.settings = config.save(self.root, {"model": "gpt-6-luna", "github_followups": True})
        self.secret = config.token(self.root)
        self.original_runtime = deploy.activate(self.root)
        self.updater = Framework(self.root, self.state)
        self.updater.github.identity = lambda: ("fixture/instance", "main")

    def commit(self, path, message):
        git(path, "add", "-A")
        git(path, "commit", "-m", message)

    def change(self, **files):
        for name, value in files.items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        self.commit(self.base, "Update base")
        return git(self.base, "rev-parse", "HEAD")

    def assert_untouched(self, head):
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(deploy.current(self.root), str(self.root / ".agent-os/releases" / self.original_runtime))
        self.assertEqual(config.load(self.root), self.settings)
        self.assertEqual(self.state.goal(self.goal["id"]), self.goal)

    def test_detect_validate_publish_activate_and_preserve_instance_data(self):
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        self.assertEqual(self.updater.check()["target_commit"], target)
        self.assertEqual(self.state.get("framework")["status"], "available")
        commit = self.updater.apply(target)
        self.assertEqual(git(self.root, "ls-remote", "origin", "refs/heads/main").split()[0], commit)
        self.assertEqual(provenance(self.root)["base_commit"], target)
        self.assertEqual((self.root / "workspace/project.txt").read_text(), "Instance project\n")
        self.assertEqual(config.token(self.root), self.secret)
        self.assertEqual(config.load(self.root), self.settings)
        self.assertEqual(self.state.goal(self.goal["id"]), self.goal)
        self.assertEqual((self.root / ".agent-os/previous-runtime").resolve().name, self.original_runtime)
        self.assertTrue(self.state.get("paused"))
        self.assertEqual(self.updater.check()["status"], "current")

    def test_conflicting_core_edits_leave_source_and_runtime_intact(self):
        (self.root / "agent_os/__init__.py").write_text("VERSION = 'local'\n")
        self.commit(self.root, "Instance core change")
        head = git(self.root, "rev-parse", "HEAD")
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        with self.assertRaisesRegex(RuntimeError, "conflict"):
            self.updater.apply(target)
        self.assert_untouched(head)

    def test_nonoverlapping_changes_in_same_core_file_survive(self):
        path = self.root / "agent_os/core.py"
        path.write_text(path.read_text().replace("DESCRIPTION = 'base'", "DESCRIPTION = 'instance'"))
        self.commit(self.root, "Customize core description")
        target = self.change(**{"agent_os/core.py": (self.base / "agent_os/core.py").read_text().replace("VALUE = 1", "VALUE = 2")})
        self.updater.apply(target)
        self.assertIn("VALUE = 2", path.read_text())
        self.assertIn("DESCRIPTION = 'instance'", path.read_text())

    def test_failed_candidate_tests_leave_source_and_runtime_intact(self):
        head = git(self.root, "rev-parse", "HEAD")
        target = self.change(**{"agent_os/core.py": "VALUE = -1\n"})
        with self.assertRaisesRegex(RuntimeError, "failed validation"):
            self.updater.apply(target)
        self.assert_untouched(head)

    def test_generated_workspace_host_and_instance_records_are_not_updated(self):
        target = self.change(**{"workspace/template.txt": "Upstream project", "docs/ACCESS.md": "Upstream access",
                                "infra/host.md": "Upstream host", "agent_os/__init__.py": "VERSION = 2\n"})
        self.updater.apply(target)
        self.assertEqual((self.root / "docs/ACCESS.md").read_text(), "Instance access\n")
        self.assertEqual((self.root / "workspace/template.txt").read_text(), "Base workspace\n")
        self.assertEqual((self.root / "infra/host.md").read_text(), "Base host instructions\n")
        for path in ("docs/history/goal/0001.json", "state/checkpoint.json", ".agent-os/config.json", "docs/VALIDATION.md"):
            self.assertFalse(managed(path))

    def test_running_dirty_and_unpublished_candidates_cannot_activate(self):
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        head = git(self.root, "rev-parse", "HEAD")
        self.state.set("active_run", {"id": "busy"})
        with self.assertRaisesRegex(RuntimeError, "Pause"):
            self.updater.apply(target)
        self.state.set("active_run", None)
        path = self.root / "scratch.txt"
        path.write_text("Uncheckpointed work")
        with self.assertRaisesRegex(RuntimeError, "Checkpoint"):
            self.updater.apply(target)
        path.unlink()
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        with self.assertRaises(RuntimeError):
            self.updater.apply(target)
        self.assert_untouched(head)

    def test_fresh_instance_provenance_and_existing_origin_are_preserved(self):
        destination = self.home / "copy"
        destination.mkdir()
        stamp(self.root, destination)
        self.assertEqual(provenance(destination), provenance(self.root))
        origin = git(self.root, "remote", "get-url", "origin")
        self.updater.check()
        self.assertEqual(git(self.root, "remote", "get-url", "origin"), origin)
        (destination / MANIFEST).unlink()
        self.assertIsNone(provenance(destination))

    def test_validation_that_modifies_candidate_source_cannot_activate(self):
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        head = git(self.root, "rev-parse", "HEAD")
        def mutate(root, *_):
            (root / "agent_os/__init__.py").write_text("VERSION = 'untested'\n")
            return [{"passed": True}], ""
        with patch("agent_os.framework.checks.verify", side_effect=mutate), self.assertRaisesRegex(RuntimeError, "modified"):
            self.updater.apply(target)
        self.assert_untouched(head)

    def test_resuming_during_validation_prevents_activation(self):
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        head = git(self.root, "rev-parse", "HEAD")
        def resume(*_):
            self.state.set("paused", False)
            return [{"passed": True}], ""
        with patch("agent_os.framework.checks.verify", side_effect=resume), self.assertRaisesRegex(RuntimeError, "changed"):
            self.updater.apply(target)
        self.assert_untouched(head)

    def test_update_preserves_guidance_waiting_work_and_background_watchers(self):
        from test_goal_progress import item, watcher
        self.state.set_guidance(self.goal["id"], "method", "Wait for the service event")
        self.state.save_work_plan(self.goal["id"], [item(), item("docs", "verified")])
        self.state.register_watcher(self.goal["id"], watcher())
        self.state.schedule_external(self.goal["id"], {}, config.DEFAULTS)
        self.state.update_goal(self.goal["id"], status="waiting", next_run=9999999999)
        self.state.note(self.goal["id"], "earlier", "attempt", {"summary": "Independent documentation verified"})
        before = self.state.export_progress()
        goal_before = self.state.goal(self.goal["id"])
        target = self.change(**{"agent_os/__init__.py": "VERSION = 2\n"})
        self.updater.apply(target)
        reloaded = State(self.root)
        reloaded.recover()
        self.assertEqual(reloaded.export_progress(), before)
        self.assertEqual(reloaded.goal(self.goal["id"]), goal_before)
        self.assertEqual(reloaded.history(self.goal["id"])[0]["kind"], "guidance")
        self.assertEqual(config.load(self.root), self.settings)
        self.assertTrue(reloaded.get("paused"))
        self.assertEqual((self.root/"workspace/project.txt").read_text(), "Instance project\n")
