# Contributing

Thanks for considering a contribution to AI Agent OS.

## Development

Use Python 3.11 or newer. The controller intentionally keeps its Python runtime dependency-free.
Before opening a pull request, run the same core checks used by CI:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q agent_os scripts tests
bash -n scripts/install-wsl.sh
node --check agent_os/static/app.js
python3 scripts/check_repository.py
```

Changes to dashboard behavior should also remain compatible with the Chromium workflow in
`.github/workflows/ci.yml`.

## Pull requests

Keep changes focused, explain the behavior being changed, and include tests or validation evidence
when appropriate. Do not weaken verification criteria simply to make a check pass.

Never commit credentials, authentication material, private runtime logs, local databases or other
sensitive data. Security-sensitive findings should follow [SECURITY.md](SECURITY.md) rather than a
public issue.
