#!/usr/bin/env bash
# Compare two exported GitHub code scanning snapshots and report hotspot deltas.
set -euo pipefail

BASE_PATH=""
HEAD_PATH=""
HISTORY_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}/history"
TOP_N=10

usage() {
  cat <<'EOF'
Usage: scripts/security/compare-github-code-scanning-alerts.sh [options]

Compare two GitHub code scanning exports produced by
scripts/security/export-github-code-scanning-alerts.sh.

Options:
  --base path        Older snapshot path
  --head path        Newer snapshot path
  --history-dir dir  Snapshot history directory (default: $AI_SECURITY_AUDIT_DIR/history)
  --top n            Number of delta rows to show (default: 10)
  -h, --help         Show this help text

If --base/--head are omitted, the script compares the latest two snapshots in --history-dir.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE_PATH="${2:?missing value for --base}"
      shift 2
      ;;
    --head)
      HEAD_PATH="${2:?missing value for --head}"
      shift 2
      ;;
    --history-dir)
      HISTORY_DIR="${2:?missing value for --history-dir}"
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

if [[ -z "${BASE_PATH}" || -z "${HEAD_PATH}" ]]; then
  mapfile -t snapshots < <(find "${HISTORY_DIR}" -maxdepth 1 -type f -name 'github-code-scanning-alerts-*.json' | sort)
  if (( ${#snapshots[@]} < 2 )); then
    echo "Need at least two snapshots in ${HISTORY_DIR} or pass --base and --head." >&2
    exit 2
  fi
  BASE_PATH="${snapshots[-2]}"
  HEAD_PATH="${snapshots[-1]}"
fi

[[ -f "${BASE_PATH}" ]] || {
  echo "Missing base snapshot: ${BASE_PATH}" >&2
  exit 2
}
[[ -f "${HEAD_PATH}" ]] || {
  echo "Missing head snapshot: ${HEAD_PATH}" >&2
  exit 2
}

jq -nr \
  --slurpfile base_file "${BASE_PATH}" \
  --slurpfile head_file "${HEAD_PATH}" \
  --arg top_n "${TOP_N}" \
  '
  $base_file[0] as $base
  | $head_file[0] as $head
  |
  def counts($alerts; $keyfn):
    $alerts
    | group_by($keyfn)
    | map({key: (.[0] | $keyfn), count: length});

  def count_map($alerts; $keyfn):
    reduce counts($alerts; $keyfn)[] as $item ({}; .[$item.key] = $item.count);

  def delta_table($base_map; $head_map):
    (($base_map + $head_map) | keys_unsorted | unique)
    | map({
        key: .,
        base: ($base_map[.] // 0),
        head: ($head_map[.] // 0),
        delta: (($head_map[.] // 0) - ($base_map[.] // 0))
      })
    | map(select(.delta != 0))
    | sort_by(-(.delta | if . < 0 then -. else . end), .key);

  def trivy_env:
    .most_recent_instance.environment
    | if type == "string" then (fromjson? // {}) else {} end;

  def trivy_image:
    trivy_env.image // "unknown";

  def trivy_category:
    trivy_env.category // .most_recent_instance.category // "unknown";

  def fmt_delta:
    if . > 0 then "+\(tostring)" else tostring end;

  {
    base_generated_at: $base.generated_at,
    head_generated_at: $head.generated_at,
    base_total: $base.total,
    head_total: $head.total,
    total_delta: ($head.total - $base.total),
    changed_paths: delta_table(
      count_map($base.alerts; .most_recent_instance.location.path // "unknown");
      count_map($head.alerts; .most_recent_instance.location.path // "unknown")
    )[:($top_n | tonumber)],
    changed_trivy_images: delta_table(
      count_map(($base.alerts | map(select(.tool.name == "Trivy"))); trivy_image);
      count_map(($head.alerts | map(select(.tool.name == "Trivy"))); trivy_image)
    )[:($top_n | tonumber)],
    changed_trivy_categories: delta_table(
      count_map(($base.alerts | map(select(.tool.name == "Trivy"))); trivy_category);
      count_map(($head.alerts | map(select(.tool.name == "Trivy"))); trivy_category)
    )[:($top_n | tonumber)]
  }
  | "GitHub Code Scanning Delta",
    "base_generated_at: \(.base_generated_at)",
    "head_generated_at: \(.head_generated_at)",
    "base_total: \(.base_total)",
    "head_total: \(.head_total)",
    "total_delta: \(.total_delta)",
    "",
    "Changed paths:",
    (.changed_paths[]? | "  \(.delta | fmt_delta)\t\(.key)\t(\(.base) -> \(.head))"),
    "",
    "Changed Trivy images:",
    (.changed_trivy_images[]? | "  \(.delta | fmt_delta)\t\(.key)\t(\(.base) -> \(.head))"),
    "",
    "Changed Trivy categories:",
    (.changed_trivy_categories[]? | "  \(.delta | fmt_delta)\t\(.key)\t(\(.base) -> \(.head))")
  '
