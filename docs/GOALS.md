# Define and monitor goals

In the dashboard, enter a title, the desired outcome and the acceptance criteria. You can
also add verification commands, one per line. These are real Bash commands executed from
the repository directory with the instance's permissions.

Example:

| Field | Content |
| --- | --- |
| Title | Build a local document organiser |
| Outcome | Build an interface to classify documents in a test folder, with a preview before moving files. |
| Acceptance criteria | Files are classified correctly; duplicate names never overwrite files; the interface shows the result; access instructions are in GitHub. |
| Optional command | `python3 -m unittest discover -s workspace/tests -v` |

Without goal-specific commands, the controller's regression suite remains mandatory and a
separate Codex session must verify the project's criteria and evidence. Vague criteria weaken
this verification. Provide acceptance tests for outcomes that can be checked in code.

Goals submitted during bootstrap remain queued. Afterwards, the first pending user goal
retains priority until it completes or is cancelled, including while it waits for quota.
New goals do not interrupt an attempt already in progress. **Pause** interrupts execution and
preserves the work; **Resume** continues. **Run now** brings forward the next attempt or
maintenance cycle without overriding an active pause.

There is no maximum attempt count. Each attempt has a timeout, records what was learned and
can change the next strategy. Quota and network failures appear in the dashboard and retry
with backoff. Missing authentication, model configuration or an operator decision can enter
**Needs input**. Resolve the dependency locally and select **Retry goal**; pause remains respected.
Later goals do not overtake a blocked goal. The [GitHub follow-up channel](OPERATORS.md), when
enabled, can supply context without bypassing application approvals.

Expand **Diagnostic history** to inspect phases, attempts, blockers and next actions. Earlier
records persist in GitHub after completion or cancellation. The optional [diagnostic advisor](DIAGNOSTICS.md)
can help with repeated technical blockers while leaving your selected worker model unchanged.

A claim of 100% from the working agent is capped at 99% until final verification. Only the
controller marks completion, after checks, independent review and GitHub publication. Not every
goal is achievable, and the model's assessment can still be wrong.

Goals and summaries are published to the repository. Keep secrets out of descriptions. For a
confidential file, reference its local path and describe only what is necessary. Operating
instructions and evidence belong in `docs/`; project deliverables belong in `workspace/`.
All generated progress, evidence, interface text and operating instructions must be in English.

For a distinct product, use the [project organization and access contract](PROJECTS.md). Its
interface opens from the Projects panel, with its own service and authentication.
