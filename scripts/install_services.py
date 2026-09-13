#!/usr/bin/env python3
"""Generate per-instance systemd services and accurate access instructions."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_os import config
from agent_os.github import GitHub
from agent_os.state import State


def quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def main():
    local = config.private_dir(ROOT)
    settings = config.load(ROOT)
    instance = re.sub(r"[^A-Za-z0-9_-]", "-", ROOT.name).lower()
    if not instance:
        raise SystemExit("Invalid instance name")
    units = Path.home() / ".config" / "systemd" / "user"
    units.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "launch.py", local / "launch.py")
    shutil.copy2(ROOT / "scripts" / "open_dashboard.py", local / "open.py")
    service_names = []
    for suffix, mode in (("worker", "worker"), ("dashboard", "serve")):
        name = f"ai-agent-os-{instance}-{suffix}.service"
        service_names.append(name)
        content = f"""[Unit]
Description=AI Agent OS {instance} {suffix}
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory={str(ROOT).replace('%', '%%')}
ExecStart={quote(sys.executable)} {quote(local / 'launch.py')} {quote(ROOT)} {mode}
Environment={quote('PATH=' + os.environ['PATH'])}
Restart=always
RestartSec=5
TimeoutStopSec=20
KillMode=control-group
UMask=0077

[Install]
WantedBy=default.target
"""
        (units / name).write_text(content)
    config.atomic_json(local / "installation.json", {"instance": instance, "services": service_names,
                        "root": str(ROOT), "port": settings["port"], "distro": os.environ.get("WSL_DISTRO_NAME", "")})
    repo, branch = GitHub(ROOT, State(ROOT)).identity()
    access = f"""# Access this instance

Instance: `{ROOT.name}`. Dashboard: **http://localhost:{settings['port']}**.

Open the installed Windows shortcut, or run inside this repository:

```bash
python3 .agent-os/open.py
```

The command opens a local authenticated link. The access token stays in `.agent-os/dashboard.token`;
never paste it in GitHub, screenshots or chat. A plain dashboard URL asks for this local token.

## Services

```bash
systemctl --user status {' '.join(service_names)}
journalctl --user -u {service_names[0]} -n 80 --no-pager
python3 -m agent_os status
python3 -m agent_os doctor
```

Pause or resume in the dashboard. Pause interrupts the current Codex process and its descendants.
To stop both services:

```bash
systemctl --user stop {' '.join(service_names)}
```

To start again, replace `stop` with `start`. The services start when WSL2 starts.
For automatic WSL startup and a dashboard shortcut at Windows sign-in, run from this repository:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w scripts/install-windows-startup.ps1)" -Distro "$WSL_DISTRO_NAME" -RepoPath "$PWD" -Instance "{instance}"
```

The installer uses a per-user startup shortcut. It does not change the machine execution policy.
Windows must be awake and signed in; no process can work while the machine is off or suspended.

## GitHub and recovery

Live status is the issue titled `Agent OS status: {ROOT.name}` in `{repo}`.
Every attempt is checkpointed on `{branch}`. Tested changes also advance the stable branch.
See [recovery](RECOVERY.md), [goals](GOALS.md), and [model settings](CODEX.md).
"""
    (ROOT / "docs" / "ACCESS.md").write_text(access)
    State(ROOT).set("needs_checkpoint", True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", *service_names], check=True)
    for service in service_names:
        subprocess.run(["systemctl", "--user", "is-active", service], check=True)
    print("Installed services: " + ", ".join(service_names))


if __name__ == "__main__":
    main()
