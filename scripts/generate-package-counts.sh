#!/usr/bin/env bash
#
# Generate package counts from flake-evaluated configurations.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEFAULT_OUTPUT="${PROJECT_ROOT}/config/package-count-baseline.json"
NIX_EVAL_TIMEOUT_SECONDS="${NIX_EVAL_TIMEOUT_SECONDS:-45}"
NIX_EXPERIMENTAL_FEATURES="nix-command flakes"

FLAKE_REF="path:${PROJECT_ROOT}"
OUTPUT_PATH=""

usage() {
  cat <<'EOF'
Usage: ./scripts/generate-package-counts.sh [options]

Options:
  --flake-ref REF   Flake reference to evaluate (default: path:<repo-root>)
  --output PATH     Write JSON output to PATH (default: stdout)
  --baseline        Write JSON output to config/package-count-baseline.json
  -h, --help        Show this help

Environment:
  NIX_EVAL_TIMEOUT_SECONDS  Timeout per nix eval call (default: 45)
EOF
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: Required command not found: ${cmd}" >&2
    exit 1
  }
}

nix_eval() {
  local -a nix_cmd=(nix --extra-experimental-features "$NIX_EXPERIMENTAL_FEATURES" eval "$@")
  if command -v timeout >/dev/null 2>&1; then
    timeout "${NIX_EVAL_TIMEOUT_SECONDS}s" "${nix_cmd[@]}"
  else
    "${nix_cmd[@]}"
  fi
}

list_attrs() {
  local attr="$1"
  nix_eval --raw \
    --apply 'attrs: builtins.concatStringsSep "\n" (builtins.sort builtins.lessThan (builtins.attrNames attrs))' \
    "${FLAKE_REF}#${attr}"
}

count_system_packages() {
  local target="$1"
  nix_eval --raw \
    --apply 'pkgs: builtins.toString (builtins.length pkgs)' \
    "${FLAKE_REF}#nixosConfigurations.\"${target}\".config.environment.systemPackages"
}

count_home_packages() {
  local target="$1"
  nix_eval --raw \
    --apply 'pkgs: builtins.toString (builtins.length pkgs)' \
    "${FLAKE_REF}#homeConfigurations.\"${target}\".config.home.packages"
}

get_primary_user() {
  local target="$1"
  nix_eval --raw "${FLAKE_REF}#nixosConfigurations.\"${target}\".config.mySystem.primaryUser"
}

avg_of() {
  local total="$1"
  local count="$2"
  awk -v t="$total" -v c="$count" 'BEGIN { if (c == 0) { printf "0.00" } else { printf "%.2f", t / c } }'
}

emit_map_entries() {
  local -n map_ref="$1"
  local indent="$2"
  local first=true
  local key

  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    if [[ "$first" == false ]]; then
      printf ',\n'
    fi
    first=false
    printf '%s"%s": %s' "$indent" "$key" "${map_ref[$key]}"
  done < <(printf '%s\n' "${!map_ref[@]}" | sort)
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:?missing value for --output}"
      shift 2
      ;;
    --baseline)
      OUTPUT_PATH="${DEFAULT_OUTPUT}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_command nix

declare -A system_counts
declare -A home_counts
declare -A combined_counts

system_total=0
system_count=0
system_min=-1
system_max=0

home_total=0
home_count=0
home_min=-1
home_max=0

combined_total=0
combined_count=0
combined_min=-1
combined_max=0

nixos_raw="$(list_attrs "nixosConfigurations")"
home_raw="$(list_attrs "homeConfigurations")"

mapfile -t nixos_targets <<<"$nixos_raw"
mapfile -t home_targets <<<"$home_raw"

for home_target in "${home_targets[@]}"; do
  [[ -z "$home_target" ]] && continue
  count="$(count_home_packages "$home_target")"
  home_counts["$home_target"]="$count"
  home_total=$((home_total + count))
  home_count=$((home_count + 1))
  if [[ "$home_min" -lt 0 || "$count" -lt "$home_min" ]]; then
    home_min="$count"
  fi
  if [[ "$count" -gt "$home_max" ]]; then
    home_max="$count"
  fi
done

for nixos_target in "${nixos_targets[@]}"; do
  [[ -z "$nixos_target" ]] && continue
  count="$(count_system_packages "$nixos_target")"
  system_counts["$nixos_target"]="$count"
  system_total=$((system_total + count))
  system_count=$((system_count + 1))
  if [[ "$system_min" -lt 0 || "$count" -lt "$system_min" ]]; then
    system_min="$count"
  fi
  if [[ "$count" -gt "$system_max" ]]; then
    system_max="$count"
  fi

  host_name="${nixos_target%-*}"
  primary_user="$(get_primary_user "$nixos_target")"

  preferred_home_target="${primary_user}-${host_name}"
  fallback_home_target="${primary_user}"
  home_count_for_target=0

  if [[ -n "${home_counts[$preferred_home_target]:-}" ]]; then
    home_count_for_target="${home_counts[$preferred_home_target]}"
  elif [[ -n "${home_counts[$fallback_home_target]:-}" ]]; then
    home_count_for_target="${home_counts[$fallback_home_target]}"
  fi

  combined=$((count + home_count_for_target))
  combined_counts["$nixos_target"]="$combined"
  combined_total=$((combined_total + combined))
  combined_count=$((combined_count + 1))
  if [[ "$combined_min" -lt 0 || "$combined" -lt "$combined_min" ]]; then
    combined_min="$combined"
  fi
  if [[ "$combined" -gt "$combined_max" ]]; then
    combined_max="$combined"
  fi
done

if [[ "$system_min" -lt 0 ]]; then system_min=0; fi
if [[ "$home_min" -lt 0 ]]; then home_min=0; fi
if [[ "$combined_min" -lt 0 ]]; then combined_min=0; fi

system_avg="$(avg_of "$system_total" "$system_count")"
home_avg="$(avg_of "$home_total" "$home_count")"
combined_avg="$(avg_of "$combined_total" "$combined_count")"

emit_json() {
  {
    echo "{"
    echo '  "nixosTargets": {'
    emit_map_entries system_counts "    "
    echo
    echo "  },"
    echo '  "homeTargets": {'
    emit_map_entries home_counts "    "
    echo
    echo "  },"
    echo '  "combinedTargets": {'
    emit_map_entries combined_counts "    "
    echo
    echo "  },"
    echo '  "summary": {'
    echo "    \"nixosTargetCount\": ${system_count},"
    echo "    \"homeTargetCount\": ${home_count},"
    echo '    "systemPackages": {'
    echo "      \"min\": ${system_min},"
    echo "      \"max\": ${system_max},"
    echo "      \"avg\": ${system_avg}"
    echo "    },"
    echo '    "homePackages": {'
    echo "      \"min\": ${home_min},"
    echo "      \"max\": ${home_max},"
    echo "      \"avg\": ${home_avg}"
    echo "    },"
    echo '    "combinedPackages": {'
    echo "      \"min\": ${combined_min},"
    echo "      \"max\": ${combined_max},"
    echo "      \"avg\": ${combined_avg}"
    echo "    }"
    echo "  }"
    echo "}"
  }
}

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  emit_json > "$OUTPUT_PATH"
  echo "Wrote package counts to ${OUTPUT_PATH}"
else
  emit_json
fi
