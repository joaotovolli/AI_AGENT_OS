# Install on WSL2

Use Ubuntu 24.04 or another distribution with Python 3.11+, Git, `gh`, Codex CLI and systemd.
Clone into a Linux directory such as `~/projects/AI_AGENT_OS` to keep the database and services
on the Linux filesystem. The agent uses the existing Codex sign-in for the Linux user.

This guide installs the selected repository. To create a separate GitHub project such as
`AI_AGENT_OS_1`, follow [REUSE.md](REUSE.md) first and install from that project's folder.

## Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y python3 git gh nodejs npm
npm install -g --prefix "$HOME/.local" @openai/codex
export PATH="$HOME/.local/bin:$PATH"
gh auth login
gh auth setup-git
codex login
```

Preserve an existing working Node/npm installation. If the current Codex package requires a
newer Node version than the distribution provides, use the official installation instructions
to install a compatible version. Interactive sign-in is required only when authentication is
missing or expired. Keep tokens out of shell history, versioned files and GitHub messages.

Check systemd:

```bash
ps -p 1 -o comm=
```

If it does not return `systemd`, add or update this section in `/etc/wsl.conf`, preserving
other existing settings:

```ini
[boot]
systemd=true
```

Restart that distribution from Windows. Prefer `wsl --terminate DISTRO_NAME` to avoid stopping
other distributions. This also ends a Codex session inside it; resume installation after
reopening WSL. See [Microsoft's systemd guide](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Install the selected repository

To install the base repository itself:

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/joaotovolli/AI_AGENT_OS.git
cd AI_AGENT_OS
bash scripts/install-wsl.sh 8765
```

If the checkout already exists, use it instead of cloning it again. For an instance already
created with `new_instance.py`, change into its directory and run the installer with its
chosen port, for example `bash scripts/install-wsl.sh 8766`.

The installer checks authentication and tests, configures passwordless sudo for the Linux
user, creates the working branch, starts two services and enables linger. It needs initial
sudo access. This grants the full WSL2 administration requested for the agent.

Installation is idempotent for the same instance. Give each instance a distinct folder name
and free port. Services capture the installation PATH, including the Codex executable's path.
Reinstall the services if the executable or repository is moved.

## Start with Windows and create a shortcut

Run inside the installed base repository in WSL:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w scripts/install-windows-startup.ps1)" -Distro "$WSL_DISTRO_NAME" -RepoPath "$PWD" -Instance "ai_agent_os"
```

Use the matching name, such as `ai_agent_os_1`, for a numbered instance. This creates a
startup shortcut for the Windows user, keeps the distribution active and adds a desktop
shortcut for the dashboard. The execution-policy setting applies only to that PowerShell
process. Windows must be on, awake and signed in. Systemd services alone
[do not keep WSL running](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Open and monitor

Use the shortcut or run:

```bash
python3 .agent-os/open.py
```

The browser opens the configured localhost port with local authentication. Microsoft documents
[Windows-to-WSL localhost access](https://learn.microsoft.com/en-us/windows/wsl/networking).
If localhost forwarding is disabled, fix it before declaring installation complete. Keep the
dashboard bound to loopback.

The first goal prepares and tests the instance. **Ready** requires passing tests, actual Codex
execution, independent review, active services and confirmed GitHub publishing. Machine-specific
details are written in English to [ACCESS.md](ACCESS.md) by the installer.
