"""Ephemeral HTTP fixture for browser tests; never starts Codex or contacts GitHub."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_os.config import token
from agent_os.server import make_server
from agent_os.state import State

root = Path(sys.argv[1])
state = State(root)
state.ensure_bootstrap()
state.update_goal("bootstrap", status="running", attempts=1, progress=45,
                  summary="Validando serviços, persistência e acesso ao dashboard.")
state.set("worker_heartbeat", time.time())
state.set("github", {"synced": True, "last_push": time.time(), "repository": "joaotovolli/AI_AGENT_OS"})
server = make_server(root, port=0)
print(json.dumps({"port": server.server_address[1]}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
