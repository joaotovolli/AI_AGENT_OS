"""Ephemeral HTTP fixture for browser tests; never starts Codex or contacts GitHub."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_os.config import token
from agent_os.server import make_server
from agent_os.state import State
from agent_os.projects import register
from agent_os import strategy
from test_strategy import record
from test_goal_progress import item

root = Path(sys.argv[1])
state = State(root)
state.ensure_bootstrap()
state.update_goal("bootstrap", status="running", attempts=1, progress=45,
                  summary="Validating services, persistence and dashboard access.")
state.save_work_plan("bootstrap", [item(status="actionable")])
strategy.save(state, "bootstrap", [record("research")])
state.set("worker_heartbeat", time.time())
state.set("github", {"synced": True, "last_push": time.time(), "repository": "joaotovolli/AI_AGENT_OS"})
state.note("bootstrap", "fixture", "attempt", {"phase": "Service validation", "summary": "Dashboard connectivity verified", "blocker": "", "next_action": "Verify goal execution"}, attempt=1)
state.set("framework", {"status": "available", "target_commit": "a"*40, "message": "A base update is available for validation."})
(root / "workspace/report-viewer").mkdir(parents=True)
register(root, "workspace/report-viewer", {"name": "Report viewer", "url": "http://localhost:8800", "description": "Separate project output", "status": "ready"})
server = make_server(root, port=0)
print(json.dumps({"port": server.server_address[1]}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
