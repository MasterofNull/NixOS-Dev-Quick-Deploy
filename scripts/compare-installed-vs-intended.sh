#!/usr/bin/env bash
#
# Compare critical intended packages/apps vs what is currently installed.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_NAME="${HOSTNAME_OVERRIDE:-$(hostname -s 2>/dev/null || hostname)}"
PROFILE="${PROFILE_OVERRIDE:-}"
FLAKE_REF="path:${REPO_ROOT}"
TARGET_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage: ./scripts/compare-installed-vs-intended.sh [options]

Options:
  --host NAME      Host name (default: current host)
  --profile NAME   Profile (ai-dev|gaming|minimal). If omitted, read from facts.
  --target NAME    Explicit nixos target (<host>-<profile>) for flake eval
  --flake-ref REF  Flake reference (default: path:<repo-root>)
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST_NAME="${2:?missing value for --host}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:?missing value for --profile}"
      shift 2
      ;;
    --target)
      TARGET_OVERRIDE="${2:?missing value for --target}"
      shift 2
      ;;
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROFILE" ]]; then
  facts_path="${REPO_ROOT}/nix/hosts/${HOST_NAME}/facts.nix"
  if [[ -f "$facts_path" ]]; then
    PROFILE="$(sed -n 's/^[[:space:]]*profile[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$facts_path" | head -n1)"
  fi
fi

if [[ -z "$PROFILE" ]]; then
  PROFILE="ai-dev"
fi

if [[ -n "$TARGET_OVERRIDE" ]]; then
  TARGET="$TARGET_OVERRIDE"
else
  TARGET="${HOST_NAME}-${PROFILE}"
fi

declare -a intended_commands=()
declare -a missing_commands=()
declare -a missing_flatpaks=()

# Critical CLI commands expected across clean deployments.
intended_commands+=(git curl jq rg flatpak python3)

if [[ "$PROFILE" == "gaming" ]]; then
  intended_commands+=(node go cargo ruby nvim sqlite3 mangohud)
elif [[ "$PROFILE" == "ai-dev" ]]; then
  intended_commands+=(node go cargo ruby nvim sqlite3)
else
  intended_commands+=(sqlite3)
fi

# Browsers: acceptable as native binary OR Flatpak app.
declare -a browser_commands=(firefox chromium google-chrome)
declare -a browser_flatpaks=(org.mozilla.firefox com.google.Chrome)

echo "=== Installed vs Intended Comparison ==="
echo "Host: ${HOST_NAME}"
echo "Profile: ${PROFILE}"
echo "Target: ${TARGET}"
echo

echo "[1/3] Critical command comparison"
for cmd in "${intended_commands[@]}"; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '  ✓ %s -> %s\n' "$cmd" "$(command -v "$cmd")"
  else
    printf '  ✗ %s -> NOT FOUND\n' "$cmd"
    missing_commands+=("$cmd")
  fi
done

echo
echo "[2/3] Browser availability comparison"
browser_ok=false
for bcmd in "${browser_commands[@]}"; do
  if command -v "$bcmd" >/dev/null 2>&1; then
    printf '  ✓ browser binary available: %s -> %s\n' "$bcmd" "$(command -v "$bcmd")"
    browser_ok=true
  fi
done

if command -v flatpak >/dev/null 2>&1; then
  mapfile -t installed_flatpaks < <(flatpak list --app --columns=application 2>/dev/null || true)
  for app in "${browser_flatpaks[@]}"; do
    if printf '%s\n' "${installed_flatpaks[@]}" | grep -Fxq "$app"; then
      printf '  ✓ browser flatpak available: %s\n' "$app"
      browser_ok=true
    else
      printf '  ✗ browser flatpak missing: %s\n' "$app"
      missing_flatpaks+=("$app")
    fi
  done
else
  echo "  ✗ flatpak command not found (cannot verify/install browser flatpaks)"
  missing_commands+=(flatpak)
  missing_flatpaks+=("${browser_flatpaks[@]}")
fi

if [[ "$browser_ok" == false ]]; then
  echo "  ✗ no browser detected via binaries or Flatpak apps"
fi

echo
echo "[3/3] Declarative target check"
if command -v nix >/dev/null 2>&1; then
  eval_output="$(nix eval --raw "${FLAKE_REF}#nixosConfigurations.\"${TARGET}\".config.mySystem.profile" 2>&1 || true)"
  if [[ -n "$eval_output" && "$eval_output" != *"error:"* ]]; then
    :
  fi

  if [[ "$eval_output" == "$PROFILE" ]]; then
    echo "  ✓ flake target resolves: ${TARGET}"
  elif [[ "$eval_output" == *"daemon-socket"* ]] || [[ "$eval_output" == *"Operation not permitted"* ]]; then
    echo "  ⚠ flake target eval skipped in restricted runtime (daemon socket unavailable)"
  else
    echo "  ✗ flake target does not resolve: ${TARGET}"
    echo "    (target/profile mismatch or eval issue)"
    [[ -n "$eval_output" ]] && echo "    nix eval output: ${eval_output}"
  fi
else
  echo "  ✗ nix command not found"
fi

echo
if [[ ${#missing_commands[@]} -eq 0 && ${#missing_flatpaks[@]} -eq 0 ]]; then
  echo "Result: PASS (critical intended tools/apps are available)"
  exit 0
fi

echo "Result: FAIL"
if [[ ${#missing_commands[@]} -gt 0 ]]; then
  echo "Missing commands: ${missing_commands[*]}"
fi
if [[ ${#missing_flatpaks[@]} -gt 0 ]]; then
  echo "Missing browser Flatpaks: ${missing_flatpaks[*]}"
fi
exit 1
