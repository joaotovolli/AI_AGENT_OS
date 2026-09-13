# Generated projects

Agent OS manages goals, execution settings, progress and recovery. A distinct product produced
for a goal belongs under `workspace/<project-name>/`, with its own README, code, assets and tests.
Its web interface should normally run as a separate service on a distinct local port, or on a
documented HTTPS URL. Genuine improvements to Agent OS may change the core controller/dashboard.

Do not import project modules into `agent_os/server.py`, mount a project inside the console or
copy workspace code into `.agent-os/runtime`. Core runtime releases contain only `agent_os/`.
Projects can share the instance repository without sharing the control interface or release.

Register an existing project directory to make its access path visible in the console and
GitHub status. For example, after creating a report viewer and starting its own service:

```bash
python3 -m agent_os project register \
  --path workspace/report-viewer --name 'Report viewer' \
  --description 'Explore the generated reports.' \
  --url http://localhost:8800 --status ready
python3 -m agent_os project list
```

Optionally pass `--goal <existing-goal-id>`. Omit `--url` for a CLI tool or file-based output.
Registration writes a small `workspace/<project-name>/project.json` containing `name`,
`description`, `url`, `goal_id` and `status` (`building`, `ready` or `stopped`). The dashboard
discovers valid manifests without importing code or probing arbitrary services. Invalid
manifests are ignored; registration reports validation errors. Symlink escapes, embedded
credentials, URL queries/fragments and the Agent OS control port are rejected. Remote links
require HTTPS. A registered link/status is a handoff description, not a live health assertion.

Each project README and the goal evidence should document:

- Its purpose, start/stop commands, dependencies and acceptance tests.
- The working access URL or output path, plus a return link to the plain Agent OS dashboard URL.
- Its independent authentication and any required operator approvals.
- Reproducible service/host setup under `infra/` when necessary, with a distinct service name.

Never reuse the Agent OS dashboard token in a project URL or product service. A public repository
must contain only publishable project metadata and summaries. Localhost links point to the
operator's machine and become reachable when that instance and project service are running.
