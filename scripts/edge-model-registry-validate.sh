#!/usr/bin/env bash
#
# edge-model-registry-validate.sh
# Validate and summarize config/edge-model-registry.json
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY_PATH="${1:-$SCRIPT_DIR/config/edge-model-registry.json}"

if [[ ! -f "$REGISTRY_PATH" ]]; then
    echo "[ERROR] Registry file not found at: $REGISTRY_PATH" >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "[ERROR] jq is required to validate the registry." >&2
    echo "Install jq and re-run this script." >&2
    exit 1
fi

echo "Validating edge model registry: $REGISTRY_PATH"

if ! jq empty "$REGISTRY_PATH" 2>/dev/null; then
    echo "[ERROR] Invalid JSON syntax in registry." >&2
    exit 1
fi

version=$(jq -r '.version // "unknown"' "$REGISTRY_PATH")
models_count=$(jq '.models | length' "$REGISTRY_PATH")

if [[ "$version" == "unknown" ]]; then
    echo "[WARN] Registry does not contain a numeric 'version' field."
fi

echo "Registry version: $version"
echo "Model entries:    $models_count"

errors=0

for idx in $(seq 0 $((models_count - 1))); do
    id=$(jq -r ".models[$idx].id // empty" "$REGISTRY_PATH")
    runtime=$(jq -r ".models[$idx].runtime // empty" "$REGISTRY_PATH")
    backend=$(jq -r ".models[$idx].backend // empty" "$REGISTRY_PATH")
    profiles=$(jq -r ".models[$idx].ai_profiles // empty" "$REGISTRY_PATH")

    if [[ -z "$id" ]]; then
        echo "[ERROR] models[$idx] is missing required field 'id'." >&2
        errors=$((errors + 1))
    fi
    if [[ -z "$runtime" ]]; then
        echo "[ERROR] models[$idx] ('$id') is missing required field 'runtime'." >&2
        errors=$((errors + 1))
    fi
    if [[ -z "$backend" ]]; then
        echo "[ERROR] models[$idx] ('$id') is missing required field 'backend'." >&2
        errors=$((errors + 1))
    fi
    if [[ -z "$profiles" ]]; then
        echo "[ERROR] models[$idx] ('$id') is missing 'ai_profiles' list." >&2
        errors=$((errors + 1))
    fi
done

if [[ $errors -eq 0 ]]; then
    echo "Validation: OK (no structural issues found)."
else
    echo "Validation: FAILED ($errors problem(s) detected)." >&2
fi

exit "$errors"

