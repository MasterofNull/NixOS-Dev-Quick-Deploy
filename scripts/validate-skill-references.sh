#!/usr/bin/env bash
set -euo pipefail

# Validate that relative references inside SKILL.md files resolve on disk.
# Checks markdown links and inline-code relative paths.

# Override roots with SKILL_REFERENCE_ROOTS (colon-delimited) for tests.
# Example: SKILL_REFERENCE_ROOTS="tests/fixtures/skills/ok:tests/fixtures/skills/bad"
if [[ -n "${SKILL_REFERENCE_ROOTS:-}" ]]; then
  IFS=':' read -r -a ROOTS <<< "${SKILL_REFERENCE_ROOTS}"
else
  ROOTS=(
    ".agent/skills"
    "ai-stack/agents/skills"
  )
fi

status=0

check_target() {
  local skill_file="$1"
  local raw_target="$2"
  local skill_dir target cleaned resolved

  skill_dir="$(dirname "$skill_file")"
  target="$(echo "$raw_target" | tr -d '[:space:]')"
  target="${target#<}"
  target="${target%>}"

  [[ -n "$target" ]] || return 0

  case "$target" in
    http://*|https://*|mailto:*|\#*)
      return 0
      ;;
  esac

  case "$target" in
    ./*|../*)
      ;;
    *)
      return 0
      ;;
  esac

  cleaned="${target%%#*}"
  cleaned="${cleaned%%\?*}"

  resolved="${skill_dir}/${cleaned}"
  if [[ -e "$resolved" ]]; then
    return 0
  fi

  # Some skills intentionally document repo-root command paths (for example
  # ./scripts/system-health-check.sh). Accept those when they resolve from root.
  if [[ "$cleaned" == ./* ]]; then
    local repo_resolved="${cleaned#./}"
    if [[ -e "$repo_resolved" ]]; then
      return 0
    fi
  fi

  echo "MISSING: ${skill_file} -> ${target}" >&2
  status=1
}

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue

  while IFS= read -r skill_file; do
    while IFS= read -r link_target; do
      check_target "$skill_file" "$link_target"
    done < <(
      grep -oE '\[[^]]+\]\([^)]*\)' "$skill_file" \
        | sed -E 's/^[^()]*\(([^)]*)\)$/\1/'
    )

    while IFS= read -r inline_target; do
      check_target "$skill_file" "$inline_target"
    done < <(
      grep -oE '`(\./|\.\./)[^` ]+`' "$skill_file" \
        | tr -d '`'
    )
  done < <(find "$root" -type f -name 'SKILL.md' | sort)
done

if [[ "$status" -eq 0 ]]; then
  echo "PASS: all relative skill references resolve."
else
  cat >&2 <<'EOF'
FAIL: one or more skill references are missing.
Remediation:
1. Add the missing file/folder, or
2. Update the SKILL.md reference to a valid relative path, or
3. Remove stale references from the skill.
EOF
fi

exit "$status"
