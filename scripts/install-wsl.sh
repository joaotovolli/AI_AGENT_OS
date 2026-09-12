#!/usr/bin/env bash
set -euo pipefail
AGENT_REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AGENT_REPO_ROOT"
AGENT_PORT="${1:-8765}"
if [[ "$(id -u)" == 0 ]]; then
  echo 'Run this installer as your normal WSL user; it configures sudo and user services.' >&2
  exit 1
fi
for dependency in python3 git gh codex sudo systemctl; do
  command -v "$dependency" >/dev/null || { echo "Missing prerequisite: $dependency. See docs/INSTALL_WSL2.md." >&2; exit 1; }
done
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [[ "$(ps -p 1 -o comm=)" != systemd ]]; then
  echo 'Enable systemd in /etc/wsl.conf, then restart WSL from Windows. See docs/INSTALL_WSL2.md.' >&2
  exit 1
fi
gh auth status >/dev/null 2>&1 || { echo 'GitHub login required: gh auth login' >&2; exit 1; }
codex login status >/dev/null 2>&1 || { echo 'Codex login required: codex login' >&2; exit 1; }
gh auth setup-git
AGENT_LINUX_USER="$(id -un)"
[[ "$AGENT_LINUX_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || { echo 'Unsupported Linux username for sudoers setup'; exit 1; }
AGENT_SUDO_FILE="$(mktemp)"
trap 'rm -f "$AGENT_SUDO_FILE"' EXIT
printf '%s ALL=(ALL:ALL) NOPASSWD: ALL\n' "$AGENT_LINUX_USER" > "$AGENT_SUDO_FILE"
echo 'Configuring the full WSL2 administration access requested for this instance.'
sudo visudo -cf "$AGENT_SUDO_FILE"
sudo install -m 0440 -o root -g root "$AGENT_SUDO_FILE" "/etc/sudoers.d/90-ai-agent-os-$AGENT_LINUX_USER"
sudo -n true
python3 -m unittest discover -s tests -v
python3 -m agent_os --root "$AGENT_REPO_ROOT" init --port "$AGENT_PORT"
python3 scripts/install_services.py
sudo loginctl enable-linger "$AGENT_LINUX_USER"
python3 -m agent_os --root "$AGENT_REPO_ROOT" doctor
echo "Dashboard: http://localhost:$AGENT_PORT"
echo 'Open with access: python3 -m agent_os open'
echo 'Bootstrap now works automatically. Runtime progress is published to the instance status issue.'
