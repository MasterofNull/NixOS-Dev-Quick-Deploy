#!/usr/bin/env bash
# CI-parity gitleaks: whole tree, no git history, run FROM the tree root with the repo config
# (allowlist paths in .gitleaks.toml are root-relative; other cwds give false positives).
# Mirrors .github/workflows/security.yml secrets-scan minus the SARIF report.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v gitleaks >/dev/null 2>&1 || { echo "FAIL: gitleaks not on PATH (aq-tool gitleaks)" >&2; exit 1; }
exec gitleaks detect --no-banner --redact --config .gitleaks.toml --source . --no-git --exit-code 1
