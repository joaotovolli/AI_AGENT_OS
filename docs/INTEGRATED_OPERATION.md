# Integrated operation

Choose the normal working Model, Reasoning and Fast preference. Agent OS manages research, work
planning, documented waiting, watchers, advisory consultation and bounded expert assistance.
The configured model remains the goal owner. Availability does not mean frequent escalation.

Before advice, the base model investigates the cause, researches authoritative information, tries
different methods, considers substitutes, advances useful independent work and consolidates a focused
dossier. It then explicitly assesses exhaustion, clarity and positive expected value versus cost and
latency. Counts are safety floors, never automatic triggers. Missing facts call for research; known
timing calls for scheduling. Higher reasoning on the same model is distinct from a stronger model.
The installed non-secret catalog selects supported resources; model names are not capability ranks.
If no suitable resource is known, the base model continues without a generic execution failure.

Advice is read-only and bounded. Recommendations return to the base model. Another consultation needs
new evidence, measured recommendation outcomes, an explicit new request and elapsed cooldown.
Persisted reservations prevent crash replay. Direct expert execution also requires useful prior advice,
trials, an explicit narrow scope and a positive value assessment. It lasts one bounded turn. The base
model resumes afterward and checks the result; the expert cannot complete the overall goal.

Operator questions are for actual human-only dependencies such as unavailable authorized credentials,
MFA, approvals or unspecified decisions beyond the goal's authority. Uncertainty or a repairable
implementation defect is not a reason to send work back to the operator. Repository-owner comments on
the instance status issue are accepted automatically after human identity and live write permission
checks. Additional operators remain an advanced CLI setting. Comments never become shell commands,
change settings, weaken acceptance or grant stronger application approvals.

## Upgrade behavior

Versions before 0.5 used `diagnostic_escalation`, `strategic_delegation` and `github_followups` as
opt-ins. These keys remain accepted for file/CLI compatibility, but false values are ignored by the
new policy. Loading old files exposes the integrated defaults; saving rewrites their compatibility
values. Files remain split so retained old runtime versions can read their known settings.

No goal is recreated. Work plans, findings, guidance, evidence, histories and reservations remain.
Migration does not wake a scheduled goal or resume a paused instance. The next normal turn after
activation/resume uses the integrated policy. Human-blocked goals still need their dependency resolved.
Existing owner-channel cursors are retained. If none exists, initialization records an intake start
before the first poll, avoiding both accidental historical backlog and loss of a new first comment.

## Active goals and History

The Goals panel displays running, blocked, queued and waiting work. Completed and cancelled goals
appear only through the compact History entry. Opening it loads 20 concise rows; Load more fetches
another page. Expanding one row loads its original criteria, saved evidence and diagnostic history.
The timestamp is the persisted terminal update time. Reading pages does not mutate goals or state.

The dashboard does not fetch detailed plans/strategies for every historical goal on each refresh.
All goals remain in SQLite, Git checkpoints and recovery. Archiving is presentation, not deletion.

Tests verify policy migration, conservative non-escalation, advisory/scoped gates, return to base,
automatic authorized owner intake, pause/deadline continuity, authenticated history pagination and
browser behavior with a large terminal history. They validate controller behavior with simulated
model results, not the quality of live model judgment.
