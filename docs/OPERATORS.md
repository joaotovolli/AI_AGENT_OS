# GitHub operator follow-ups

Enable **GitHub follow-ups** in Model and execution, then save. The feature is off by default.
Only comments created after enabling it on this instance's existing `Agent OS status:` issue
are eligible. Ordinary issues, pull requests and other repositories are not input channels.

Leave a normal comment with context, a clarification or the result of a requested local action.
The repository owner is the default operator. For organization-owned repositories, configure
individual GitHub logins. Every accepted author must be a human user on the configured allowlist
and have current repository write, maintain or admin permission. The authenticated GitHub CLI
must be able to inspect that permission and read/write status-issue comments; failures are shown
in the dashboard. Bots, third parties and edited duplicates do not become new messages.

The worker polls at the existing GitHub progress interval (60 seconds by default), including
while paused and during execution heartbeats. A receipt confirms queueing. The message enters
the next appropriate turn of the current bootstrap or user goal. With no active goal it waits
for the next user goal, without creating a goal or consuming an idle maintenance turn. A later
reply describes the outcome. Offline time and GitHub throttling may delay receipts.

Accepted comments are persisted by repository and comment ID. Restart recovers pending delivery;
an interrupted turn can receive its unfinished context again. Receipt publication reconciles
ambiguous network failures against the authenticated writer's existing receipt markers. This
deduplicates messages and replies; it does not promise exactly-once side effects inside a
crashed Codex turn. Applications must retain their own transaction and approval protections.

Disabling the feature stops new intake and GitHub replies until enabled again. Previously
accepted context still reaches its goal. A comment may wake a blocked goal for reconsideration;
it cannot resume a paused supervisor, change acceptance commands, change model settings, create
an authenticated dashboard session or approve an action requiring a stronger application gate.
Quoted material remains untrusted. The controller never evaluates comment text as shell code.

Replies and compact history are sanitized public text. Raw messages and model transcripts stay
in the private database/run directory; checkpoints contain only message IDs, delivery status
and target goal IDs. Do not paste credentials, dashboard tokens or private logs into GitHub.
When a credential is missing, use the local provider sign-in or secure application setup described
in the instance's access instructions, then request **Retry goal** or post a non-secret follow-up.

If all local state is lost, `restore` imports handled receipts and re-fetches pending comments
subject to current authorization. A comment deleted before recovery cannot be reconstructed;
post a new non-secret clarification if it is still needed. See [recovery](RECOVERY.md).
