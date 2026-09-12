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
