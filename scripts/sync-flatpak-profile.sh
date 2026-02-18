#!/usr/bin/env bash
#
# Sync Flatpak apps from declarative flake profile data.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FLAKE_REF="path:${REPO_ROOT}"
TARGET=""
NON_INTERACTIVE=true

usage() {
  cat <<'EOF'
Usage: ./scripts/sync-flatpak-profile.sh --target <host-profile> [options]

Options:
  --target NAME      nixos target name (<host>-<profile>) [required]
  --flake-ref REF    flake reference (default: path:<repo-root>)
  --interactive      allow interactive flatpak prompts
  -h, --help         show this help
EOF
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

if ! command -v flatpak >/dev/null 2>&1; then
  echo "Flatpak is not installed; skipping profile sync."
  exit 0
fi

if ! command -v nix >/dev/null 2>&1; then
  echo "Nix CLI not found; cannot resolve profileData.flatpakApps."
  exit 1
fi

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
mapfile -t installed_apps < <(flatpak list --app --columns=application 2>/dev/null || true)

ensure_flathub_remote() {
  # Keep remote scope aligned with install scope (`flatpak install --user ...`).
  local remote_url="https://dl.flathub.org/repo/flathub.flatpakrepo"
  local refs=""

  if ! flatpak remotes --user --columns=name 2>/dev/null | grep -Fxq "flathub"; then
    echo "Adding user flathub remote..."
    flatpak remote-add --user --if-not-exists flathub "$remote_url"
  fi

  refs="$(flatpak remote-ls --user flathub --app --columns=application 2>/dev/null || true)"
  if [[ -n "$refs" ]]; then
    return 0
  fi

  echo "User flathub remote has no refs; repairing user remote metadata..."
  flatpak remote-delete --user flathub >/dev/null 2>&1 || true
  flatpak remote-add --user --if-not-exists flathub "$remote_url"

  refs="$(flatpak remote-ls --user flathub --app --columns=application 2>/dev/null || true)"
  if [[ -z "$refs" ]]; then
    echo "Unable to refresh user flathub metadata; skipping app installation." >&2
    return 1
  fi

  return 0
}

if ! ensure_flathub_remote; then
  exit 1
fi

install_flatpak_app() {
  local app="$1"
  local output=""

  if output="$("${install_cmd[@]}" "$app" 2>&1)"; then
    printf '%s\n' "$output"
    return 0
  fi

  printf '%s\n' "$output" >&2
  if printf '%s\n' "$output" | grep -Fq "No remote refs found for"; then
    echo "    ↻ retrying after flathub remote repair" >&2
    if ensure_flathub_remote && output="$("${install_cmd[@]}" "$app" 2>&1)"; then
      printf '%s\n' "$output"
      return 0
    fi
    printf '%s\n' "$output" >&2
  fi

  return 1
}

declare -a install_cmd=(flatpak install --user flathub)
if [[ "$NON_INTERACTIVE" == true ]]; then
  install_cmd=(flatpak --noninteractive --assumeyes install --user flathub)
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

echo "Flatpak profile sync complete."
