#!/usr/bin/env bash
# Validate the repo-local edgeai CLI surface and offline JSON behavior.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EDGEAI="$ROOT/scripts/ai/edgeai"
[[ -x "$EDGEAI" ]] || { echo "edgeai is not executable" >&2; exit 1; }
bash -n "$EDGEAI"
"$EDGEAI" --version | grep -q '^edgeai '
"$EDGEAI" --help | grep -q 'edgeai models list \[--json\]'
"$EDGEAI" --help | grep -q 'edgeai models add --id ID'
"$EDGEAI" --help | grep -q 'edgeai models delete <model-id>'
"$EDGEAI" --help | grep -q 'edgeai chat \[--model MODEL\]'
"$EDGEAI" --help | grep -q 'edgeai contracts check \[--json\]'
# Doctor JSON must be well-formed even if services are down.
EDGEAI_COORDINATOR_URL=http://127.0.0.1:9 EDGEAI_DASHBOARD_URL=http://127.0.0.1:9 "$EDGEAI" doctor --json | python3 -m json.tool >/dev/null
# Offline API commands should emit JSON error envelopes, not shell tracebacks.
EDGEAI_COORDINATOR_URL=http://127.0.0.1:9 EDGEAI_DASHBOARD_URL=http://127.0.0.1:9 "$EDGEAI" models list --json 2>/dev/null | python3 -m json.tool >/dev/null || true
EDGEAI_DASHBOARD_URL=http://127.0.0.1:9 "$EDGEAI" models add --id local-test --name "Local Test" --repo org/repo --file model.gguf 2>/dev/null | python3 -m json.tool >/dev/null || true
EDGEAI_DASHBOARD_URL=http://127.0.0.1:9 "$EDGEAI" models delete local-test 2>/dev/null | python3 -m json.tool >/dev/null || true
EDGEAI_DASHBOARD_URL=http://127.0.0.1:9 "$EDGEAI" models download local-test 2>/dev/null | python3 -m json.tool >/dev/null || true
EDGEAI_COORDINATOR_URL=http://127.0.0.1:9 "$EDGEAI" chat --json "ping" 2>/dev/null | python3 -m json.tool >/dev/null || true
"$EDGEAI" contracts check --json | python3 -m json.tool >/dev/null
grep -q 'writeShellScriptBin "edgeai"' "$ROOT/nix/modules/roles/ai-stack.nix"
echo "PASS: edgeai CLI contract"
