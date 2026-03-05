#!/usr/bin/env bash
set -euo pipefail

# Enforce deterministic external references in skill docs.
# Floating GitHub branch links (main/master) are not allowed.

ROOTS=(
  ".agent/skills"
  "ai-stack/agents/skills"
)

PATTERN='raw\.githubusercontent\.com/.*/(main|master)/|github\.com/.*/blob/(main|master)/'

tmp_hits="$(mktemp)"
trap 'rm -f "$tmp_hits"' EXIT

status=0

scan_root() {
  local root="$1"

  if command -v rg >/dev/null 2>&1; then
    rg -n \
      -g 'SKILL.md' \
      -g '*.md' \
      -e 'raw\.githubusercontent\.com/.*/(main|master)/' \
      -e 'github\.com/.*/blob/(main|master)/' \
      "$root" || true
    return
  fi

  while IFS= read -r file; do
    grep -nHE "$PATTERN" "$file" || true
  done < <(find "$root" -type f \( -name 'SKILL.md' -o -name '*.md' \) | sort)
}

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  scan_root "$root" >>"$tmp_hits"
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
