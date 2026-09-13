# Prompt to create and install AI_AGENT_OS_1

This prompt explicitly creates a **new private GitHub repository** and installs it on WSL2.
Use a different repository name, folder and free port for each further instance. The creation
script does not select the next number automatically. See [REUSE.md](REUSE.md) for the process.

Copy the text below into Codex on the target WSL2 machine.

---

Use https://github.com/joaotovolli/AI_AGENT_OS.git as the reusable source for a new instance.
Create the private GitHub repository joaotovolli/AI_AGENT_OS_1 and install it in
~/projects/AI_AGENT_OS_1, using port 8766 if available. Keep the base checkout available for
creating future projects. All project text and operating instructions must be in English.

I authorise creating this repository and the necessary WSL2 dependencies, full-access Codex
configuration, passwordless sudo, persistent services and Windows startup shortcuts. Preserve
unrelated work and keep credentials private. Use existing valid GitHub and Codex sign-ins.

1. Locate or clone the base into ~/projects/AI_AGENT_OS. Read AGENTS.md, docs/REUSE.md and
   docs/INSTALL_WSL2.md. Use a clean committed base revision. If the requested instance
   repository or local folder already exists, inspect it and continue only if it is the
   intended instance; preserve its work and never overwrite a different project.

2. For a new instance, run from the base checkout:
   python3 scripts/new_instance.py joaotovolli/AI_AGENT_OS_1 ~/projects/AI_AGENT_OS_1
   Confirm that the new checkout's origin is joaotovolli/AI_AGENT_OS_1. This step creates the
   new GitHub repository and pushes its initial commit. Running the WSL installer alone does
   not create a repository.

3. Change into ~/projects/AI_AGENT_OS_1. Apply the installation and validation steps in
   docs/IMPLEMENTATION_PROMPT.md to this selected instance, substituting AI_AGENT_OS_1,
   its origin and port 8766 for the base name and port. Run bash scripts/install-wsl.sh 8766.
   Install Windows startup and dashboard shortcuts with the instance name ai_agent_os_1.

4. Keep gpt-5.6-luna with medium reasoning as the default and Fast off. Verify actual Codex
   authentication, model support, services and browser access. Follow bootstrap until its
   evidence passes, then complete a small sample goal with independent review and GitHub sync.
   Validate pause/resume, recovery and an early maintenance cycle. Leave hourly maintenance
   enabled and the agent running for my first project goal.

5. Publish changes and English operating instructions to AI_AGENT_OS_1. Keep credentials,
   raw logs and local state private. Update ACCESS.md, VALIDATION.md and goal evidence in
   that instance's docs directory. Verify CI. Report the instance URL, desktop shortcut,
   GitHub repository and status link. State any real remaining blockage precisely.

The instance is an independent copy. Do not automatically publish its project work back to
AI_AGENT_OS or create additional instances without a separate instruction.

Leave GitHub follow-ups and diagnostic escalation disabled unless I explicitly enable them.
Verify their controls and persisted settings using fixtures. Read docs/PROJECTS.md for generated
outputs and docs/FRAMEWORK_UPDATES.md for base provenance and future updates. Do not apply
base updates to any other existing instance as part of this installation.
