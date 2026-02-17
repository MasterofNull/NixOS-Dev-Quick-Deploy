#!/usr/bin/env bash
set -euo pipefail

# Enforce deterministic external references in skill docs.
# Floating GitHub branch links (main/master) are not allowed.

ROOTS=(
  ".agent/skills"
  "ai-stack/agents/skills"
)

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: rg is required for lint-skill-external-deps.sh" >&2
  exit 2
fi

tmp_hits="$(mktemp)"
trap 'rm -f "$tmp_hits"' EXIT

status=0

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue

  rg -n \
    -g 'SKILL.md' \
    -g '*.md' \
    -e 'raw\.githubusercontent\.com/.*/(main|master)/' \
    -e 'github\.com/.*/blob/(main|master)/' \
    "$root" >>"$tmp_hits" || true
done

if [[ -s "$tmp_hits" ]]; then
  echo "FAIL: floating external dependency links found in skill docs:" >&2
  cat "$tmp_hits" >&2
  status=1
fi

if [[ $status -eq 0 ]]; then
  echo "PASS: skill external dependency links are pinned/non-floating."
fi

exit "$status"
