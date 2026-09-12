# Validation record

## Initial implementation

Validation environment: Linux container with Python 3.12.14. This is not the owner's WSL2 host.

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

The initial tests use a fake Codex executable and mocked GitHub HTTP calls where appropriate.
They verify controller behavior; they do not prove that the owner's installed Codex version,
account, model access, Fast entitlement, Linux services or Windows integration work.

## Required WSL2 commissioning

These checks remain pending until the installation prompt is executed on the target host:

- Authenticate and run the actual selected Codex CLI model using the adapter's arguments.
- Verify standard/Fast behavior with the account's available service tiers.
- Execute the bootstrap goal and an independently verified sample goal with real GitHub pushes.
- Verify the dashboard visually and interactively in a real Windows browser, including mobile
  viewport layout. The build environment has no browser engine installed; visual inspection
  was not claimed from static syntax checks.
- Install and verify the per-user systemd services, unattended sudo, Windows startup shortcuts
  and WSL keep-alive. Confirm behavior without an open terminal.
- Exercise service restart, pause/resume, an idle maintenance cycle and the final hourly schedule.
- Confirm that GitHub Actions passes on the published commit.

Update this record with actual versions, dates, commit IDs and outcomes. Failed checks must stay
visible until resolved. A passing test suite is evidence of tested behavior, not a guarantee of
perfect or universally successful autonomous operation.
