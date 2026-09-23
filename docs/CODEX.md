# Codex model and execution settings

Default: `gpt-6-luna`, `model_reasoning_effort="medium"`, standard service tier. The dashboard
accepts a free-form model ID and reasoning value. Its local model suggestions and automatic
escalation policy are restricted to the current GPT-6 family: `gpt-6-luna`, `gpt-6-sol` and
`gpt-6-astra`. Availability is ultimately determined by the installed CLI and authenticated
account. An unavailable model is reported, never silently replaced.

A normal working command is constructed as an argument array, with the prompt on stdin:

```bash
codex exec --json --color never --model gpt-6-luna \
  -c 'model_reasoning_effort="medium"' \
  -c 'service_tier="default"' \
  --dangerously-bypass-approvals-and-sandbox \
  --cd /path/to/instance \
  --output-schema /private/path/schema.json \
  --output-last-message /private/path/result.json -
```

Fast replaces the service-tier setting with `service_tier="fast"`. This is a service tier, not a
reasoning level or a promise that every model/account combination supports it. Configuration
changes apply to the next working attempt and its review. The current attempt keeps its original
settings. The global Codex config is not rewritten.

Independent verification uses `--sandbox read-only` and `approval_policy="never"`. The working
agent has full access; the verification session inspects evidence. Both use the selected model.

## GPT-6 escalation policy

Normal work starts on **GPT-6 Luna Medium**. Escalation remains an evidence-backed strategic
decision rather than an attempt-count trigger:

1. `gpt-6-luna` with `high` reasoning for a harder same-model consultation.
2. `gpt-6-sol` with `high` reasoning for a materially stronger bounded consultation or scoped turn.
3. `gpt-6-astra` with `high` reasoning only when the stronger GPT-6 path is justified by the
   existing exhaustion, evidence, cost/value and cooldown gates, or when Sol is unavailable.

GPT-5.6 defaults are migrated when an upgraded instance loads its settings. Legacy Terra diagnostic
preferences are not used for automatic escalation. The controller filters its non-secret Codex
catalog view to Luna, Sol and Astra for automatic model selection, while preserving explicit
operator control of the normal Model field.

JSONL events drive live progress. `turn.completed` usage is accumulated for this instance. The
application does not claim to know the account's remaining weekly allowance. An exhausted quota
stops productive model execution, preserves the goal and backs off until a later retry works.

During commissioning, test the exact model and tier with the actual installed CLI. If syntax or
availability has changed, repair the adapter with evidence from `codex exec --help` and official
documentation. Do not change the owner's chosen model just to make the test pass.

Official references consulted for this implementation:

- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): JSONL events, saved
  authentication, output schemas and the final-result file.
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli): execution,
  model, sandbox and configuration flags.
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference): reasoning
  and `service_tier="fast"`, which maps to priority processing in requests.
- [Models](https://developers.openai.com/api/docs/models): GPT-6 Luna, Sol and Astra model IDs and
  supported reasoning levels.

The optional [diagnostic advisor](DIAGNOSTICS.md) is a separate bounded read-only consultation.
It does not replace the selected model for implementation or completion review. The dashboard
also exposes [GitHub follow-ups](OPERATORS.md).
