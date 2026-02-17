#!/usr/bin/env bash
set -euo pipefail

# Enforce a minimum viable skill contract:
# - required SKILL.md frontmatter keys (name, description)
# - one-hop relative references from SKILL.md (no deep chains)
# - maintenance/version stanza recommended (warning-only)

ROOTS=(
  ".agent/skills"
  "ai-stack/agents/skills"
)

warnings=0

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: rg is required for lint-skill-template.sh" >&2
  exit 2
fi

trim_target() {
  local t="$1"
  t="${t//[[:space:]]/}"
  t="${t#<}"
  t="${t%>}"
  t="${t%%#*}"
  t="${t%%\?*}"
  printf '%s' "$t"
}

check_frontmatter() {
  local skill_file="$1"
  local fm
  fm="$(awk '
    NR == 1 && $0 == "---" { in_fm = 1; next }
    in_fm && $0 == "---" { exit }
    in_fm { print }
  ' "$skill_file")"

  if [[ -z "$fm" ]]; then
    echo "WARN: missing YAML frontmatter in ${skill_file}" >&2
    ((warnings++)) || true
    return
  fi

  if ! printf '%s\n' "$fm" | rg -q '^name:'; then
    echo "WARN: missing required frontmatter key 'name' in ${skill_file}" >&2
    ((warnings++)) || true
  fi
  if ! printf '%s\n' "$fm" | rg -q '^description:'; then
    echo "WARN: missing required frontmatter key 'description' in ${skill_file}" >&2
    ((warnings++)) || true
  fi
}

check_reference_depth() {
  local skill_file="$1"
  local target cleaned normalized
  local content_no_code

  content_no_code="$(
    awk '
      /^```/ { in_block = !in_block; next }
      !in_block { print }
    ' "$skill_file"
  )"

  while IFS= read -r target; do
    cleaned="$(trim_target "$target")"
    [[ -n "$cleaned" ]] || continue

    case "$cleaned" in
      http://*|https://*|mailto:*|\#*)
        continue
        ;;
      ./*|../*)
        ;;
      *)
        continue
        ;;
    esac

    normalized="$cleaned"
    while [[ "$normalized" == ./* ]]; do
      normalized="${normalized#./}"
    done
    while [[ "$normalized" == ../* ]]; do
      normalized="${normalized#../}"
    done

    # one-hop max from SKILL.md:
    # allowed: file.md, references/file.md, scripts/tool.py
    # blocked: references/deeper/file.md
    if [[ "$normalized" == */*/* ]]; then
      echo "WARN: deep reference (>1 hop) in ${skill_file}: ${cleaned}" >&2
      ((warnings++)) || true
    fi
  done < <(
    {
      printf '%s\n' "$content_no_code" | grep -oE '\[[^]]+\]\([^)]*\)' | sed -E 's/^[^()]*\(([^)]*)\)$/\1/'
    } || true
  )
}

check_maintenance_stanza() {
  local skill_file="$1"
  if ! rg -qi 'maintenance|version' "$skill_file"; then
    echo "WARN: no maintenance/version stanza detected in ${skill_file}" >&2
    ((warnings++)) || true
  fi
}

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  while IFS= read -r skill_file; do
    check_frontmatter "$skill_file"
    check_reference_depth "$skill_file"
    check_maintenance_stanza "$skill_file"
  done < <(find "$root" -type f -name 'SKILL.md' | sort)
done

if [[ "$warnings" -gt 0 ]]; then
  echo "PASS: skill template lint completed with ${warnings} warning(s) (non-blocking)." >&2
else
  echo "PASS: skill template lint checks passed."
fi

exit 0
