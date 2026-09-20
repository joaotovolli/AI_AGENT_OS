# Goal history and diagnostic advice

Each goal retains structured operational summaries in local SQLite independently of the rolling
Recent activity window. Every Git checkpoint exports them into `docs/history/<goal-id>/`.
The index links chronological JSON chunks containing at most 100 distinct groups. Consecutive
identical entries share one record with their attempt/time range and repetition count. Only
goals with new history are exported. Completed and cancelled goals retain separate histories.

An attempt records phase, method and stable approach key, completed milestones, meaningful
progress, blocker category and stable blocker key, summary, next action and verification state.
These are short operational descriptions, not raw commands, transcripts or reasoning traces.
The dashboard shows current context and the latest 100 entries; Git retains earlier context.
Percentages remain estimates. The existing acceptance, independent review, publication and
activation gates determine completion.

## Optional diagnostic advisor

**Diagnostic advisor** is off by default and persists per instance. Enabling it never changes
the normal worker's model, reasoning or Fast settings. A separate read-only Codex session may
analyze one recurring technical blocker and return a different approach to that worker.
Normal implementation and completion review stay in the regular goal lifecycle.

Read [strategic execution](STRATEGY.md) for the decision contract. The worker must explicitly
request advice after researching the cause, considering alternatives, trying evidenced approaches
and assessing exhaustion, clarity and expected value. Attempt counts and diversity are safety floors,
not triggers. The worker can choose research, a new experiment, preparation or scheduled waiting even
when historical stall heuristics are present.

A consolidated dossier preserves the full goal and acceptance criteria, affected work, verified
evidence, research, attempts, rejected hypotheses, current diagnosis, uncertainty and previous advice.
The advisor uses read-only sandboxing, no approval prompts, Standard tier and a 180-second default
timeout. It can recommend that no further escalation is needed. The base model executes its advice
with independent judgment and records recommendation trials.

Reservations are persisted before invocation. A one-hour cooldown, a new request ID, new evidence
and documented trials of the latest advice gate later consultations. The same advisor may revisit
a genuinely updated dossier; duplicate next-action advice is discarded. Pause/cancel and changed
operator context invalidate a stale consultation. Missing access and external timing do not become
reasons to buy more inference.

## Selecting an advisor

The dashboard accepts ordered `model-id reasoning` preferences. Designate models you consider
stronger for diagnosis. Choices must exist in the installed Codex model catalog and explicitly
support the chosen reasoning level. `consult_reasoning` selects the next catalog-supported higher effort for the current model;
`consult_model` selects a different model. Without preferences, the controller follows explicit catalog upgrade suggestions. It
does not infer capability from model names or silently try guessed IDs. If no suitable
candidate is known, history records that limitation and the configured worker stays in control.
Catalog presence is not proof of live entitlement; actual CLI failures are recorded without
silently replacing the worker or bypassing provider limits.

Advanced settings can be changed with `python3 -m agent_os settings --json '<JSON object>'`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `diagnostic_escalation` | `false` | Explicit permission for advisor calls |
| `diagnostic_models` | `[]` | Ordered objects containing `model` and `reasoning` |
| `diagnostic_min_attempts` | `3` | Evidence safety floor; never an automatic trigger |
| `diagnostic_cooldown_seconds` | `3600` | Minimum interval between consultations |
| `diagnostic_timeout_seconds` | `180` | Maximum duration of one consultation |

| `strategic_delegation` | `false` | Additional opt-in for one justified scoped execution turn after useful advice/trials |
| `delegation_timeout_seconds` | `600` | Maximum duration of that scoped turn |

Scoped execution cannot mark the overall goal complete. Normal ownership resumes afterward.
The helper's scope is an instruction under the existing full-access account, not a sandbox.
New delegation preferences live in `.agent-os/strategy-settings.json`, which retained older runtimes
ignore. Existing preferences are unchanged by updates.

Advisor usage is included in the instance token counter. New feature preferences live in ignored
`.agent-os/features.json`; original execution settings remain in `.agent-os/config.json` so
retained older runtime versions can still read their configuration.
