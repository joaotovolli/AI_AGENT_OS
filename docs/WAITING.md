# Productive work and external waiting

A goal can have independent workstreams. The controller stores the plan in additive SQLite
state, includes it in every new attempt and exports it in the sanitized recovery checkpoint.
The plan tracks execution; the original acceptance criteria remain authoritative.

## Work plan

The working result may include `work_plan`, an array of updates keyed by a stable `key`.
An empty array means no updates, not deletion. Previously verified work remains recorded.
Each item contains `title`, `criterion` (the original criterion it supports), `status`,
`blocker_key`, `depends_on` (other work keys) and `evidence`.

| Status | Meaning |
| --- | --- |
| `actionable` | Work can proceed once its dependencies are verified |
| `waiting` | An external condition prevents this item from progressing |
| `needs_input` | Operator input or an application approval is required |
| `verified` | Evidence is recorded; final independent review still checks it |

The next prompt prioritizes actionable keys. A waiting item does not delay unrelated actionable
work. Dependencies must exist and cannot contain cycles. Omitted items survive subsequent
attempts and restarts. All recorded items must be verified before completion can enter the
existing deterministic checks, independent review, confirmed checkpoint and activation gates.
A plan cannot remove or weaken an original acceptance requirement.

## Stable external blockers

Report stable `blocker_key` and `approach_key` values in `diagnostic`. Report narrow observed
facts in `observations`, as `key`/`value` strings. For example, `service_state=starting` can stay
constant over many polls. Timestamps, percentages, reworded summaries and repeated commands
are not evidence of progress. The controller hashes normalized observations; it does not use
the model's progress percentage or `progress_made` claim to reset the retry count. This relies
on accurate stable keys and factual observations, not semantic understanding of arbitrary text.

Without a watcher, the first equivalent external results wait five minutes. At three equivalent
results, the default delay becomes 15 minutes, then doubles to a maximum of six hours. A new
approach or changed observation resets the sequence and permits the next attempt promptly.
`diagnostic.next_check_at` can name a useful future UTC Unix timestamp; use `0` when unknown.
The configured maximum waiting interval caps that request.

| Setting | Default |
| --- | --- |
| `external_repeat_limit` | 3 equivalent results |
| `external_wait_min_seconds` | 900 |
| `external_wait_max_seconds` | 21600 |

Use the local `settings --json` CLI to change these validated values. They are stored separately
in `.agent-os/progress-settings.json` so retained 0.2 runtimes can still read their configuration.
Authentication, configuration and operator requirements retain their existing gates. Waiting
is not an error and does not qualify for the optional technical diagnostic advisor.

## Deterministic watchers

The working result can register a `watchers` array for externally waiting work items. Watchers
run in a bounded background pool, including while Codex works on independent tasks. They never
invoke Codex or execute shell commands. Application-specific authenticated observation belongs
in the application's authorized local service, which can write a sanitized status file for a
JSON watcher. Watchers do not hold passwords, tokens or authentication headers.

Example work result fields for a generic service:

```json
{
  "work_plan": [
    {
      "key": "service-health",
      "title": "Verify deployed service health",
      "criterion": "The deployed service is healthy",
      "status": "waiting",
      "blocker_key": "service-starting",
      "depends_on": [],
      "evidence": ""
    }
  ],
  "watchers": [
    {
      "key": "service-ready",
      "work_key": "service-health",
      "kind": "json_value",
      "path": "workspace/service/status.json",
      "url": "",
      "field": "healthy",
      "expected": "true",
      "predicate": "equals",
      "interval_seconds": 60,
      "lifetime_seconds": 86400
    }
  ]
}
```

| Kind | Observation |
| --- | --- |
| `file_exists` | A regular file exists; expected is `true` or `false`, predicate `equals` |
| `file_changed` | SHA-256 of a file up to 1 MiB; predicate `changed` |
| `json_value` | A scalar at a dotted JSON object path; expected is JSON text, such as `true`, `42` or `"ready"` |
| `http_status` | HTTP response status; expected is a numeric string, such as `200` |

All fields in the example are required; unused string fields are empty. File paths are relative
to `workspace/`, cannot traverse symlinks and cannot escape it. HTTP checks accept credential-free
HTTP(S) URLs without queries or fragments, use a three-second network timeout and do not follow
redirects or retry authorization/rate-limit failures as successful conditions. Response bodies
are not collected. Never use URLs whose GET requests have side effects.

Polling starts at the requested interval, at least 30 seconds, and doubles every three unchanged
polls up to one hour. The maximum lifetime is seven days, with at most ten active watchers per
goal and four concurrent checks. For `changed`, the first successful observation establishes a
baseline. Use `file_exists` to wait for a previously absent file to appear.

The controller persists observations, deadlines, backoff and errors across restart. Re-registering
an identical watcher does not reset its baseline or lifetime. Use a new key or changed specification
to deliberately register a fresh watcher. No historical event log or Git commit is generated for
an unchanged poll; the current state is visible on the dashboard and regular status publication.

When all externally waiting items have active watchers and no independent work remains, normal
model turns are deferred until an event, expiry or the maximum waiting interval. A successful
predicate emits a durable `watcher.changed` event, makes only its linked item actionable and
requeues the goal. It does not mark the item verified, grant approval, resume a paused instance
or clear a goal-wide operator/authentication block. An event arriving during a model turn is
preserved; a stale result cannot overwrite it or complete the goal.

The dashboard displays guidance, work items, partial blockage, the reason for waiting, next model
check, watcher status, last check and observation. It provides watcher cancellation and explicit
Retry controls. Cancelling or completing a goal deactivates its guidance and active watchers;
verified work and audit history remain available. Expiry asks the worker to reassess the dependency.
Pause prevents model turns; background checks can continue. Resume preserves waiting deadlines.
Use **Retry goal**, **Run now** or new operator context when an immediate reassessment is intended.

Before external waiting, follow [strategic execution](STRATEGY.md): investigate authoritative timing,
alternatives and independent preparation. A documented schedule takes precedence over watchers;
watchers are a fallback for unknown, machine-observable transitions.
