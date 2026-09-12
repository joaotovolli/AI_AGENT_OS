#!/usr/bin/env python3
"""Stable local opener, copied to .agent-os/open.py on installation."""
import base64
import json
import os
import subprocess
import webbrowser
from pathlib import Path

local = Path(__file__).resolve().parent
settings = json.loads((local / "config.json").read_text())
secret = (local / "dashboard.token").read_text().strip()
url = f"http://localhost:{settings['port']}/#token={secret}"
if os.environ.get("WSL_DISTRO_NAME"):
    script = "Start-Process '" + url + "'"
    encoded = base64.b64encode(script.encode("utf-16le")).decode()
    subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded], check=True)
else:
    webbrowser.open(url)
