# Reproducible host changes

Keep scripts and sanitized change records here whenever a goal changes files outside this
repository. Record the purpose, affected paths, verification and reversal procedure. Never copy
private machine directories or credential files into Git.

The installation's baseline host changes are:

- A validated sudoers entry at `/etc/sudoers.d/90-ai-agent-os-<linux-user>` granting the requested
  unattended administration. This is shared by that Linux user's instances.
- Two per-instance user systemd units and login linger, installed by `scripts/install_services.py`
  and `scripts/install-wsl.sh`.
- Optional Windows startup and dashboard shortcuts installed by `scripts/install-windows-startup.ps1`.

Use text configuration templates with local secret references. Large or binary artifacts should
use a documented Git LFS or release-asset workflow; the automatic source publisher rejects raw
binary files and individual files larger than 5 MiB to keep checkpoints inspectable.
