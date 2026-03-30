#!/usr/bin/env bash
#
# Sync Flatpak apps from declarative flake profile data.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

FLAKE_REF="path:${REPO_ROOT}"
TARGET=""
NON_INTERACTIVE=true
INSTALL_SCOPE="system"
FLATHUB_REMOTE_NAME="${FLATHUB_REMOTE_NAME:-flathub}"
FLATHUB_REMOTE_URL="${FLATHUB_REMOTE_URL:-https://dl.flathub.org/repo/flathub.flatpakrepo}"
FLATHUB_REMOTE_FALLBACK_URL="${FLATHUB_REMOTE_FALLBACK_URL:-https://flathub.org/repo/flathub.flatpakrepo}"

usage() {
  cat <<'USAGE'
Usage: ./scripts/data/sync-flatpak-profile.sh --target <host-profile> [options]

Options:
  --target NAME      nixos target name (<host>-<profile>) [required]
  --flake-ref REF    flake reference (default: path:<repo-root>)
  --interactive      allow interactive flatpak prompts
  --scope SCOPE      install scope: system|user (default: user)
  -h, --help         show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:?missing value for --target}"
      shift 2
      ;;
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --interactive)
      NON_INTERACTIVE=false
      shift
      ;;
    --scope)
      INSTALL_SCOPE="${2:?missing value for --scope}"
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

[[ -n "$TARGET" ]] || {
  echo "ERROR: --target is required" >&2
  usage
  exit 1
}

case "$INSTALL_SCOPE" in
  system|user) ;;
  *)
    echo "ERROR: --scope must be 'system' or 'user'" >&2
    exit 1
    ;;
esac

if ! command -v flatpak >/dev/null 2>&1; then
  echo "Flatpak is not installed; skipping profile sync."
  exit 0
fi

if ! command -v nix >/dev/null 2>&1; then
  echo "Nix CLI not found; cannot resolve profileData.flatpakApps."
  exit 1
fi

FLATPAK_CMD=(flatpak)
if [[ "$INSTALL_SCOPE" == "system" && "$EUID" -ne 0 ]]; then
  if ! command -v sudo >/dev/null 2>&1; then
    echo "ERROR: --scope system requires sudo when not root." >&2
    exit 1
  fi
  if [[ "$NON_INTERACTIVE" == true ]]; then
    FLATPAK_CMD=(sudo -n flatpak)
  else
    FLATPAK_CMD=(sudo flatpak)
  fi
fi

flatpak_run() {
  "${FLATPAK_CMD[@]}" "$@"
}

is_network_resolution_failure() {
  local output="${1:-}"
  [[ "$output" == *"Could not resolve hostname"* ]] \
    || [[ "$output" == *"Temporary failure in name resolution"* ]] \
    || [[ "$output" == *"Name or service not known"* ]] \
    || [[ "$output" == *"No route to host"* ]] \
    || [[ "$output" == *"Could not connect"* ]] \
    || [[ "$output" == *"Network is unreachable"* ]]
}

ensure_xdg_flatpak_exports_in_path() {
  local user_exports="${HOME}/.local/share/flatpak/exports/share"
  local system_exports="/var/lib/flatpak/exports/share"

  export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"

  case ":${XDG_DATA_DIRS:-}": in
    *":${user_exports}:"*) ;;
    *) XDG_DATA_DIRS="${user_exports}${XDG_DATA_DIRS:+:${XDG_DATA_DIRS}}" ;;
  esac

  case ":${XDG_DATA_DIRS:-}": in
    *":${system_exports}:"*) ;;
    *) XDG_DATA_DIRS="${XDG_DATA_DIRS:+${XDG_DATA_DIRS}:}${system_exports}" ;;
  esac

  export XDG_DATA_DIRS
}

ensure_xdg_flatpak_exports_in_path

echo "Resolving Flatpak app list from ${FLAKE_REF}#nixosConfigurations.${TARGET}..."

if ! apps_raw="$(nix eval --raw \
  --apply 'apps: builtins.concatStringsSep "\n" apps' \
  "${FLAKE_REF}#nixosConfigurations.\"${TARGET}\".config.mySystem.profileData.flatpakApps" 2>&1)"; then
  echo "Failed to resolve declarative Flatpak apps for ${TARGET}." >&2
  echo "$apps_raw" >&2
  exit 1
fi

if [[ -z "$apps_raw" ]]; then
  echo "No declarative Flatpak apps found for target ${TARGET}; nothing to do."
  exit 0
fi

mapfile -t desired_apps <<<"$apps_raw"
mapfile -t installed_apps < <(flatpak_run list --"${INSTALL_SCOPE}" --app --columns=application 2>/dev/null || true)

ensure_flathub_remote() {
  local refs=""
  local output=""
  local remote_url=""
  local -a remote_urls=("$FLATHUB_REMOTE_URL" "$FLATHUB_REMOTE_FALLBACK_URL")

  if ! flatpak_run remotes --"${INSTALL_SCOPE}" --columns=name 2>/dev/null | grep -Fxq "$FLATHUB_REMOTE_NAME"; then
    echo "Adding ${INSTALL_SCOPE} ${FLATHUB_REMOTE_NAME} remote..."
    for remote_url in "${remote_urls[@]}"; do
      [[ -n "$remote_url" ]] || continue
      if output="$(flatpak_run remote-add --"${INSTALL_SCOPE}" --if-not-exists "$FLATHUB_REMOTE_NAME" "$remote_url" 2>&1)"; then
        break
      fi
      printf '%s\n' "$output" >&2
      if ! is_network_resolution_failure "$output"; then
        return 1
      fi
    done
  fi

  refs="$(flatpak_run remote-ls --"${INSTALL_SCOPE}" "$FLATHUB_REMOTE_NAME" --app --columns=application 2>/dev/null || true)"
  if [[ -n "$refs" ]]; then
    return 0
  fi

  echo "${INSTALL_SCOPE^} ${FLATHUB_REMOTE_NAME} remote has no refs; repairing metadata..."
  flatpak_run remote-delete --"${INSTALL_SCOPE}" "$FLATHUB_REMOTE_NAME" >/dev/null 2>&1 || true
  for remote_url in "${remote_urls[@]}"; do
    [[ -n "$remote_url" ]] || continue
    if output="$(flatpak_run remote-add --"${INSTALL_SCOPE}" --if-not-exists "$FLATHUB_REMOTE_NAME" "$remote_url" 2>&1)"; then
      break
    fi
    printf '%s\n' "$output" >&2
    if ! is_network_resolution_failure "$output"; then
      return 1
    fi
  done

  refs="$(flatpak_run remote-ls --"${INSTALL_SCOPE}" "$FLATHUB_REMOTE_NAME" --app --columns=application 2>/dev/null || true)"
  if [[ -z "$refs" ]]; then
    echo "Unable to refresh ${INSTALL_SCOPE} ${FLATHUB_REMOTE_NAME} metadata; skipping app installation." >&2
    return 2
  fi

  return 0
}

if ! ensure_flathub_remote; then
  rc=$?
  if [[ "$rc" -eq 2 ]]; then
    exit 0
  fi
  exit "$rc"
fi

install_flatpak_app() {
  local app="$1"
  local output=""

  if output="$(${install_cmd[@]} "$app" 2>&1)"; then
    printf '%s\n' "$output"
    return 0
  fi

  printf '%s\n' "$output" >&2
  if printf '%s\n' "$output" | grep -Fq "No remote refs found for"; then
    echo "    ↻ retrying after flathub remote repair" >&2
    if ensure_flathub_remote && output="$(${install_cmd[@]} "$app" 2>&1)"; then
      printf '%s\n' "$output"
      return 0
    fi
    printf '%s\n' "$output" >&2
  fi

  return 1
}

declare -a install_cmd=("${FLATPAK_CMD[@]}" install --"${INSTALL_SCOPE}" "$FLATHUB_REMOTE_NAME")
if [[ "$NON_INTERACTIVE" == true ]]; then
  install_cmd=("${FLATPAK_CMD[@]}" --noninteractive --assumeyes install --"${INSTALL_SCOPE}" "$FLATHUB_REMOTE_NAME")
fi

missing=0
for app in "${desired_apps[@]}"; do
  [[ -z "$app" ]] && continue
  if printf '%s\n' "${installed_apps[@]}" | grep -Fxq "$app"; then
    echo "  ✓ $app"
    continue
  fi

  echo "  → installing $app"
  if install_flatpak_app "$app"; then
    echo "    ✓ installed $app"
  else
    echo "    ✗ failed to install $app"
    missing=$((missing + 1))
  fi
done

if [[ "$missing" -gt 0 ]]; then
  echo "Flatpak profile sync finished with ${missing} failed app install(s)."
  exit 1
fi

# ── Dedup: remove user-scope copies of apps now installed system-wide ────────
# Only runs when installing at system scope. Prevents the same app appearing
# twice in launchers (once from --user exports, once from --system exports).
if [[ "$INSTALL_SCOPE" == "system" ]]; then
  mapfile -t user_installed < <(flatpak list --user --app --columns=application 2>/dev/null || true)
  if [[ ${#user_installed[@]} -gt 0 ]]; then
    for app in "${desired_apps[@]}"; do
      [[ -z "$app" ]] && continue
      if printf '%s\n' "${user_installed[@]}" | grep -Fxq "$app"; then
        echo "  ↳ removing user-scope duplicate: $app"
        flatpak --noninteractive --assumeyes uninstall --user "$app" 2>/dev/null || true
      fi
    done
  fi
fi

echo "Flatpak profile sync complete."
