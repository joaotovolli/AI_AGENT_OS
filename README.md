# AI Agent OS

[![CI](https://github.com/joaotovolli/AI_AGENT_OS/actions/workflows/ci.yml/badge.svg)](https://github.com/joaotovolli/AI_AGENT_OS/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reusable, self-hosted execution supervisor for **Codex CLI on WSL2**. Define a goal in the
dashboard, choose a model, and let the worker continue through implementation, verification
and further attempts. GitHub stores code, instructions and progress.

**Version 0.2.0.** The controller and its automated tests are implemented. The target machine
must still complete authenticated WSL2 commissioning. The system never claims to be error-free.

## Project status

- **Maturity:** Alpha / active development
- **Runtime:** WSL2 with Python 3.11+
- **Verification:** Python 3.11/3.12/3.13 regression suite plus Chromium dashboard workflow
- **License:** MIT

The project has automated CI and repeatable validation, but the target-host commissioning steps
in the validation record remain part of deployment readiness.

## Start here

1. To run the existing base, give Codex the [WSL2 installation prompt](docs/IMPLEMENTATION_PROMPT.md).
   To create a separate project, use the [AI_AGENT_OS_1 prompt](docs/NEW_INSTANCE_PROMPT.md) instead.
2. Follow the generated [dashboard access instructions](docs/ACCESS.md).
3. Let the automatic bootstrap goal pass its readiness checks.
4. Add your first [goal](docs/GOALS.md). Goals submitted during bootstrap wait in the queue.

The default dashboard address is **http://localhost:8765** after installation. The Windows
shortcut opens it with local authentication. The interface, documentation, prompts and generated operating instructions are in English.

## Behavior

| Requirement | Implementation |
| --- | --- |
| Full WSL2 administration | Working Codex turns run without the Codex sandbox or approval prompts. Installation configures unattended sudo for the Linux user. |
| GitHub records every attempt | Code, sanitized goal state and progress checkpoints go to an instance working branch; tested changes advance the stable branch. |
| Instructions live in GitHub | Installation, access, operation, recovery and host changes are documented in Markdown and reproducible scripts. |
| Choose the Codex model | Default `gpt-5.6-luna`, reasoning `medium`; free-form model and reasoning fields, plus Fast. No silent fallback. |
| Persist until completion | SQLite state, process recovery, bounded individual turns, unlimited subsequent attempts and explicit verification. |
| GitHub operator follow-ups | Opt-in, authorized status-issue comments enter the goal queue with durable receipts and replies. |
| Per-goal diagnostics | Compact history survives the live activity window and is published separately for each goal. |
| Optional diagnostic advisor | A bounded read-only consultation can help with a repeated technical blocker; the worker model stays unchanged. |
| Framework updates | Recorded provenance, daily discovery and explicit validated integration preserve instance work and retain the previous runtime. |
| Separate projects | Project manifests expose access links without embedding generated products into the control console. |
| Hourly idle improvement | After the queue clears, health and justified improvement goals run every 3,600 seconds by default. |

The scheduler runs locally, not on GitHub Actions. Actions runs the regression suite without
Codex credentials. The machine must be on and WSL2 must be running for execution to continue.

## Runtime guarantees and limits

- A separate, immutable copy of the last tested controller keeps operating while Codex edits
  source. A new copy activates after tests and GitHub publishing pass. The stable launcher can
  restore the previous runtime if a replacement repeatedly fails to start.
- A goal is complete only after deterministic checks, a separate read-only Codex review and a
  confirmed GitHub checkpoint. Progress percentages are estimates, not proof of completion.
- Quota exhaustion and outages preserve the goal and trigger backoff. Missing operator input,
  authentication or configuration can enter **Needs input**, stopping paid retries until the
  dependency is addressed. Automatic retries do not bypass limits or create tokens. The
  application does not know the remaining account quota.
- Full access is intentional and powerful. The agent can change the Linux host and any mounted
  paths accessible to that user, including Windows mounts. This is not a security sandbox.
- Credentials and raw runtime logs remain local. Common credential formats are checked before
  publishing, but automated scanning cannot recognize every possible secret.

## Develop and verify

Python 3.11+ is sufficient for the controller. No third-party Python packages, database server,
Node build step or OpenAI API key are required. Codex CLI uses its existing local sign-in.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q agent_os scripts tests
bash -n scripts/install-wsl.sh
node --check agent_os/static/app.js
python3 scripts/check_repository.py
```

Node is used for JavaScript syntax validation and by the npm installation of Codex CLI. The dashboard itself is served as static HTML, CSS and JavaScript.

Contributions are welcome through focused pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the development checks and [SECURITY.md](SECURITY.md) for security reporting guidance.

Read the [architecture](docs/ARCHITECTURE.md), [validation record](docs/VALIDATION.md),
[Codex settings](docs/CODEX.md), and [reusable instance guide](docs/REUSE.md).

New in 0.2: [operator follow-ups](docs/OPERATORS.md), [goal diagnostics and advisor](docs/DIAGNOSTICS.md),
[project organization](docs/PROJECTS.md), and [safe framework updates](docs/FRAMEWORK_UPDATES.md).
Follow-ups and diagnostic escalation are disabled by default. Existing instances adopt updates
explicitly; publishing a new base version does not change a running instance.

The [initial CI run](https://github.com/joaotovolli/AI_AGENT_OS/actions/runs/34696972138) passed
36 tests on Python 3.11/3.12/3.13 and a real Chromium dashboard workflow on desktop and mobile
viewports. The browser job uses Playwright as a development-only dependency.
