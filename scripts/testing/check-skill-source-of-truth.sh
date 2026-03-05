#!/usr/bin/env bash
set -euo pipefail

# Enforce canonical skill locations and block legacy .claude skill trees.

status=0

while IFS= read -r skill_file; do
  rel="${skill_file#./}"

  case "$rel" in
    .agent/skills/*|.agent/python_skills/*|ai-stack/agents/skills/*|archive/*)
      ;;
    .claude/*)
      echo "FAIL: legacy .claude skill path detected: $skill_file" >&2
      status=1
      ;;
    *)
      echo "FAIL: SKILL.md outside approved roots: $skill_file" >&2
      status=1
      ;;
  esac
done < <(find . -type f -name 'SKILL.md' | sort)

if [[ "$status" -eq 0 ]]; then
  echo "PASS: skill files are confined to approved roots."
fi

exit "$status"
