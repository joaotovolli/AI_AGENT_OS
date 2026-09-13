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

The initial conservative trigger requires at least three attempts against the same technical
blocker, three distinct approach keys, no reported meaningful progress and no changed completed
milestone. More attempts can be required using `diagnostic_min_attempts`. A new blocker or real
progress resets the window. Stable keys and summaries are supplied by the worker: they are
observable heuristics, not proof that two methods differ semantically. Incorrect classification
should be corrected through operator context and evidence.

Operator, authentication and configuration dependencies enter **Needs input**, preserving queue
priority and stopping paid attempts until **Retry goal** or an authorized follow-up. An external
dependency waits at least five minutes; quota failures retain bounded backoff. None triggers
stronger-model diagnosis. Pause continues to stop all goal execution.

The advisor receives bounded goal context and recent history. It uses read-only sandboxing,
no approval prompts, Standard service tier and a 180-second timeout by default. It cannot
implement, approve consequential actions or replace the worker. Reservations are persisted
before invocation. A one-hour cooldown and fresh distinct attempts prevent immediate repeat
consultations; duplicate next-action advice is discarded. History records why it ran, the
recommended direction and subsequent working attempts.

## Selecting an advisor

The dashboard accepts ordered `model-id reasoning` preferences. Designate models you consider
stronger for diagnosis. Choices must exist in the installed Codex model catalog and explicitly
support the chosen reasoning level. A preference for the current model requires greater reasoning
effort. Without preferences, the controller follows explicit catalog upgrade suggestions. It
does not infer capability from model names or silently try guessed IDs. If no suitable untried
candidate is known, history records that limitation and the configured worker stays in control.
Catalog presence is not proof of live entitlement; actual CLI failures are recorded without
silently replacing the worker or bypassing provider limits.

Advanced settings can be changed with `python3 -m agent_os settings --json '<JSON object>'`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `diagnostic_escalation` | `false` | Explicit permission for advisor calls |
| `diagnostic_models` | `[]` | Ordered objects containing `model` and `reasoning` |
| `diagnostic_min_attempts` | `3` | Minimum attempts against one blocker |
| `diagnostic_cooldown_seconds` | `3600` | Minimum interval between consultations |
| `diagnostic_timeout_seconds` | `180` | Maximum duration of one consultation |

Advisor usage is included in the instance token counter. New feature preferences live in ignored
`.agent-os/features.json`; original execution settings remain in `.agent-os/config.json` so
retained older runtime versions can still read their configuration.
