import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from agent_os.config import token
from agent_os.server import make_server
from agent_os.state import State


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.server = make_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.secret = token(self.root)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, body=None, auth=True, headers=None):
        h = {"Content-Type": "application/json"}
        if auth:
            h["Authorization"] = "Bearer " + self.secret
        h.update(headers or {})
        request = urllib.request.Request(self.url+path, data=json.dumps(body).encode() if body is not None else None, headers=h)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if response.headers.get("Content-Type", "").startswith("application/json") else raw

    def test_authentication_and_public_health(self):
        self.assertEqual(self.request("/api/state", auth=False)[0], 401)
        self.assertEqual(self.request("/healthz", auth=False), (200, {"ok": True}))
        self.assertEqual(self.request("/api/state")[0], 200)

    def test_origin_and_host_validation(self):
        self.assertEqual(self.request("/api/control", {"action":"pause"}, headers={"Origin":"https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Host":"attacker.invalid"})[0], 403)

    def test_goal_submission_pause_resume_and_cancel(self):
        status, goal = self.request("/api/goals", {"title":"Goal","description":"Work","acceptance":"Evidence"})
        self.assertEqual(status, 201)
        self.assertEqual(self.request("/api/control", {"action":"pause"})[0], 200)
        self.assertTrue(self.request("/api/state")[1]["paused"])
        self.request("/api/control", {"action":"resume"})
        self.assertFalse(self.request("/api/state")[1]["paused"])
        self.request("/api/control", {"action":"cancel","goal_id":goal["id"]})
        self.assertEqual(State(self.root).goal(goal["id"])["status"], "cancelled")

    def test_settings_persist_and_unblock_waiting_goal(self):
        state = State(self.root)
        goal = state.add_goal("Goal", "Work", "Evidence")
        state.update_goal(goal["id"], status="waiting", next_run=9999999999)
        self.assertEqual(self.request("/api/settings", {"model":"new-custom-model","fast":True})[0], 200)
        self.assertEqual(State(self.root).goal(goal["id"])["next_run"], 0)
        self.assertTrue(self.request("/api/state")[1]["settings"]["fast"])
        self.assertEqual(self.request("/api/settings", {"port":9000})[0], 400)

    def test_invalid_input_and_static_paths(self):
        self.assertEqual(self.request("/api/goals", {"title":""})[0], 400)
        self.assertEqual(self.request("/../../.agent-os/dashboard.token")[0], 404)
        status, html = self.request("/", auth=False)
        self.assertEqual(status, 200)
        self.assertIn('id="goal-form"', html)
        self.assertNotIn(self.secret, html)

    def test_history_requires_authentication_and_survives_cancellation(self):
        state = State(self.root)
        goal = state.add_goal("Goal", "Task", "Evidence")
        state.note(goal["id"], "attempt", "attempt", {"phase": "Validate", "summary": "Totals checked"})
        state.receive_followup("owner/repo", 1, 1, "owner", "Clarification", goal["id"])
        path = "/api/history/"+goal["id"]
        self.assertEqual(self.request(path, auth=False)[0], 401)
        self.assertEqual(self.request(path)[1][0]["data"]["phase"], "Validate")
        self.request("/api/control", {"action": "cancel", "goal_id": goal["id"]})
        self.assertEqual(self.request(path)[1][-1]["kind"], "cancelled")
        self.assertEqual(state.followups()[0]["status"], "handled")
        self.assertIn("cancelled", state.followups()[0]["reply"])
        self.assertEqual(self.request("/api/history/missing")[0], 404)

    def test_feature_settings_and_blocked_goal_retry_preserve_pause(self):
        values = {"diagnostic_escalation": True, "github_followups": True, "github_operators": ["owner"],
                  "diagnostic_models": [{"model": "advisor-model", "reasoning": "high"}]}
        self.assertEqual(self.request("/api/settings", values)[0], 200)
        state = State(self.root)
        self.assertGreater(state.get("operator_enabled_since"), 0)
        for key, value in values.items():
            self.assertEqual(self.request("/api/state")[1]["settings"][key], value)
        goal = state.add_goal("Goal", "Task", "Evidence")
        state.update_goal(goal["id"], status="blocked")
        state.set("paused", True)
        self.request("/api/control", {"action": "retry", "goal_id": goal["id"]})
        self.assertTrue(state.get("paused"))
        self.assertEqual(state.goal(goal["id"])["status"], "queued")

    def test_framework_requests_require_authentication_pause_and_pinned_commit(self):
        state = State(self.root)
        self.assertEqual(self.request("/api/framework", {"action": "check"}, auth=False)[0], 401)
        self.assertEqual(self.request("/api/framework", {"action": "apply", "commit": "a"*40})[0], 400)
        state.set("paused", True)
        self.assertEqual(self.request("/api/framework", {"action": "apply", "commit": "main"})[0], 400)
        state.set("active_run", {"id": "busy"})
        self.assertEqual(self.request("/api/framework", {"action": "apply", "commit": "a"*40})[0], 400)
        state.set("active_run", None)
        self.assertEqual(self.request("/api/framework", {"action": "apply", "commit": "a"*40})[0], 202)
        self.assertEqual(state.get("framework_request")["commit"], "a"*40)
        self.assertEqual(self.request("/api/framework", {"action": "check"})[0], 400)

    def test_persistent_guidance_api_auth_replacement_and_immutable_criteria(self):
        state = State(self.root)
        goal = state.add_goal("Goal", "Work", "Original criteria")
        data = {"action": "set", "goal_id": goal["id"], "key": "method", "body": "Use the health endpoint"}
        self.assertEqual(self.request("/api/guidance", data, auth=False)[0], 401)
        self.assertEqual(self.request("/api/guidance", dict(data, acceptance="Changed"))[0], 400)
        self.assertEqual(self.request("/api/guidance", data)[0], 200)
        self.assertEqual(self.request("/api/guidance", dict(data, body="Use the state file"))[1][0]["version"], 2)
        self.assertEqual(state.goal(goal["id"])["acceptance"], "Original criteria")
        snapshot = self.request("/api/state")[1]
        self.assertEqual(snapshot["goal_progress"][goal["id"]]["guidance"][0]["body"], "Use the state file")
        self.assertEqual(self.request("/api/guidance", dict(data, action="clear"))[1], [])

    def test_resume_after_update_preserves_external_deadline(self):
        state = State(self.root)
        goal = state.add_goal("Goal", "Work", "Original criteria")
        state.update_goal(goal["id"], status="waiting", next_run=9999999999)
        state.set("paused", True)
        self.request("/api/control", {"action": "resume"})
        self.assertEqual(state.goal(goal["id"])["next_run"], 9999999999)
        self.request("/api/control", {"action": "retry", "goal_id": goal["id"]})
        self.assertEqual(state.goal(goal["id"])["next_run"], 0)
