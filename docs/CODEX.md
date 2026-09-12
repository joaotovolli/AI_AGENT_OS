# Codex model and execution settings

Default: `gpt-5.6-luna`, `model_reasoning_effort="medium"`, standard service tier. The dashboard
accepts a free-form model ID and reasoning value, with suggestions from the local non-secret
Codex model cache when available. Availability is ultimately determined by the installed CLI
and authenticated account. An unavailable model is reported, never silently replaced.

A normal working command is constructed as an argument array, with the prompt on stdin:

```bash
codex exec --json --color never --model gpt-5.6-luna \
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

JSONL events drive live progress. `turn.completed` usage is accumulated for this instance. The
application does not claim to know the account's remaining weekly allowance. A exhausted quota
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
- [Models](https://learn.chatgpt.com/docs/models): `gpt-5.6-luna` and selectable Codex model IDs.
