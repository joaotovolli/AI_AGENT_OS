# Integrated autonomy and compact history verification

2026-09-20, version 0.5.0, issue #15.

The complete local regression suite passed: **133 tests**. The affected API, migration, strategy,
advisor, operator and scoped-execution subset passed all 54 tests. Python compilation, shell and
JavaScript syntax checks and the tracked-content scan passed. The Chromium workflow passed with
65 terminal fixture goals, active-only cards, paginated history, on-demand criteria/diagnostic details,
only Model/Reasoning/Fast inputs, cancellation moving a goal into History, mobile layout and text
injection protection. GitHub Actions repeats the full suite on Python 3.11, 3.12 and 3.13.

Reproduction commands:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q agent_os scripts tests
bash -n scripts/install-wsl.sh
node --check agent_os/static/app.js
python3 scripts/check_repository.py
```

`tests/test_integrated_autonomy.py` verifies legacy false flags cannot disable the integrated policy,
base preferences survive, pause/deadlines/guidance/strategies/reservations remain intact, unneeded
escalation is suppressed, justified advice uses catalog selection without feature setup, owner intake
works on its first poll, and terminal history stays paged while full recovery snapshots retain goals.
Existing strategy/advisor tests retain read-only-first, explicit expected value, new evidence, measured
advice outcomes, cooldown, crash reservation and return-to-base requirements for scoped execution.

`tests/test_dashboard.py` verifies authentication, pagination limits, active-only state and retained
original criteria/attempts in historical details. Browser evidence is attached to the PR's CI runs.
All prior acceptance, pause/cancel, authentication, independent review and checkpoint tests remain.

Tests use simulated model outputs. They establish controller behavior, not live reasoning quality or
provider entitlement. Existing goals adopt the new policy on their next normal turn; updates do not
force paid work or resume a paused instance.
