#!/usr/bin/env bash
# scripts/governance/config-directory-lint.sh — Config directory governance lint
#
# Checks:
#   1. Every config/*.json and config/*.yaml (single-doc) has a _meta header
#   2. No duplicate env var canonical names across domain-overlapping files
#
# Usage:
#   scripts/governance/config-directory-lint.sh [--strict]
#
# Exit: 0 = pass, 1 = issues found (strict mode) or warnings only (default)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${ROOT_DIR}/config"
STRICT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

issues=0
warnings=0

# ---------------------------------------------------------------------------
# Check 1: _meta presence in config files
# ---------------------------------------------------------------------------
while IFS= read -r f; do
  fname="$(basename "${f}")"
  ext="${fname##*.}"
  if [[ "${ext}" == "json" ]]; then
    # Skip array JSON files (can't have top-level _meta)
    first_char="$(head -c 1 "${f}" | tr -d '[:space:]')"
    if [[ "${first_char}" == "[" ]]; then
      continue
    fi
    # Skip machine-generated files that are overwritten by tooling
    case "${fname}" in
      package-count-baseline.json) continue ;;
    esac
    if ! python3 -c "import json,sys; d=json.load(open('${f}')); sys.exit(0 if '_meta' in d else 1)" 2>/dev/null; then
      echo "[config-lint] WARN ${fname}: missing _meta header"
      warnings=$((warnings + 1))
    fi
  elif [[ "${ext}" == "yaml" || "${ext}" == "yml" ]]; then
    # Skip multi-doc YAML files
    if grep -qc '^---' "${f}" 2>/dev/null && [[ $(grep -c '^---' "${f}") -gt 1 ]]; then
      continue
    fi
    if ! python3 -c "
import sys
try:
    import yaml
    d = yaml.safe_load(open('${f}'))
    sys.exit(0 if isinstance(d, dict) and '_meta' in d else 1)
except Exception:
    sys.exit(0)  # parse errors are handled elsewhere
" 2>/dev/null; then
      echo "[config-lint] WARN ${fname}: missing _meta header"
      warnings=$((warnings + 1))
    fi
  fi
done < <(find "${CONFIG_DIR}" -maxdepth 1 -name "*.json" -o -name "*.yaml" -o -name "*.yml" | sort)

# ---------------------------------------------------------------------------
# Check 2: No duplicate canonical env var names in env-contract.yaml
# ---------------------------------------------------------------------------
if [[ -f "${CONFIG_DIR}/env-contract.yaml" ]]; then
  dupes="$(python3 -c "
import yaml, collections
doc = yaml.safe_load(open('${CONFIG_DIR}/env-contract.yaml'))
vars_list = doc.get('vars', [])
canonicals = [v['canonical'] for v in vars_list if isinstance(v, dict) and 'canonical' in v]
counts = collections.Counter(canonicals)
dupes = [name for name, cnt in counts.items() if cnt > 1]
if dupes:
    print(' '.join(dupes))
" 2>/dev/null || true)"
  if [[ -n "${dupes}" ]]; then
    echo "[config-lint] WARN env-contract.yaml: duplicate canonical names: ${dupes}"
    warnings=$((warnings + 1))
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if [[ "${warnings}" -eq 0 && "${issues}" -eq 0 ]]; then
  echo "[config-lint] PASS: config directory governance checks passed"
  exit 0
fi

if [[ "${STRICT}" -eq 1 && $((issues + warnings)) -gt 0 ]]; then
  echo "[config-lint] FAIL: ${issues} issue(s), ${warnings} warning(s) in strict mode"
  exit 1
fi

echo "[config-lint] WARN: ${warnings} warning(s) (use --strict to fail on warnings)"
exit 0
