# Adaptive strategy verification

Date: 2026-09-20. Version: 0.4.0. Scope: public framework behavior for issue #13.

## Automated evidence

| Behavior | Regression evidence |
| --- | --- |
| Known time/window beats generic backoff; mixed schedule/watcher uses earliest useful check | Strategic scheduling tests |
| Research, alternatives and preparation precede waiting/watching | Strategic validation and worker preparation tests |
| Aggregate refinement preserves pending real validation and original criteria | Aggregate refinement test |
| Research, rejected hypotheses and preparation survive restart/checkpoint recovery | Strategic recovery and hypothesis archival tests |
| Repeated labels do not create methodological diversity; rejected methods need new evidence | Method-signature and rejected-method tests |
| Counts cannot override no-escalation decisions or an incomplete dossier | Reflective request tests |
| External, information and access constraints do not buy technical advice | Constraint test |
| Higher reasoning and different models are distinct catalog-confirmed resources | Resource selection and advisor tests |
| First advice is read-only; later advice needs trials and new evidence in an updated dossier | Reflective consultation tests |
| Advisor may recommend no further escalation; base receives the recommendation | Second-consultation test |
| Scoped execution needs separate opt-in, useful advice, trials and explicit scope | Delegation gate tests |
| Helper cannot complete overall goal; success/failure returns to base after restart | Scoped worker integration and reservation tests |
| Pause/context changes invalidate advice; existing completion/publication gates remain | Advisor, worker and framework suites |
| Retained runtime configuration remains readable | Separate strategy settings test |
| Strategy details survive refresh; scoped setting persists | Chromium desktop/mobile workflow |

Commands: `python3 -m unittest discover -s tests -v`, `python3 -m compileall -q agent_os scripts tests`,
`bash -n scripts/install-wsl.sh`, `node --check agent_os/static/app.js`,
`python3 scripts/check_repository.py`. CI repeats regression on Python 3.11, 3.12 and 3.13 and runs
`tests/browser_smoke.cjs` in Chromium. The initial implementation passed 122 tests and all four CI
jobs. The final revision extends the suite to 126 tests, including scoped failure/restart, aggregate
refinement, strict result validation, advice IDs preserved across Git recovery and persistent dashboard details.

## Practical limits

Controller tests use simulated model results; they do not prove research quality or intelligence
of a live model. Provider entitlement, successful real-world diagnosis and WSL host operation remain
environment-dependent. A fixture cannot satisfy a requirement for real evidence. Stronger execution
is off by default and never silently changes the configured working model. The paused update flow
validates and publishes each instance's candidate before activation and retains its old runtime.
