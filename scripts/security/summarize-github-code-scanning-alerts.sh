#!/usr/bin/env bash
# Summarize exported GitHub code scanning alerts into hotspot buckets.
set -euo pipefail

INPUT_PATH="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}/github-code-scanning-alerts.json"
TOP_N=10
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/security/summarize-github-code-scanning-alerts.sh [options]

Summarize a GitHub code scanning export produced by
scripts/security/export-github-code-scanning-alerts.sh.

Options:
  --input path   Path to exported JSON
  --top n        Number of hotspot rows to show per section (default: 10)
  -h, --help     Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT_PATH="${2:?missing value for --input}"
      shift 2
      ;;
    --top)
      TOP_N="${2:?missing value for --top}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v jq >/dev/null 2>&1 || {
  echo "Missing required command: jq" >&2
  exit 2
}
command -v python3 >/dev/null 2>&1 || {
  echo "Missing required command: python3" >&2
  exit 2
}

[[ -f "${INPUT_PATH}" ]] || {
  echo "Missing export file: ${INPUT_PATH}" >&2
  exit 2
}

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

workflow_categories_path="${tmp_dir}/workflow-categories.json"
ROOT_DIR="${ROOT_DIR}" python3 - <<'PY' > "${workflow_categories_path}"
import json
import os
from pathlib import Path

import yaml

workflow = yaml.safe_load(
    (Path(os.environ["ROOT_DIR"]) / ".github/workflows/security.yml").read_text()
)
core = [item["category"] for item in workflow["jobs"]["trivy-scan-core"]["strategy"]["matrix"]["include"]]
custom = [f"trivy-custom-{svc}" for svc in workflow["jobs"]["trivy-scan-custom"]["strategy"]["matrix"]["service"]]
print(json.dumps(core + custom))
PY

print_table() {
  local title="$1"
  local jq_filter="$2"
  shift 2

  printf '\n%s\n' "${title}"
  jq -r "$@" "${jq_filter}" "${INPUT_PATH}"
}

jq -r '
  "GitHub Code Scanning Summary",
  "generated_at: \(.generated_at)",
  "repository: \(.repository)",
  "state: \(.state)",
  "total: \(.total)",
  "",
  "By tool:",
  (.by_tool | to_entries | sort_by(-.value, .key)[] | "  \(.key): \(.value)"),
  "",
  "By severity:",
  (.by_severity | to_entries | sort_by(-.value, .key)[] | "  \(.key): \(.value)")
' "${INPUT_PATH}"

print_table \
  "Top affected paths:" \
  '
  .alerts
  | group_by(.most_recent_instance.location.path // "unknown")
  | map({
      key: (.[0].most_recent_instance.location.path // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  '

print_table \
  "Top rule ids:" \
  '
  .alerts
  | group_by(.rule.id // "unknown")
  | map({
      key: (.[0].rule.id // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  '

print_table \
  "Top Trivy paths:" \
  '
  .alerts
  | map(select(.tool.name == "Trivy"))
  | group_by(.most_recent_instance.location.path // "unknown")
  | map({
      key: (.[0].most_recent_instance.location.path // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  '

print_table \
  "Top Trivy images:" \
  '
  .alerts
  | map(select(.tool.name == "Trivy"))
  | map(. + {
      trivy_environment: (
        .most_recent_instance.environment
        | if type == "string" then (fromjson? // {}) else {} end
      )
    })
  | group_by(.trivy_environment.image // "unknown")
  | map({
      key: (.[0].trivy_environment.image // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  '

print_table \
  "Top Trivy categories:" \
  '
  .alerts
  | map(select(.tool.name == "Trivy"))
  | map(. + {
      trivy_environment: (
        .most_recent_instance.environment
        | if type == "string" then (fromjson? // {}) else {} end
      )
    })
  | group_by(.trivy_environment.category // .most_recent_instance.category // "unknown")
  | map({
      key: (.[0].trivy_environment.category // .[0].most_recent_instance.category // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  '

print_table \
  "Current workflow-backed Trivy categories:" \
  '
  .alerts
  | map(select(.tool.name == "Trivy"))
  | map(. + {
      trivy_environment: (
        .most_recent_instance.environment
        | if type == "string" then (fromjson? // {}) else {} end
      )
    })
  | map(select(
      (
        .trivy_environment.category
        // .most_recent_instance.category
        // "unknown"
      ) as $category
      | ($category | IN($workflow_categories[0][]))
    ))
  | group_by(.trivy_environment.category // .most_recent_instance.category // "unknown")
  | map({
      key: (.[0].trivy_environment.category // .[0].most_recent_instance.category // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  ' \
  --slurpfile workflow_categories "${workflow_categories_path}"

print_table \
  "Current workflow-backed Trivy images:" \
  '
  .alerts
  | map(select(.tool.name == "Trivy"))
  | map(. + {
      trivy_environment: (
        .most_recent_instance.environment
        | if type == "string" then (fromjson? // {}) else {} end
      )
    })
  | map(select(
      (
        .trivy_environment.category
        // .most_recent_instance.category
        // "unknown"
      ) as $category
      | ($category | IN($workflow_categories[0][]))
    ))
  | group_by(.trivy_environment.image // "unknown")
  | map({
      key: (.[0].trivy_environment.image // "unknown"),
      count: length
    })
  | sort_by(-.count, .key)
  | .[:'"${TOP_N}"'][]
  | "  \(.count)\t\(.key)"
  ' \
  --slurpfile workflow_categories "${workflow_categories_path}"
