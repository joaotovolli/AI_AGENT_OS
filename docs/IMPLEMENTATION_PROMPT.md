# WSL2 implementation prompt

This prompt installs the **existing AI_AGENT_OS repository**. It does not create
`AI_AGENT_OS_1` or another GitHub repository. For a separate numbered project, use the
[new-instance prompt](NEW_INSTANCE_PROMPT.md) or follow [REUSE.md](REUSE.md) first.

Copy the text below into a Codex session running on the target WSL2 host.

---

Install, validate and operate the existing repository
https://github.com/joaotovolli/AI_AGENT_OS.git on my WSL2 Linux machine. Complete the actual
installation and verification using the implementation already in the repository.

Use English for the interface, documentation, prompts, generated progress, evidence,
GitHub updates and operating instructions, regardless of the language used in this conversation.

I authorise the necessary WSL2 changes, dependency installation and configuration, services,
passwordless sudo for my Linux user, and WSL startup at Windows sign-in. Preserve unrelated
projects and settings. Keep credentials private. This authorisation does not override real
provider, account or tool restrictions.

1. Locate the existing checkout or clone into ~/projects/AI_AGENT_OS. Verify the origin.
   Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/INSTALL_WSL2.md, docs/CODEX.md
   and docs/VALIDATION.md. Continue from the existing implementation. This task uses the
   base repository itself; creating another GitHub repository is a separate operation.

2. Inspect WSL, systemd, Python, Git, GitHub CLI, Node/npm and Codex CLI. Install or adjust
   what is needed. Reuse valid GitHub and Codex authentication. Keep auth.json, tokens and
   .env files out of logs, chat and GitHub. If sign-in genuinely requires my interaction,
   identify the exact missing step. Prepare all possible work before a required WSL restart
   and document how to resume afterwards.

3. Use codex exec --help and an actual run to verify the adapter with gpt-5.6-luna and
   medium reasoning. This is the required default. Check JSONL output, the result schema
   and full-access execution. Verify Fast behaviour against current CLI support and the
   account's available tiers; record an actual limitation if unsupported. Preserve my
   selected model and existing global configuration. Use the saved Codex sign-in without
   adding a dependency on an OpenAI API key.

4. Run the regression suite and fix defects. Execute bash scripts/install-wsl.sh 8765,
   selecting another free port only if necessary. Install Windows shortcuts and keep-alive
   using scripts/install-windows-startup.ps1. Verify that both services remain active
   without an open terminal and the shortcut opens the Windows browser successfully.

5. Follow the automatic bootstrap attempts and fix installation or integration problems.
   Validate the actual browser workflow at desktop and narrow viewport sizes: authentication,
   goal submission, queue state, model/reasoning/Fast settings, progress, pause, resume and
   cancellation. Preserve the tests and acceptance criteria when repairing failures.

6. After bootstrap, create a small, verifiable sample goal, such as producing an example
   file in workspace/smoke-test with a test that checks its content. Observe actual execution,
   independent review, commit, push and dashboard completion. Verify interrupted-goal recovery
   and failure handling with the regression suite. Trigger an early maintenance cycle using
   Run now and leave the final interval at 3,600 seconds. Finish with Luna Medium and Fast off
   unless I explicitly request different settings.

7. Publish code, fixes and instructions to this repository. Every attempt needs a checkpoint
   on the instance working branch; tested changes advance the stable branch. Preserve remote
   history without force pushes. Record external host changes through reproducible scripts
   and sanitised notes in infra/. Update docs/ACCESS.md, docs/VALIDATION.md and goal evidence
   with actual results from this machine. Verify CI on GitHub. Keep raw logs and the local
   database out of Git.

8. Finish with evidence of readiness: dashboard accessible from Windows, persistent services,
   authenticated Codex using the requested model, a verified sample goal, confirmed GitHub sync
   and automatic maintenance. Leave the agent running for my first project goal. Report the
   URL, shortcut, GitHub links and any real remaining limitation. State uncertainty accurately.
   If quota is exhausted, preserve and publish the available progress, report the blockage and
   retain scheduled retries. Do not bypass limits.

Keep the project reusable as AI_AGENT_OS_1, AI_AGENT_OS_2 and other independent repositories.
Preserve scripts/new_instance.py and per-instance ports, state and services.

Leave GitHub follow-ups and diagnostic escalation disabled unless I explicitly enable them.
Verify their controls and persisted settings using fixtures. Read docs/PROJECTS.md for generated
outputs and docs/FRAMEWORK_UPDATES.md for base provenance and future updates. Do not apply
base updates to any other existing instance as part of this installation.
