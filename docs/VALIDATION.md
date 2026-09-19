# Validation record

## Initial implementation

Validation date: 2026-09-12. Environments: a Linux container with Python 3.12.14 and GitHub
Actions Ubuntu runners with Python 3.11, 3.12 and 3.13. These are not the owner's WSL2 host.

Automated checks performed:

- 36 standard-library regression and integration tests passed.
- Actual subprocess fixtures exercised Codex JSONL consumption, output schema validation,
  provider quota errors, timeout and cancellation without consuming model tokens.
- Actual HTTP requests exercised local authentication, host/origin validation, goal creation,
  pause/resume/cancellation, settings persistence and protected endpoints.
- Actual temporary Git repositories and a bare remote exercised checkpoints, remote SHA
  confirmation, credential rejection, remote divergence and runtime version activation.
- Controller tests exercised working-turn/review ordering, failed acceptance checks, quota
  backoff, GitHub failures before completion, pending-completion recovery, changed-evidence
  invalidation and hourly maintenance scheduling.
- Python compilation, Bash syntax and browser JavaScript syntax were checked.
- GitHub Actions completed successfully on all three Python versions and in a separate Chromium
  browser job. [Passing run](https://github.com/joaotovolli/AI_AGENT_OS/actions/runs/34696972138),
  tested implementation commit `52cef548ebb69e598c3aa2eb002a465230bed343`.
- Real Chromium exercised goal submission, model/reasoning/Fast persistence after reload, pause,
  resume, cancellation, access-fragment removal, text-injection prevention and absence of page
  JavaScript errors. Viewports were 1440x1000 and 390x844; the narrow layout had no horizontal
  overflow. Screenshots and the result summary are available in that run's browser-evidence
  artifact, retained for 14 days. Screenshot retrieval for manual inspection was unavailable
  in the build environment, so manual visual acceptance remains part of host commissioning.

The initial tests use a fake Codex executable and mocked GitHub HTTP calls where appropriate.
They verify controller behavior; they do not prove that the owner's installed Codex version,
account, model access, Fast entitlement, Linux services or Windows integration work.

## English project baseline

On 2026-09-12, the interface, documentation, installation prompts and test examples were
converted to English. Working and review prompts now require English reports and evidence.
The installation guides distinguish installing the existing base from explicitly creating
a separate private repository such as `AI_AGENT_OS_1`.

All 36 local tests and the compilation, syntax and tracked-content checks passed. GitHub
Actions also passed on Python 3.11, 3.12 and 3.13 and in the Chromium desktop/mobile workflow:
[passing run](https://github.com/joaotovolli/AI_AGENT_OS/actions/runs/34710641713), tested
commit `76999c3fcd9e7a4fc8e48d077f2feee55095a6be`. Actual WSL2 commissioning remains pending.

## Version 0.2: instance lifecycle improvements

Validation date: 2026-09-13. The change and GitHub validation jobs are linked from
[PR #7](https://github.com/joaotovolli/AI_AGENT_OS/pull/7) and its
[checks](https://github.com/joaotovolli/AI_AGENT_OS/pull/7/checks).

The local Linux suite contains 75 regression and integration tests. Coverage includes:

- History surviving the rolling event window, repeated-attempt compaction, per-goal restoration,
  sanitization, cancelled-goal retention and feature settings readable by retained older runtimes.
- Authorized follow-up intake, current permission/identity checks, pagination, edited-comment
  deduplication, interrupted delivery, ambiguous receipt publication and third-party marker spoofing.
- Diagnostic trigger exclusions for progress and nontechnical dependencies, bounded read-only
  advice, unchanged worker settings, durable reservations, duplicate advice and advisor memory
  beyond the recent context window. Codex outcomes and GitHub HTTP responses use fixtures here.
- Real temporary Git repositories with independent instance history: base discovery, three-way
  merges, compatible local core edits, source conflicts, failed tests, rejected remote pushes,
  source changes during validation, resume during validation and retained runtime activation.
  Workspace content, goals, settings and local tokens are checked for preservation.
- Authenticated HTTP history/settings/update endpoints, blocked-goal retry, pause preservation,
  cancellation, and a follow-up arriving before a pending completion is accepted.

The Chromium workflow also covers optional settings persistence, separate project links, open
history surviving polling, and the update pause gate, alongside existing desktop/mobile,
authentication, goal, cancellation and text-injection checks. Browser screenshots are saved in
the CI artifact for 14 days. Python compilation, installer/JavaScript syntax and tracked-content
credential checks remain required gates.

These checks validate the framework in Linux fixtures. They do not perform a live diagnostic
consultation, operate a real instance through status comments, apply an update to a user's WSL2
installation or prove provider entitlement. The public base change does not modify existing
instances. Target-host commissioning remains an explicit deployment step below.

## Version 0.3: persistent guidance and productive waiting

Validation date: 2026-09-19. [PR #12](https://github.com/joaotovolli/AI_AGENT_OS/pull/12)
contains the implementation and its [CI checks](https://github.com/joaotovolli/AI_AGENT_OS/pull/12/checks).

The regression suite contains 103 tests. New coverage includes:

- One-shot delivery versus persistent goal guidance; replacement, clearing, authorized GitHub
  commands, replay deduplication, restart and checkpoint recovery, and terminal cleanup.
- Stable observation digests, timestamp/percentage exclusion, changed evidence and approaches,
  bounded external backoff, useful-check deadlines and explicit operator wake-up.
- Mixed actionable, externally waiting, operator-dependent and verified work; dependency ordering,
  preservation of completed work, eventual verified completion and incomplete-plan rejection.
- Deterministic condition polling without model calls, persistent baselines, backoff, change events,
  errors, expiry, cancellation and stale observations arriving after completion/cancellation.
- Guidance and watcher events arriving during a turn, preventing stale completion or lost wake-up.
- Real Git framework integration preserving goals, guidance, work plans, watcher state, settings,
  project files and the previous runtime. Resume keeps external waiting deadlines.
- Authenticated guidance endpoints with immutable-criteria enforcement. Chromium checks create,
  replace, reload and clear guidance, and verify that refresh does not erase an unfinished draft.

The initial candidate passed the three-version Python matrix and Chromium desktop/mobile workflow
in [run 35473272636](https://github.com/joaotovolli/AI_AGENT_OS/actions/runs/35473272636).
Final results for subsequent commits are attached to the PR checks. Model outputs, provider APIs
and remote publication failures are controlled fixtures; real local Git repositories and HTTP
dashboard requests exercise integration. No target-host update or authenticated model turn is
claimed by these tests. Apply the validated base update on the target instance and inspect its
project health before resuming, following [the update guide](FRAMEWORK_UPDATES.md).

## Required WSL2 commissioning

These checks remain pending until the installation prompt is executed on the target host:

- Authenticate and run the actual selected Codex CLI model using the adapter's arguments.
- Verify standard/Fast behavior with the account's available service tiers.
- Execute the bootstrap goal and an independently verified sample goal with real GitHub pushes.
- Verify the dashboard visually and interactively in the owner's Windows browser. Chromium
  automation passed on GitHub's Linux runner; actual Windows-to-WSL access is a separate check.
- Install and verify the per-user systemd services, unattended sudo, Windows startup shortcuts
  and WSL keep-alive. Confirm behavior without an open terminal.
- Exercise service restart, pause/resume, an idle maintenance cycle and the final hourly schedule.
- Confirm that GitHub Actions also passes after any changes made during host commissioning.

Update this record with actual versions, dates, commit IDs and outcomes. Failed checks must stay
visible until resolved. A passing test suite is evidence of tested behavior, not a guarantee of
perfect or universally successful autonomous operation.
