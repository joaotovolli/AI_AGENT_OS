# Recovery and operation

## The dashboard opens, but the agent is not working

Check pause status, the next attempt time and the displayed error. Exhausted quota triggers
further attempts with backoff. If authentication expired, run `codex login` or `gh auth login`
in WSL2, then choose **Run now**. If your account cannot access the model, change its ID in
the dashboard. Models and credentials are never silently replaced.

The service uses the PATH captured at installation. After moving Codex to another path, run
`python3 scripts/install_services.py` again. Exact service names are in [ACCESS.md](ACCESS.md).

## A faulty change to the system itself

The worker uses an immutable copy of tested code. Source edits do not replace that copy
immediately. If tests fail, the attempt stays on the `agent/...` working branch and the next
execution tries to repair the source using the previous deployed controller.

If a replacement exits unsuccessfully three times, with each run lasting less than 30 seconds,
the launcher restores the previous runtime. The record is in `.agent-os/recovery.log`. This
handles startup failures; errors appearing later depend on regression checks and subsequent
maintenance. The launcher and local opener are copied at installation, so they do not depend
on the source currently being edited.

For manual rollback, stop both services, point `.agent-os/runtime` to the target of
`.agent-os/previous-runtime`, then start the services again. Preserve the failing source on
the working branch for investigation. Do not discard pending work with `git reset --hard`.

## GitHub is unavailable or a branch has diverged

State and code remain local. New paid attempts do not start while the required repository is
unreachable. A failed push leaves a pending checkpoint. Completion is not confirmed until
publication succeeds.

Reconcile independent remote commits without force-pushing. The agent receives the sync error
in its next context and can resolve legitimate divergence. Conflicts requiring an external
decision remain visible. Branch protection that prevents direct pushes must be addressed in
the project configuration or publishing workflow.

If the scanner detects a secret, remove it from the file and any unpublished local commits
before pushing. Keep the scanner enabled. Credentials already published must be revoked at
the originating service.

## Restore goals in a fresh checkout of the same instance

Clone the branch containing the latest checkpoint, including `agent/...` when appropriate.
Before initialising the fresh checkout:

```bash
python3 -m agent_os restore
bash scripts/install-wsl.sh 8765
```

Choose the instance's own port if different. Restore requires an empty local database and the
same repository origin. Incomplete goals return to the queue; bootstrap validates the host
again. The checkpoint does not contain raw logs, credentials or every historical database
detail. For full local recovery, back up `.agent-os` with the services stopped so the SQLite
copy is consistent.

## Remove an installation

Stop and disable the services listed in ACCESS.md, remove their unit files from
`~/.config/systemd/user`, and run `systemctl --user daemon-reload`. Remove this instance's
Windows startup and dashboard shortcuts, and stop its keep-alive process.

The Linux user's sudo permission is shared across instances. Remove
`/etc/sudoers.d/90-ai-agent-os-LINUX_USERNAME` only when no other instance depends on it.
GitHub repositories and project files remain intact unless explicitly deleted.
