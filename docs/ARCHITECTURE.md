# Architecture

## Process ownership

Two per-user systemd services run a small stable launcher: one worker and one dashboard. The
launcher is copied to `.agent-os/launch.py` during installation. Its only responsibility is to
run the active immutable runtime, restart it and fall back on repeated startup failures.

The worker is the only owner of the instance execution lock. It loads local configuration,
selects the next goal, checks GitHub connectivity and starts `codex exec`. Each attempt has a
new Codex session, with persisted goal state and recent evidence included in the prompt. This
avoids depending on an indefinitely growing session. Codex remains responsible for its own
within-turn reasoning and context handling.

The web server remains available while the worker waits on Codex, GitHub or quota. It reads and
writes the same SQLite database through independent transactions. Dashboard mutations require a
local bearer token; browser requests also enforce Host and Origin checks. There are no remote
CDN assets, unauthenticated execution endpoints or arbitrary GitHub issue ingestion.

## Goal lifecycle

Goals begin queued. Bootstrap has priority and gates all user goals. A selected goal becomes
running and records an attempt. A working result can propose continuation, blockage or completion.
The controller executes the repository regression suite and any owner-provided acceptance commands.
When completion is claimed, a separate Codex session reviews the actual evidence in read-only mode.

An accepted result remains provisional until its verified workspace fingerprint still matches,
its checkpoint is pushed, and the stable branch/runtime activation succeeds. Failure at any step
keeps the goal open. A pause interrupts the process group; resume requeues it. Cancellation is
persistent. Recovering a crashed worker requeues interrupted attempts without losing their history.

Successful unfinished attempts continue after a short scheduling interval. Errors use exponential
backoff, capped at one hour by default; quota, authentication and configuration errors start at
60 seconds. There is no maximum goal attempt count. The individual working turn is limited to
30 minutes by default, followed by another attempt as needed. A verification turn defaults to
10 minutes. These watchdogs prevent one stalled process from disabling the goal indefinitely.

If no user goal is active, the scheduler creates a maintenance goal once the hourly deadline is
due. It checks the system and addresses a concrete reliability or usability issue if one exists.
Completed maintenance schedules the next hour. It does not manufacture code changes just to be busy.

## Source, deployment and GitHub

| Location | Purpose |
| --- | --- |
| `agent_os/` | Editable controller and dashboard source |
| `workspace/` | Project work produced for goals |
| `infra/` | Reproducible host changes and sanitized records |
| `docs/evidence/` | Goal completion evidence |
| `.agent-os/state.sqlite3` | Local transactional state, attempts and recent events |
| `.agent-os/config.json` | Local model/runtime configuration |
| `.agent-os/runs/` | Private prompts, outputs and bounded logs |
| `.agent-os/releases/` | Immutable deployed controller versions |
| `.agent-os/runtime` | Active release symlink |
| `.agent-os/previous-runtime` | Rollback release symlink |
| `state/checkpoint.json` | Sanitized Git recovery snapshot |
| `STATUS.md` | Human-readable status at the last Git checkpoint |

Installation creates `agent/<instance-folder>` from the repository's default branch. Every
attempt stages and checks the working tree, commits its changes and pushes this branch. Every
unpushed commit is also checked. The remote branch is verified against the pushed SHA. No force
push is used. A divergent remote requires reconciliation and remains visible as a pending sync.

Passing changes can advance the stable branch by fast-forward and activate a new immutable
runtime copy. The dashboard and worker restart to pick up that copy. A failing source edit stays
on the working branch while the old deployed code continues running. The launcher records child
process identity so it can clean up an orphaned Codex process after a worker crash.

One GitHub status issue is updated about once per minute while the worker is active. The dashboard
polls every three seconds. Meaningful model progress can be reported using the documented local
`progress` command. Raw command output is retained locally; public progress uses event types,
sanitized summaries and goal status. API throttling can delay GitHub updates.

The repository includes experimental code as well as successful code. CI failures on working
branches are evidence to repair, and do not automatically replace the deployed runtime.

## Trust and boundaries

All components run under the owner's Linux account. Full-access Codex can technically modify its
own controller or bypass application conventions. Runtime snapshots and acceptance checks protect
against ordinary failures; they are not protection against a malicious agent with the same privileges.
The read-only review is an independent session, not a mathematical proof of correctness.

Acceptance commands are explicitly entered by the dashboard operator and run through Bash. New
incoming GitHub issues do not authorize shell execution. Each instance is isolated by its own
repository, state and services, but host-level access is shared across instances.
