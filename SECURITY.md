# Security Policy

## Supported version

AI Agent OS is currently in alpha development. Security fixes are applied to the latest version on
the default branch; older revisions are not maintained as separate supported releases.

## Reporting a vulnerability

Please do not publish credentials, authentication logs, access tokens or exploitable security details
in a public GitHub issue.

If GitHub private vulnerability reporting is available for this repository, use it. Otherwise,
contact the repository owner through GitHub before disclosing sensitive technical details publicly.

When reporting a vulnerability, include the affected component, reproduction conditions, expected
impact and any relevant version or commit information. Do not include real secrets in reproduction
material.

## Scope

The project intentionally gives its local agent broad access to its WSL2 environment. That design is
not a security sandbox. Reports about unintended credential disclosure, authentication bypass,
unexpected remote exposure, unsafe publication to GitHub or privilege escalation beyond the stated
local execution model are considered security-relevant.
