# Create AI_AGENT_OS_1, AI_AGENT_OS_2 and further instances

`AI_AGENT_OS` can serve as the reusable base. Each project instance has its own GitHub
repository, Linux folder, dashboard port, goal database and services.

## Repository creation and installation are separate steps

| Command | What it does |
| --- | --- |
| `git clone ...` | Downloads an existing repository. It does not create a GitHub repository or install services. |
| `python3 scripts/new_instance.py OWNER/NAME DESTINATION` | Copies committed source into a fresh local Git repository, creates a new private GitHub repository with that name, sets its `origin`, and pushes the initial commit. |
| `bash scripts/install-wsl.sh PORT` | Installs the runtime for the selected project folder, creates its working branch and starts bootstrap. It does not create another GitHub repository. |

Renaming a local folder does not change `origin`. Use the instance creation script when the
new project needs its own GitHub repository. Names are explicit: the script does not allocate
the next number automatically or create additional instances later.

## Create and install a separate instance

Start from a clean base checkout, with valid `gh` authentication, Git author configuration
and permission to create private repositories. If the base is already cloned, use that
checkout instead of cloning it again. It does not need to be running as a service.

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/joaotovolli/AI_AGENT_OS.git
cd AI_AGENT_OS
python3 scripts/new_instance.py joaotovolli/AI_AGENT_OS_1 ~/projects/AI_AGENT_OS_1
cd ~/projects/AI_AGENT_OS_1
bash scripts/install-wsl.sh 8766
```

This creates `joaotovolli/AI_AGENT_OS_1` on GitHub and `~/projects/AI_AGENT_OS_1` locally.
Its dashboard uses `http://localhost:8766` after installation. Its working branch is
`agent/AI_AGENT_OS_1`; tested changes also advance `main` in **AI_AGENT_OS_1**.
Project changes are not automatically sent back to the base repository.

For Windows startup and a dashboard shortcut, run from the new instance folder:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w scripts/install-windows-startup.ps1)" -Distro "$WSL_DISTRO_NAME" -RepoPath "$PWD" -Instance "ai_agent_os_1"
```

Repeat from the base checkout with `AI_AGENT_OS_2`, a new destination and another free port.
The examples reserve 8765 for the base, 8766 for instance 1 and 8767 for instance 2. These
numbers are conventions; every running instance needs a free port.

## What a new instance inherits

The script copies files committed at the source checkout's `HEAD`, including the controller,
dashboard, tests and documentation. Uncommitted changes are not copied. It removes the old goal
checkpoint and evidence, resets the access/status pages and starts a new Git history. Ignored
credentials, databases, raw logs and local runtime configuration are not copied.

Use a clean base checkout for a generic instance. Creating one from a project repository also
copies that project's committed files. Both the destination folder and the new repository name
must be unused. Every fresh instance performs its own bootstrap before working on user goals.

## Updates and shared host access

Instances are independent copies, not linked forks with automatic updates. Base improvements
do not automatically update existing instances, and instance improvements do not automatically
update the base. Integrate selected changes deliberately and rerun validation.

Instances on the same WSL2 machine share the host and the Codex account allowance. Separate
ports and databases prevent operational conflicts; they do not create security sandboxes.
Coordinate host-wide package, service and configuration changes across goals.
