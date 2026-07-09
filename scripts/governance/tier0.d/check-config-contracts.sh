#!/usr/bin/env bash
# tier0.d: every config with a registered schema must validate + round-trip (WS1).
# Prevents an invalid config edit from being committed (the running service's
# hot-reload would reject it anyway, but catch it at commit time too).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

mapfile -t PATHS < <(cd "$REPO" && python3 - <<'PY'
try:
    from contracts.config import registry
    for p in registry():
        print(p)
except Exception as exc:
    import sys
    print(f"__ERROR__ {exc}", file=sys.stderr)
    sys.exit(0)
PY
)

if [[ ${#PATHS[@]} -eq 0 ]]; then
    echo "[tier0.d/check-config-contracts] PASS: no registered config schemas"
    exit 0
fi

fail=0
for rel in "${PATHS[@]}"; do
    [[ -z "$rel" ]] && continue
    for action in validate round-trip; do
        if ! out=$(cd "$REPO" && python3 scripts/ai/lib/config_loader.py "$action" "$rel" 2>&1); then
            echo "[tier0.d/check-config-contracts] FAIL ($action): $out" >&2
            fail=1
        fi
    done
done

if [[ $fail -eq 0 ]]; then
    echo "[tier0.d/check-config-contracts] PASS: ${#PATHS[@]} registered config(s) validate + round-trip"
else
    echo "[tier0.d/check-config-contracts] FAIL: fix config or schema above" >&2
    exit 1
fi
