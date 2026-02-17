#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FLAKE_REF="path:${REPO_ROOT}"
LOCK_FILE=""
REPORT_JSON="${REPO_ROOT}/.reports/flake-validation-report.json"
REPORT_MD="${REPO_ROOT}/.reports/flake-validation-report.md"
CHECK_NIX_METADATA=true

usage() {
  cat <<'EOF'
Usage: ./scripts/validate-flake-inputs.sh [options]

Validate flake input compatibility, lock integrity, dependency wiring, and
basic supply-chain security guardrails.

Options:
  --flake-ref REF       Flake ref to validate (default: path:<repo-root>)
  --lock-file PATH      Explicit flake.lock path (default: auto-resolve from --flake-ref)
  --report-json PATH    JSON report path (default: ./.reports/flake-validation-report.json)
  --report-md PATH      Markdown report path (default: ./.reports/flake-validation-report.md)
  --skip-nix-metadata   Skip 'nix flake metadata' probe (useful in restricted sandbox)
  -h, --help            Show this help
EOF
}

resolve_local_flake_path() {
  local ref="${1:-}"
  case "$ref" in
    path:*) printf '%s\n' "${ref#path:}" ;;
    /*) printf '%s\n' "$ref" ;;
    .|./*|../*)
      (cd "$ref" >/dev/null 2>&1 && pwd) || true
      ;;
    *) ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --lock-file)
      LOCK_FILE="${2:?missing value for --lock-file}"
      shift 2
      ;;
    --report-json)
      REPORT_JSON="${2:?missing value for --report-json}"
      shift 2
      ;;
    --report-md)
      REPORT_MD="${2:?missing value for --report-md}"
      shift 2
      ;;
    --skip-nix-metadata)
      CHECK_NIX_METADATA=false
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

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for flake input validation." >&2
  exit 2
fi

LOCAL_FLAKE_PATH="$(resolve_local_flake_path "$FLAKE_REF")"
if [[ -z "$LOCK_FILE" ]]; then
  if [[ -n "$LOCAL_FLAKE_PATH" ]]; then
    LOCK_FILE="${LOCAL_FLAKE_PATH}/flake.lock"
  else
    echo "ERROR: Could not resolve local flake path from '${FLAKE_REF}'. Use --lock-file." >&2
    exit 2
  fi
fi

if [[ ! -f "$LOCK_FILE" ]]; then
  echo "ERROR: flake lock file not found: $LOCK_FILE" >&2
  exit 2
fi

errors_file="$(mktemp)"
warnings_file="$(mktemp)"
passes_file="$(mktemp)"
trap 'rm -f "$errors_file" "$warnings_file" "$passes_file"' EXIT

add_error() {
  echo "$1" >>"$errors_file"
}

add_warning() {
  echo "$1" >>"$warnings_file"
}

add_pass() {
  echo "$1" >>"$passes_file"
}

json_array_from_file() {
  local file="$1"
  jq -Rsc 'split("\n")[:-1]' "$file"
}

declared_nixpkgs_ref() {
  local flake_nix="$1"
  sed -nE 's/^[[:space:]]*nixpkgs\.url[[:space:]]*=[[:space:]]*"github:NixOS\/nixpkgs\/([^"]+)".*/\1/p' "$flake_nix" | head -n1
}

declared_home_manager_ref() {
  local flake_nix="$1"
  sed -nE '/home-manager[[:space:]]*=[[:space:]]*\{/,/};/ s/^[[:space:]]*url[[:space:]]*=[[:space:]]*"github:nix-community\/home-manager\/([^"]+)".*/\1/p' "$flake_nix" | head -n1
}

declared_home_manager_follows() {
  local flake_nix="$1"
  sed -nE '/home-manager[[:space:]]*=[[:space:]]*\{/,/};/ s/^[[:space:]]*inputs\.nixpkgs\.follows[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$flake_nix" | head -n1
}

validate_dependency_graph() {
  local missing_links
  missing_links="$(
    jq -r '
      .nodes as $nodes
      | .nodes
      | to_entries[]
      | .key as $node
      | (.value.inputs // {})
      | to_entries[]
      | .key as $input
      | .value as $target
      | if ($target | type) == "string" then
          if $nodes[$target] then empty else "\($node).inputs.\($input) -> missing node: \($target)" end
        elif ($target | type) == "array" then
          [ $target[] | select(($nodes[.] // null) == null) ] as $missing
          | if ($missing | length) == 0 then empty else
              "\($node).inputs.\($input) -> missing path nodes: \($missing | join(", "))"
            end
        else
          "\($node).inputs.\($input) has unsupported type: \($target | type)"
        end
    ' "$LOCK_FILE"
  )"

  if [[ -n "$missing_links" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      add_error "Dependency graph: ${line}"
    done <<<"$missing_links"
  else
    add_pass "Dependency graph check passed (all input references resolve to lock nodes)."
  fi
}

validate_integrity_and_security() {
  local missing_hashes
  missing_hashes="$(jq -r '
    .nodes
    | to_entries[]
    | select(.key != "root")
    | select((.value.locked.narHash // "") == "")
    | .key
  ' "$LOCK_FILE")"

  if [[ -n "$missing_hashes" ]]; then
    while IFS= read -r node; do
      [[ -n "$node" ]] || continue
      add_error "Missing narHash integrity lock for input '${node}'."
    done <<<"$missing_hashes"
  else
    add_pass "Integrity hash check passed (narHash present for all non-root inputs)."
  fi

  local missing_revs
  missing_revs="$(jq -r '
    .nodes
    | to_entries[]
    | select(.key != "root")
    | select((.value.locked.type // "") | test("^(github|gitlab|git|sourcehut)$"))
    | select((.value.locked.rev // "") == "")
    | .key
  ' "$LOCK_FILE")"

  if [[ -n "$missing_revs" ]]; then
    while IFS= read -r node; do
      [[ -n "$node" ]] || continue
      add_error "Missing immutable revision pin for git-based input '${node}'."
    done <<<"$missing_revs"
  else
    add_pass "Immutable revision check passed for git-based inputs."
  fi

  local insecure_urls
  insecure_urls="$(jq -r '
    .nodes
    | to_entries[]
    | select(.key != "root")
    | .key as $name
    | [
        (.value.original.url // ""),
        (.value.locked.url // "")
      ]
    | map(select(startswith("http://")))
    | .[]
    | "\($name): \(.)"
  ' "$LOCK_FILE")"

  if [[ -n "$insecure_urls" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      add_error "Insecure HTTP source detected: ${line}"
    done <<<"$insecure_urls"
  else
    add_pass "Source transport check passed (no HTTP flake input URLs detected)."
  fi

  local floating_refs
  floating_refs="$(jq -r '
    .nodes
    | to_entries[]
    | select(.key != "root")
    | .key as $name
    | (.value.original.ref // "") as $ref
    | select($ref | test("^(main|master|unstable|nixos-unstable|nixpkgs-unstable)$"))
    | "\($name): \($ref)"
  ' "$LOCK_FILE")"

  if [[ -n "$floating_refs" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      add_warning "Floating branch ref detected (consider release/tag pin): ${line}"
    done <<<"$floating_refs"
  else
    add_pass "Floating branch ref check passed."
  fi

  local local_paths
  local_paths="$(jq -r '
    .nodes
    | to_entries[]
    | select(.key != "root")
    | select((.value.locked.type // "") == "path")
    | .key
  ' "$LOCK_FILE")"

  if [[ -n "$local_paths" ]]; then
    while IFS= read -r node; do
      [[ -n "$node" ]] || continue
      add_warning "Local path input detected for '${node}' (review reproducibility implications)."
    done <<<"$local_paths"
  else
    add_pass "Local path input check passed."
  fi
}

validate_compatibility() {
  local root_nixpkgs_node root_nixpkgs_ref hm_lock_ref hm_follows_lock
  root_nixpkgs_node="$(jq -r '.nodes.root.inputs.nixpkgs // empty' "$LOCK_FILE")"
  if [[ -z "$root_nixpkgs_node" ]]; then
    add_error "Root flake input 'nixpkgs' is missing from lock graph."
  else
    root_nixpkgs_ref="$(jq -r --arg node "$root_nixpkgs_node" '.nodes[$node].original.ref // empty' "$LOCK_FILE")"
    if [[ -n "$root_nixpkgs_ref" ]]; then
      add_pass "Root nixpkgs lock ref: ${root_nixpkgs_ref}"
    else
      add_warning "Could not determine root nixpkgs ref from lock metadata."
    fi
  fi

  hm_lock_ref="$(jq -r '.nodes["home-manager"].original.ref // empty' "$LOCK_FILE")"
  if [[ -n "$hm_lock_ref" ]]; then
    add_pass "Home Manager lock ref: ${hm_lock_ref}"
  else
    add_warning "Could not determine Home Manager ref from lock metadata."
  fi

  hm_follows_lock="$(jq -r '
    .nodes["home-manager"].inputs.nixpkgs as $x
    | if ($x | type) == "string" then $x
      elif ($x | type) == "array" then ($x | last)
      else ""
      end
  ' "$LOCK_FILE")"
  if [[ "$hm_follows_lock" != "nixpkgs" ]]; then
    add_error "Home Manager nixpkgs follow target is '${hm_follows_lock}' (expected 'nixpkgs')."
  else
    add_pass "Home Manager follows root nixpkgs input."
  fi

  if [[ -n "$LOCAL_FLAKE_PATH" && -f "${LOCAL_FLAKE_PATH}/flake.nix" ]]; then
    local flake_nix declared_nix declared_hm declared_hm_follows
    flake_nix="${LOCAL_FLAKE_PATH}/flake.nix"
    declared_nix="$(declared_nixpkgs_ref "$flake_nix")"
    declared_hm="$(declared_home_manager_ref "$flake_nix")"
    declared_hm_follows="$(declared_home_manager_follows "$flake_nix")"

    if [[ -n "$declared_nix" && -n "${root_nixpkgs_ref:-}" && "$declared_nix" != "$root_nixpkgs_ref" ]]; then
      add_error "Declared nixpkgs ref '${declared_nix}' != locked root nixpkgs ref '${root_nixpkgs_ref}'. Run 'nix flake update --flake ${LOCAL_FLAKE_PATH}'."
    elif [[ -n "$declared_nix" && -n "${root_nixpkgs_ref:-}" ]]; then
      add_pass "Declared nixpkgs ref matches lock (${declared_nix})."
    fi

    if [[ -n "$declared_hm" && -n "$hm_lock_ref" && "$declared_hm" != "$hm_lock_ref" ]]; then
      add_error "Declared home-manager ref '${declared_hm}' != locked home-manager ref '${hm_lock_ref}'. Run 'nix flake update --flake ${LOCAL_FLAKE_PATH}'."
    elif [[ -n "$declared_hm" && -n "$hm_lock_ref" ]]; then
      add_pass "Declared home-manager ref matches lock (${declared_hm})."
    fi

    if [[ -n "$declared_hm_follows" && "$declared_hm_follows" != "nixpkgs" ]]; then
      add_error "home-manager.inputs.nixpkgs.follows is '${declared_hm_follows}' (expected 'nixpkgs')."
    elif [[ -n "$declared_hm_follows" ]]; then
      add_pass "home-manager.inputs.nixpkgs.follows is correctly set to 'nixpkgs'."
    else
      add_warning "Could not parse home-manager.inputs.nixpkgs.follows from flake.nix."
    fi
  else
    add_warning "Local flake.nix not available for declared-vs-locked compatibility checks."
  fi
}

probe_nix_metadata() {
  if [[ "$CHECK_NIX_METADATA" != true ]]; then
    add_warning "Skipped nix flake metadata probe (--skip-nix-metadata)."
    return
  fi

  if ! command -v nix >/dev/null 2>&1; then
    add_warning "nix command not found; skipped metadata probe."
    return
  fi

  if nix flake metadata --json "$FLAKE_REF" >/dev/null 2>&1; then
    add_pass "nix flake metadata probe succeeded."
  else
    add_warning "nix flake metadata probe failed in current environment (daemon/network restricted)."
  fi
}

validate_dependency_graph
validate_integrity_and_security
validate_compatibility
probe_nix_metadata

errors_json="$(json_array_from_file "$errors_file")"
warnings_json="$(json_array_from_file "$warnings_file")"
passes_json="$(json_array_from_file "$passes_file")"

mkdir -p "$(dirname "$REPORT_JSON")" "$(dirname "$REPORT_MD")"
timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

jq -n \
  --arg timestamp "$timestamp" \
  --arg flake_ref "$FLAKE_REF" \
  --arg lock_file "$LOCK_FILE" \
  --argjson errors "$errors_json" \
  --argjson warnings "$warnings_json" \
  --argjson passes "$passes_json" \
  '{
    timestamp: $timestamp,
    flakeRef: $flake_ref,
    lockFile: $lock_file,
    summary: {
      errors: ($errors | length),
      warnings: ($warnings | length),
      passed: ($passes | length)
    },
    checks: {
      errors: $errors,
      warnings: $warnings,
      passed: $passes
    }
  }' >"$REPORT_JSON"

{
  echo "# Flake Validation Report"
  echo
  echo "- Timestamp: ${timestamp}"
  echo "- Flake ref: \`${FLAKE_REF}\`"
  echo "- Lock file: \`${LOCK_FILE}\`"
  echo
  echo "## Summary"
  echo
  echo "- Errors: $(jq -r '.summary.errors' "$REPORT_JSON")"
  echo "- Warnings: $(jq -r '.summary.warnings' "$REPORT_JSON")"
  echo "- Passed checks: $(jq -r '.summary.passed' "$REPORT_JSON")"
  echo
  echo "## Errors"
  jq -r '.checks.errors[]? | "- " + .' "$REPORT_JSON"
  echo
  echo "## Warnings"
  jq -r '.checks.warnings[]? | "- " + .' "$REPORT_JSON"
  echo
  echo "## Passed Checks"
  jq -r '.checks.passed[]? | "- " + .' "$REPORT_JSON"
} >"$REPORT_MD"

error_count="$(jq -r '.summary.errors' "$REPORT_JSON")"
warning_count="$(jq -r '.summary.warnings' "$REPORT_JSON")"
pass_count="$(jq -r '.summary.passed' "$REPORT_JSON")"

echo "Flake validation complete: ${pass_count} passed, ${warning_count} warnings, ${error_count} errors."
echo "JSON report: ${REPORT_JSON}"
echo "Markdown report: ${REPORT_MD}"

if [[ "$error_count" -gt 0 ]]; then
  exit 1
fi

exit 0
