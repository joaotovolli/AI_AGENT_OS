# Adaptive strategic execution

The configured model owns the goal. At each turn it chooses a useful next action from current
evidence, immutable acceptance criteria and persistent conclusions. Attempt counts never select
a strategy or automatically buy a stronger model. Scripts are tools for implementation and cheap
observation; running a script repeatedly is not evidence of progress.

## Understand before waiting

Map criteria to separate work items: verified work, locally actionable implementation, research,
evidence gaps, external validation and genuine human dependencies. Give independent preparation
its own actionable item. If a previous plan collapsed all criteria into one waiting item, add
specific child items and make the parent actionable with those prerequisites. Preserve its original
criterion and verify the aggregate after its children. No criterion disappears during refinement.

Before waiting, inspect relevant logs, contracts, API semantics, authorized configuration,
authoritative documentation, status metadata, schedules and rate-limit resets. State what causes
the failure and what remains unknown. Consider alternate permitted providers of the required
capability, equivalent routes and local fixtures for preparation. Fixtures never satisfy a criterion
that explicitly requires live evidence. Record the source and conclusion; do not copy private logs.

Perform independent and anticipatory work while another stream waits. Prepare tests, recovery,
integration, data or documentation only where this advances the actual goal. A clean, fully prepared
state is a valid reason to wait; do not manufacture activity.

| Evidence about availability | Next action |
| --- | --- |
| Documented exact time | `schedule` with UTC Unix `not_before` and evidenced `timing_source` |
| Documented bounded window | Choose a useful `not_before` inside it; record `expected_by` |
| Unknown time, safely observable | `watch`, after research, alternatives and preparation assessment |
| Unknown and unobservable | `backoff` with bounded periodic reassessment |
| Missing knowledge | `research` or a discriminating `experiment` |
| Human-only requirement | `needs_input` with the exact human dependency |

Documented schedules are not shortened to the generic external-backoff cap. They cancel obsolete
watchers on that item. Independent actionable items still run first; multiple waiting streams
use their earliest useful reassessment. Human-only requirements include MFA, unavailable authorized
credentials, explicit approvals and decisions outside the goal's authority. Uncertainty or a
repairable local configuration defect is not itself a human dependency.

## Strategic record contract

The structured result includes `strategies`, an array of updates keyed by `work_key`. Use `[]` when
no update is needed, including read-only review and advisory results. Each record includes:

- Situation, stable blocker, typed `constraint`, diagnosis and remaining uncertainty. Escalation
  requires a `technical` constraint; external timing, access and information gaps do not qualify.
- Source-backed `findings`: stable key, source, sanitized finding and evidence reference.
- `approaches`: stable key, method, hypothesis, status, result and evidence. Status is `untried`,
  `failed`, `rejected`, `selected` or `succeeded`.
- `alternatives` and `independent_work`: concise conclusions about substitutes and preparation.
- `preparation`: stable key, action, `planned` or `done`, and completion evidence.
- Chosen `action`, operational `reason`, `next_action`, `chosen_approach` and new `change_evidence`.
- `not_before`, `expected_by`, `timing_source` and `human_dependency`; use zero/empty when inapplicable.
- `escalation`: `request_id`, focused `question`, `exhaustion`, `clarity`, `expected_value` and optional
  execution `scope`. Use empty strings where no escalation is requested.
- `advice_outcomes`: key, `advice_id` (the advisor data ID, or legacy event key), action tried, result and evidence.

Findings, approaches, preparation and advice outcomes merge by stable key, so omitted conclusions
survive future turns. Reopening an abandoned method, even under another key, requires new evidence.
Equivalent method/hypothesis text does not count as diverse experimentation. Timestamp and percentage
changes do not count as new evidence. Semantic novelty still requires model judgment: this is an
auditable operational contract, not proof that differently worded claims are genuinely different.

Records are additive SQLite data, visible in goal details and included in recovery checkpoints.
Store concise operational conclusions, never hidden reasoning traces. Full evidence belongs in
sanitized repository files referenced by the record. Existing goals receive this policy on their
next normal turn; updating does not discard their evidence, change preferences or force an early
paid turn while a known deadline is pending.

## Reflection and escalation

Missing information calls for research; known timing calls for scheduling. Complex conceptual
conflicts can justify `consult_reasoning`: a read-only consultation using the same model at the
next supported higher effort. A precisely narrowed technical problem can justify `consult_model`:
a read-only consultation with an operator-preferred or catalog-suggested stronger model.

Both require an explicit assessment of exhausted autonomous options, problem clarity and expected
value versus cost/latency. At least three base attempts and three evidenced distinct methods are
safety floors, never triggers. The affected item must be locally actionable with prerequisites met.
The dossier includes full goal/criteria, relevant work, verified evidence, research, rejected
hypotheses, diagnosis, uncertainty, prior advice and recommendation trials. The advisor can recommend
research, scheduling, a simpler approach or no additional escalation. The base model executes next.

A later consultation needs a new request, elapsed cooldown, changed evidence and outcomes from the
latest useful advice. The same advisor may revisit an updated dossier. Persisted reservations prevent
replaying a request after restart, including failed calls. Counts and rephrased justifications cannot
replace new evidence.

Optional **Scoped expert execution** also requires **Diagnostic advisor**, useful prior advice,
evidenced recommendation trials and an explicit narrow scope/value assessment. It grants one bounded
working turn, never a persistent change of model. It cannot complete the overall goal or replace its
work plan. The base model resumes to inspect the changes, follow-ups and evidence. Existing tests,
independent review, Git checkpoint and activation still gate overall completion. Scope is an
instructional boundary under the existing full-access host model, not a filesystem sandbox.

## Limits

These controls improve continuity and action selection; they cannot guarantee correct diagnosis,
exhaustive research, access to unavailable services or higher model capability. Evidence references
and model-authored assessments still require verification. Pausing/cancelling, authentication,
provider restrictions, approvals and immutable criteria always retain precedence.
