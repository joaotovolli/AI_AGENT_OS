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
local bearer token; browser requests also enforce Host and Origin checks. The optional GitHub
channel queues authorized status-issue comments as context, with durable IDs and receipts. It
does not expose dashboard controls or execute arbitrary issues. There are no remote CDN assets
or unauthenticated execution endpoints.

## Goal lifecycle

Goals begin queued. Bootstrap has priority and gates all user goals. A selected goal becomes
running and records an attempt. A working result can propose continuation, blockage or completion.
The controller executes the repository regression suite and any owner-provided acceptance commands.
When completion is claimed, a separate Codex session reviews the actual evidence in read-only mode.

An accepted result remains provisional until its verified workspace fingerprint still matches,
its checkpoint is pushed, and the stable branch/runtime activation succeeds. Failure at any step
keeps the goal open. Pending accepted follow-ups also prevent completion until addressed.
The working agent returns completed when its own work/evidence are ready; it must not wait for
these later supervisor gates. The read-only reviewer inspects the supplied deterministic
results without trying to rerun mutating tests in a read-only sandbox. A pause interrupts the process group; resume requeues it. Cancellation is
persistent. Recovering a crashed worker requeues interrupted attempts without losing their history.

Successful unfinished attempts continue after a short scheduling interval. Errors use exponential
backoff, capped at one hour by default; quota, authentication and configuration errors start at
60 seconds. Missing operator input, authentication or configuration enters blocked (Needs input),
retains user-goal priority and waits for an explicit retry or authorized follow-up. External
dependencies wait at least five minutes. Neither class invokes a diagnostic advisor.
There is no maximum goal attempt count. The individual working turn is limited to
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
| `.agent-os/config.json` | Original local model/runtime configuration, readable by older retained runtimes |
| `.agent-os/features.json` | Opt-in operator/advisor and update settings |
| `docs/history/<goal-id>/` | Compact, versioned operational history |
| `workspace/<project>/project.json` | Validated project access metadata |
| `.agent-os-base.json` | Source repository, branch and inherited base commit |
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

## History, advice and framework evolution

Additive SQLite tables store per-goal history and follow-up delivery, separately from the rolling
event stream. Dirty histories are exported in chunks during the normal checkpoint. Consecutive
identical entries are compacted with repetition ranges. The last 12 entries inform new attempts;
older context remains in per-goal Git files. Recovery restores those ranges and message receipts.

The optional diagnostic advisor requires an explicit evidence-backed strategic request; historical
stall signals and distinct unsuccessful approaches are safety floors, not automatic triggers. A persisted reservation, bounded read-only turn and cooldown prevent
immediate duplicate consultations. Its short recommendation returns to the worker. Catalog
metadata and explicit operator preferences select candidates; model names are not capability
ranks. See [diagnostics](DIAGNOSTICS.md) for the trigger, controls and limits.

Generated project code stays outside core runtime snapshots. The console discovers validated
manifests and links to each project surface. See [projects](PROJECTS.md) for the handoff contract.

Framework checks fetch and diff the recorded base at most daily without inference. Explicit
paused updates merge managed paths in a disposable worktree, validate and scan the result,
publish/confirm the candidate, fast-forward source and activate. Conflicts stop before source
replacement; instance state and project areas are excluded. Publication and activation are
separate operations, with documented recovery for a failure between them. See
[framework updates](FRAMEWORK_UPDATES.md).

## Trust and boundaries

All components run under the owner's Linux account. Full-access Codex can technically modify its
own controller or bypass application conventions. Runtime snapshots and acceptance checks protect
against ordinary failures; they are not protection against a malicious agent with the same privileges.
The read-only review is an independent session, not a mathematical proof of correctness.

Acceptance commands are explicitly entered by the dashboard operator and run through Bash. New
incoming GitHub issues do not authorize shell execution. Each instance is isolated by its own
repository, state and services, but host-level access is shared across instances.

## Goal continuity and conditional waiting (0.3)

Additive `guidance`, `work_items`, `goal_control` and `watchers` tables preserve goal-scoped
instructions and dependency state. Each new worker prompt receives active guidance and the saved
work plan separately from one-shot context and immutable acceptance criteria. A context revision
prevents stale completion after operator guidance or a background event arrives during a turn.

The scheduler runs independent actionable work first. Repeated equivalent external blockers use
stable observations and persisted bounded backoff. Deterministic background watchers evaluate
sanitized file, JSON and HTTP predicates with a bounded thread pool, without invoking the model.
Matching events requeue only the associated waiting work; completion still requires all existing
gates. Terminal goals deactivate guidance and watchers. Recovery checkpoints include these tables.
Resume preserves waiting deadlines. See [waiting](WAITING.md) and [operators](OPERATORS.md).


## Adaptive strategy (0.4)

The additive `strategies` table keeps source-backed diagnoses, alternatives, preparation, rejected
approaches, decisions and advice outcomes per work item. Results update these concise operational
records and prompts receive them across restarts. Documented future availability takes precedence
over generic backoff or polling, while independent work retains priority. `docs/STRATEGY.md` defines
the contract and limits of model-authored evidence.

Read-only advice distinguishes higher reasoning from a stronger model and receives a consolidated
dossier. Follow-up consultations require recommendation trials and new evidence. A separate opt-in
permits one bounded, justified expert execution turn after useful advice. The helper cannot complete
the goal or replace the plan; the base model resumes and existing completion gates remain intact.
New preferences use `.agent-os/strategy-settings.json` to preserve retained runtime compatibility.
