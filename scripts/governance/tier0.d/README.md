# tier0.d/ — Tier 0 Extension Checks

Drop executable `.sh` scripts here to add new gates to the Tier 0 validation
pipeline **without editing `tier0-validation-gate.sh`**.

## Contract

- Receives `$1 = MODE` (`--pre-commit` or `--pre-deploy`)
- Exit 0 → pass (logged as `[tier0] PASS: tier0.d/<name>`)
- Exit 1 → fail (logged as `[tier0] FAIL: tier0.d/<name>`, blocks commit)
- Prefix stdout/stderr with `[tier0.d/<name>]` for traceability
- Use `REPO_ROOT="$(git rev-parse --show-toplevel)"` to find repo paths
- Must be idempotent and fast (< 5s)

## Example

```bash
#!/usr/bin/env bash
# tier0.d/check-my-thing.sh — describe what this checks
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"

if some_condition; then
    exit 0
fi
echo "[tier0.d/check-my-thing] FAIL: describe what went wrong" >&2
exit 1
```

## Current extension checks

(none yet — add .sh files here)
