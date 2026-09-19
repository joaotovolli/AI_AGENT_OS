# Base framework updates

New instances created with `scripts/new_instance.py` record their source repository, branch and
exact base commit in `.agent-os-base.json`. Copies of an existing instance retain its inherited
base provenance. Each instance keeps its own `origin`, branches, workspace, settings and state.

The supervisor checks upstream at most once per day by default (`framework_check_seconds`).
Use **Check for updates** for an immediate check. This fetch/diff uses Git without model inference.
Checks do not modify source or activate fetched code. Updates are never applied automatically.

## Apply a known update

1. Checkpoint instance changes and inspect the reported upstream commit.
2. Pause the instance and wait until its current attempt has stopped.
3. Select **Apply validated update**. The request pins the displayed commit.
4. Review the result, project access and dashboard. Resume after the update succeeds.

The worker prepares a disposable Git worktree, performs three-way merges against the recorded
base, and runs the resulting instance's regression suite and Python/shell/JavaScript syntax
checks. Tests must not modify candidate source. Credential scanning remains a publication gate.
Only a validated candidate can be committed and pushed to the instance branch. Its remote SHA
must be confirmed before fast-forwarding local source, advancing the stable branch and activating
an immutable runtime. The previous runtime is retained. The instance remains paused for review.

| Area | Update treatment |
| --- | --- |
| `agent_os/`, `scripts/`, `tests/`, `.github/` | Three-way framework integration |
| Framework README, agreement, packaging, license and contributor/security documents | Three-way integration |
| Framework `docs/` | Three-way integration, except instance records below |
| `workspace/`, `infra/` | Preserved |
| `docs/ACCESS.md`, `docs/VALIDATION.md`, `docs/evidence/`, `docs/history/` | Preserved |
| `state/`, `.agent-os/`, credentials and runtime snapshots | Preserved |

Clean nonoverlapping instance changes survive integration. Conflicting edits, add/delete conflicts,
symlinks, unsupported binary changes, invalid provenance, dirty source, failed tests and rejected
pushes stop the update. Before publication/fast-forward, failure leaves source and runtime intact.
No automatic destructive conflict resolution or force push is used. Inspect the named conflict,
reconcile it deliberately in source, test/checkpoint, and request the update again.

Git publication, stable-branch promotion and local activation are not one atomic transaction.
If publication succeeds but a later step fails, the validated commit may already be on GitHub
or in local source while the previous runtime remains active. Keep the instance paused, inspect
`git status`, the remote branches and [runtime recovery](RECOVERY.md), and complete or roll back
activation deliberately. An interrupted apply is not automatically replayed on restart.

## Command-line operation

The CLI must acquire the worker lock. Stop the worker service first; use the dashboard when the
worker is running. Read the service name in the instance's `docs/ACCESS.md`.

```bash
python3 -m agent_os framework check
python3 -m agent_os framework apply --commit <full-upstream-commit>
```

The command-line apply sets the instance paused. It does not restart services that you stopped.

## Adopt an older instance

Older repositories do not contain provenance and must not guess it. Determine the exact base
commit they originally inherited from their creation history. Keep an independent clean checkout
of the current base and stop the older instance's worker and dashboard services. Back up its
ignored `.agent-os/` directory locally and checkpoint its own source first.

Run the current base's management wrapper without replacing the older source:

```bash
python3 /path/to/AI_AGENT_OS/scripts/manage.py --root /path/to/instance \
  framework adopt --repository joaotovolli/AI_AGENT_OS --commit <original-base-commit>
```

Review and commit `.agent-os-base.json` in the instance using its normal Git workflow. Then use
the same wrapper with `framework check` and `framework apply --commit <reported-target>`.
If the older instance changed core code, integration may stop on conflicts; resolve these with
evidence, preserving its project work. After successful activation, start its services and review
before resuming. No existing instance is modified merely by updating the public base repository.

## Upgrading a running 0.2 instance to 0.3

Publish the update to the base first. In the instance, **Check for updates** discovers the available
base commit. **Apply validated update** is the separate explicit action that automatically prepares,
merges, tests, publishes and activates it after the worker is paused. Checking alone never deploys
code. No manual copying of source files is required for a clean integration.

The 0.2 updater can install this release: database additions are created when the new runtime
starts, and existing goals, follow-up receipts, attempt history, model settings and projects stay
in place. There are no destructive schema migrations or new goal status strings. New waiting
settings use a separate file that older retained runtimes ignore. A rollback retains the new
SQLite tables but does not implement the new guidance/watcher behavior; keep the worker paused
until the desired runtime is restored and inspected.

Pause interrupts the active bounded Codex attempt and retains its work. The dashboard stays
available during candidate validation and restarts briefly for runtime activation. Separate project
services are not restarted by the framework updater and can continue operating. This is not a
zero-downtime guarantee for services coupled to the control runtime or applications with their own
update procedures. Check the instance's project health after activation, then resume the worker.

Resume preserves external waiting deadlines, verified work and condition watcher state. Use Retry
if immediate reassessment is required. Existing one-shot comments remain one-shot; save ongoing
instructions explicitly as persistent guidance. The first new attempt can derive a work plan from
the original criteria and existing evidence without restarting the project.

Local tests cover real Git integration and preservation of goals, guidance, waiting state, watcher
observations, settings and project files. They cannot prove that every customized live instance will
merge cleanly. A conflict or candidate-test failure must leave the previous source/runtime available
and report the exact issue. Never resolve a conflict by replacing the instance's project code.
