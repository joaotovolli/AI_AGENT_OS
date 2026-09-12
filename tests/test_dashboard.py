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
