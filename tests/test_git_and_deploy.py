import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import deploy
from agent_os.github import GitHub, repo_name
from agent_os.redact import redact, secret_path
from agent_os.state import State


class GitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "instance"
        self.root.mkdir()
        self.remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(self.remote)], check=True, capture_output=True)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Agent OS Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", str(self.remote))
        (self.root / ".gitignore").write_text(".agent-os/\n")
        (self.root / "README.md").write_text("Fixture\n")
        self.git("add", ".")
        self.git("commit", "-m", "Initial")
        self.git("push", "origin", "main")
        self.state = State(self.root)
        self.github = GitHub(self.root, self.state)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True).stdout.decode().strip()

    def test_remote_identity_never_accepts_embedded_credentials(self):
        self.assertEqual(repo_name("git@github.com:owner/repo.git"), "owner/repo")
        self.assertEqual(repo_name("https://github.com/owner/repo.git"), "owner/repo")
        with self.assertRaises(ValueError):
            repo_name("https://" + "user:pass" + "@github.com/owner/repo.git")

    def test_checkpoint_uses_real_git_and_survives_local_state_recreation(self):
        goal = self.state.add_goal("Fixture", "Work", "Evidence")
        with patch.object(self.github, "identity", return_value=("owner/repo", "main")):
            commit = self.github.checkpoint("test: checkpoint state")
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/main").split()[0], commit)
        saved = json.loads((self.root / "state/checkpoint.json").read_text())
        self.assertEqual(saved["goals"][0]["id"], goal["id"])
        self.assertNotIn(".agent-os", self.git("ls-files"))

    def test_credentials_are_rejected_even_if_force_added(self):
        (self.root / "auth.json").write_text('{}')
        self.git("add", "auth.json")
        with self.assertRaisesRegex(RuntimeError, "credential/runtime"):
            self.github.scan_index()

    def test_recognized_secret_content_is_rejected(self):
        (self.root / "bad.txt").write_text("ghp_" + "A" * 36)
        self.git("add", "bad.txt")
        with self.assertRaisesRegex(RuntimeError, "Possible credential"):
            self.github.scan_index()

    def test_non_fast_forward_remote_is_not_overwritten(self):
        other = Path(self.tmp.name) / "other"
        subprocess.run(["git", "clone", str(self.remote), str(other)], check=True, capture_output=True)
        for key, value in (("user.name", "Other"), ("user.email", "other@example.invalid")):
            subprocess.run(["git", "config", key, value], cwd=other, check=True)
        (other / "other.txt").write_text("Independent work")
        for args in (["add", "."], ["commit", "-m", "Other work"], ["push", "origin", "main"]):
            subprocess.run(["git", *args], cwd=other, check=True, capture_output=True)
        with patch.object(self.github, "identity", return_value=("owner/repo", "main")):
            with self.assertRaisesRegex(RuntimeError, "absent locally"):
                self.github.checkpoint("test: preserve divergence")

    def test_runtime_activation_keeps_previous_release(self):
        package = self.root / "agent_os"
        package.mkdir()
        (package / "__init__.py").write_text('VERSION = 1\n')
        first = deploy.activate(self.root)
        (package / "__init__.py").write_text('VERSION = 2\n')
        self.assertIn('VERSION = 1', (self.root / ".agent-os/runtime/agent_os/__init__.py").read_text())
        second = deploy.activate(self.root)
        self.assertNotEqual(first, second)
        self.assertEqual((self.root / ".agent-os/previous-runtime").resolve().name, first)
        self.assertEqual(deploy.activate(self.root), second)

    def test_redaction(self):
        value = "ghp_" + "Z" * 36
        self.assertNotIn(value, redact(value))
        self.assertTrue(secret_path("dir/.env.local"))
        self.assertFalse(secret_path(".env.example"))
