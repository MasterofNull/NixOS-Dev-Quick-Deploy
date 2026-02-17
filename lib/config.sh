#!/usr/bin/env bash
#
# Configuration Generation
# Purpose: Generate NixOS and home-manager configurations from templates
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/nixos.sh → derive_system_release_version(), normalize_channel_name()
#
# Required Variables:
#   - HM_CONFIG_DIR → Home manager config directory
#   - HOME_MANAGER_FILE → Path to home.nix
#   - FLAKE_FILE → Path to flake.nix
#   - SYSTEM_CONFIG_FILE → Path to configuration.nix
#   - GPU_TYPE → Detected GPU type
#
# Exports:
#   - generate_nixos_system_config() → Generate system configuration
#   - create_home_manager_config() → Generate home-manager configuration
#   - validate_system_build_stage() → Validate configuration with dry-build
#
# ============================================================================

# ============================================================================
# Internal helpers
# ============================================================================

run_git_safe() {
    if command -v git >/dev/null 2>&1; then
        git "$@"
        return
    fi

    if command -v nix >/dev/null 2>&1; then
        nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#git --command git "$@"
        return
    fi

    return 127
}

# Replace placeholder tokens in template files using a Python helper to safely
# handle multi-line replacements. The helper is used extensively when writing
# templates/home.nix and templates/configuration.nix.
replace_placeholder() {
    local target_file="$1"
    local placeholder="$2"
    local replacement="$3"

    if [[ -z "$target_file" || -z "$placeholder" ]]; then
        return 1
    fi

    if [[ ! -f "$target_file" ]]; then
        print_error "Template file not found for replacement: $target_file"
        return 1
    fi

    if ! grep -Fq "$placeholder" "$target_file"; then
        return 0
    fi

    local python_runner="run_python"
    if ! declare -F run_python >/dev/null 2>&1; then
        python_runner="python3"
    fi

    PLACEHOLDER_VALUE="$replacement" "$python_runner" - "$target_file" "$placeholder" <<'PY'
import pathlib
import sys
import os

target = pathlib.Path(sys.argv[1])
placeholder = sys.argv[2]
value = os.environ.get("PLACEHOLDER_VALUE", "")

text = target.read_text(encoding="utf-8")
text = text.replace(placeholder, value)
target.write_text(text, encoding="utf-8")
PY
}

backup_generated_file() {
    # Backup an existing generated file before replacement.
    # Args: $1 = file path, $2 = friendly label, $3 = backup directory,
    #       $4 = timestamp suffix
    # Returns:
    #   0 → backup succeeded
    #   1 → backup attempted but failed
    #   2 → file did not exist (no backup needed)
    local source_path="$1"
    local label="${2:-}"
    local backup_dir="${3:-$HM_BACKUP_DIR}"
    local timestamp="${4:-$(date +%Y%m%d_%H%M%S)}"

    if [[ -z "$source_path" || -z "$backup_dir" ]]; then
        return 1
    fi

    if [[ ! -f "$source_path" ]]; then
        return 2
    fi

    if ! safe_mkdir "$backup_dir"; then
        print_warning "Could not create backup directory: $backup_dir"
        return 1
    fi

    local base_name
    base_name=$(basename "$source_path")
    local backup_target="$backup_dir/${base_name}.backup.$timestamp"

    if safe_copy_file_silent "$source_path" "$backup_target"; then
        local display_label="${label:-$base_name}"
        print_success "Backed up ${display_label}"
        return 0
    fi

    local display_label="${label:-$base_name}"
    print_warning "Failed to back up ${display_label}"
    return 1
}

sync_support_module() {
    # Ensure support modules (e.g., python-overrides.nix) are copied from
    # templates, backing up pre-existing versions only when they differ.
    # Args: $1 = module filename, $2 = source directory,
    #       $3 = destination directory, $4 = backup dir, $5 = timestamp
    local module_name="$1"
    local template_dir="${2:-$SCRIPT_DIR/templates}"
    local destination_dir="${3:-$HM_CONFIG_DIR}"
    local backup_dir="${4:-$HM_BACKUP_DIR}"
    local timestamp="${5:-$(date +%Y%m%d_%H%M%S)}"

    if [[ -z "$module_name" ]]; then
        print_error "sync_support_module: module name required"
        return 1
    fi

    local module_source="$template_dir/$module_name"
    local module_destination="$destination_dir/$module_name"

    if [[ ! -f "$module_source" ]]; then
        print_error "Required template missing: $module_source"
        return 1
    fi

    local needs_copy=true
    if [[ -f "$module_destination" ]]; then
        if cmp -s "$module_source" "$module_destination" 2>/dev/null; then
            needs_copy=false
        else
            backup_generated_file "$module_destination" "$module_name" "$backup_dir" "$timestamp" || true
        fi
    fi

    if [[ "$needs_copy" == false ]]; then
        print_success "$module_name already up to date"
        return 0
    fi

    if ! safe_copy_file "$module_source" "$module_destination"; then
        print_error "Failed to install $module_name into $destination_dir"
        return 1
    fi

    safe_chown_user_dir "$module_destination" || true
    print_success "Installed $module_name"
    return 0
}

DEFAULT_COSMIC_BLACKLIST_ENTRIES=(
    "cosmic-app-library"
    "cosmic-app-list"
    "cosmic-applet-a11y"
    "cosmic-applet-audio"
    "cosmic-applet-battery"
    "cosmic-applet-bluetooth"
    "cosmic-applet-input-sources"
    "cosmic-applet-minimize"
    "cosmic-applet-network"
    "cosmic-applet-notifications"
    "cosmic-applet-power"
    "cosmic-applet-status-area"
    "cosmic-applet-tiling"
    "cosmic-applet-time"
    "cosmic-applet-workspaces"
    "cosmic-applets"
    "cosmic-bg"
    "cosmic-comp"
    "cosmic-edit"
    "cosmic-files"
    "cosmic-files-applet"
    "cosmic-greeter"
    "cosmic-greeter-daemon"
    "cosmic-greeter-start"
    "cosmic-idle"
    "cosmic-initial-setup"
    "cosmic-launcher"
    "cosmic-notification-daemon"
    "cosmic-notifications"
    "cosmic-osd"
    "cosmic-panel"
    "cosmic-panel-button"
    "cosmic-player"
    "cosmic-randr"
    "cosmic-screenshot"
    "cosmic-session"
    "cosmic-settings"
    "cosmic-settings-daemon"
    "cosmic-store"
    "cosmic-term"
    "cosmic-terminal"
    "cosmic-text"
    "cosmic-workspaces"
)

discover_cosmic_blacklist_entries() {
    local -a entries=()
    local -a search_dirs=(
        "/run/current-system/sw/bin"
    )

    local dir path
    for dir in "${search_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            continue
        fi
        while IFS= read -r -d '' path; do
            local name
            name=$(basename "$path")
            [[ -n "$name" ]] || continue
            entries+=("$name")
        done < <(find "$dir" -maxdepth 1 -type f -name 'cosmic-*' -print0 2>/dev/null || true)
    done

    if (( ${#entries[@]} == 0 )); then
        printf '%s\n' "${DEFAULT_COSMIC_BLACKLIST_ENTRIES[@]}"
        return 0
    fi

    printf '%s\n' "${entries[@]}" | LC_ALL=C sort -u
}

render_cosmic_blacklist_block() {
    local -a entries=()
    if mapfile -t entries < <(discover_cosmic_blacklist_entries); then
        :
    fi

    if (( ${#entries[@]} == 0 )); then
        entries=("${DEFAULT_COSMIC_BLACKLIST_ENTRIES[@]}")
    fi

    local formatted=""
    local entry
    for entry in "${entries[@]}"; do
        printf -v formatted '%s    "%s"\n' "$formatted" "$entry"
    done

    printf '%s' "$formatted"
}

# Resolve MangoHud profile preferences once so system/home configs stay in sync.
# Preference file path defined in config/variables.sh:129.
# On first run (no preference file exists), the default "desktop" profile will be
# persisted to ensure MangoHud only overlays in the mangoapp window, not on COSMIC
# applets or system windows.
resolve_mangohud_preferences() {
    local default_profile="desktop"

    local mangohud_profile="$default_profile"
    local mangohud_profile_origin="defaults"
    local mangohud_profile_candidate=""

    if [[ -n "${MANGOHUD_PROFILE_OVERRIDE:-}" ]]; then
        mangohud_profile_candidate="$MANGOHUD_PROFILE_OVERRIDE"
        mangohud_profile_origin="environment override"
    elif [[ -n "${MANGOHUD_PROFILE_PREFERENCE_FILE:-}" && -f "$MANGOHUD_PROFILE_PREFERENCE_FILE" ]]; then
        mangohud_profile_candidate=$(awk -F'=' '/^MANGOHUD_PROFILE=/{print $2}' "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
        mangohud_profile_origin="preference file"
    fi

    if [[ -n "$mangohud_profile_candidate" ]]; then
        case "$mangohud_profile_candidate" in
            disabled|light|full|desktop|desktop-hybrid)
                mangohud_profile="$mangohud_profile_candidate"
                ;;
            *)
                print_warning "Unsupported MangoHud profile '$mangohud_profile_candidate'; expected disabled, light, full, desktop, or desktop-hybrid. Using default profile '$mangohud_profile'."
                ;;
        esac
    fi

    # Persist the default profile to preference file on first run (if no override is set)
    if [[ -z "${MANGOHUD_PROFILE_OVERRIDE:-}" && -n "${MANGOHUD_PROFILE_PREFERENCE_FILE:-}" ]]; then
        if [[ ! -f "$MANGOHUD_PROFILE_PREFERENCE_FILE" ]]; then
            mkdir -p "$(dirname "$MANGOHUD_PROFILE_PREFERENCE_FILE")" 2>/dev/null || true
            printf 'MANGOHUD_PROFILE=%s\n' "$mangohud_profile" > "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null || true
            chmod 600 "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null || true
        fi
    fi

    local mangohud_desktop_window_mode=false
    local mangohud_injects_into_apps=true
    case "$mangohud_profile" in
        disabled)
            mangohud_injects_into_apps=false
            ;;
        desktop)
            mangohud_desktop_window_mode=true
            mangohud_injects_into_apps=false
            ;;
        desktop-hybrid)
            mangohud_desktop_window_mode=true
            ;;
    esac

    RESOLVED_MANGOHUD_PROFILE="$mangohud_profile"
    RESOLVED_MANGOHUD_PROFILE_ORIGIN="$mangohud_profile_origin"
    RESOLVED_MANGOHUD_DESKTOP_MODE="$mangohud_desktop_window_mode"
    RESOLVED_MANGOHUD_INJECTS="$mangohud_injects_into_apps"
}

# Build the MangoHud preset/configuration block shared by system and home
# templates. The generated string is spliced into both template files via
# replace_placeholder to keep behaviour consistent across system/home configs.
generate_mangohud_nix_definitions() {
    cat <<'EOF'
  glfMangoHudCosmicBlacklist = [
__COSMIC_BLACKLIST_ENTRIES__
  ];
  glfMangoHudBlacklistEntry =
    if glfMangoHudCosmicBlacklist == [] then
      ""
    else
      "blacklist=${lib.concatStringsSep "," glfMangoHudCosmicBlacklist}";
  glfMangoHudCommonEntries =
    lib.optional (glfMangoHudBlacklistEntry != "") glfMangoHudBlacklistEntry;
  glfMangoHudPresets = {
    disabled = [ ];
    light =
      # Layout: vertical, one metric per line with labels
      [
      "control=mangohud"
      "legacy_layout=0"
      "vertical"
      "background_alpha=0"
      "gpu_stats"
      "gpu_power"
      "gpu_temp"
      "cpu_stats"
      "cpu_load"
      "cpu_temp"
      "core_load"
      "ram"
      "vram"
      "fps"
      "fps_metrics=AVG,0.001"
      "frametime"
      "font_scale=1.05"
      ]
      ++ glfMangoHudCommonEntries;
    full =
      [
      "control=mangohud"
      "legacy_layout=0"
      "vertical"
      "background_alpha=0"
      "gpu_stats"
      "gpu_power"
      "gpu_temp"
      "cpu_stats"
      "cpu_load"
      "cpu_temp"
      "core_load"
      "ram"
      "vram"
      "fps"
      "fps_metrics=AVG,0.001"
      "frametime"
      "refresh_rate"
      "resolution"
      "vulkan_driver"
      "wine"
      ]
      ++ glfMangoHudCommonEntries;
    desktop =
      # Note: desktop mode uses no_display=1 to prevent MangoHud from overlaying
      # any applications. Stats are only visible in the mangoapp desktop window.
      # Layout: vertical, one metric per line with labels in order:
      # GPU → Power → CPU → CPU Load → (enumerated cores) → RAM → VRAM → FPS → AVG → Frametime
      [
      "control=mangohud"
      "legacy_layout=0"
      "vertical"
      "background_alpha=0"
      "alpha=0.9"
      "font_scale=1.1"
      "position=top-left"
      "offset_x=32"
      "offset_y=32"
      "hud_no_margin=1"
      "no_display=1"
      "gpu_stats"
      "gpu_power"
      "gpu_temp"
      "cpu_stats"
      "cpu_load"
      "cpu_temp"
      "core_load"
      "ram"
      "vram"
      "fps"
      "fps_metrics=AVG,0.001"
      "frametime"
      ]
      ++ glfMangoHudCommonEntries;
    "desktop-hybrid" =
      # Note: desktop-hybrid intentionally omits no_display=1 to allow
      # MangoHud overlays in games/apps while also running mangoapp.
      # The blacklist (glfMangoHudCommonEntries) prevents overlays on COSMIC apps.
      # Layout: vertical, one metric per line with labels in order:
      # GPU → Power → CPU → CPU Load → (enumerated cores) → RAM → VRAM → FPS → AVG → Frametime
      [
      "control=mangohud"
      "legacy_layout=0"
      "vertical"
      "background_alpha=0"
      "alpha=0.9"
      "font_scale=1.1"
      "position=top-left"
      "offset_x=32"
      "offset_y=32"
      "hud_no_margin=1"
      "gpu_stats"
      "gpu_power"
      "gpu_temp"
      "cpu_stats"
      "cpu_load"
      "cpu_temp"
      "core_load"
      "ram"
      "vram"
      "fps"
      "fps_metrics=AVG,0.001"
      "frametime"
      ]
      ++ glfMangoHudCommonEntries;
  };
  glfMangoHudProfile = "__MANGOHUD_PROFILE__";
  glfMangoHudEntries =
    lib.attrByPath [ glfMangoHudProfile ] [] glfMangoHudPresets;
  glfMangoHudHasEntries = glfMangoHudEntries != [];
  glfMangoHudConfigFileContents =
    if !glfMangoHudHasEntries then
      ""
    else
      lib.concatStringsSep "\n" glfMangoHudEntries + "\n";
  glfMangoHudDesktopMode =
    glfMangoHudProfile == "desktop" || glfMangoHudProfile == "desktop-hybrid";
  glfMangoHudInjectsIntoApps =
    glfMangoHudHasEntries && glfMangoHudProfile != "desktop";
EOF
}

# Cache for resolved MangoHud state so subsequent steps can reuse it.
RESOLVED_MANGOHUD_PROFILE=""
RESOLVED_MANGOHUD_PROFILE_ORIGIN="defaults"
RESOLVED_MANGOHUD_DESKTOP_MODE=false
RESOLVED_MANGOHUD_INJECTS=true

# Binary cache helpers keep runtime tooling and rendered configuration aligned
# across NixOS + Home Manager outputs.
get_binary_cache_sources() {
    local -a caches=(
        "https://cache.nixos.org"
        "https://nix-community.cachix.org"
        "https://devenv.cachix.org"
    )

    if [[ "${GPU_TYPE:-}" == "nvidia" ]]; then
        caches+=("https://cuda-maintainers.cachix.org")
    fi

    if (( ${#ADDITIONAL_BINARY_CACHES[@]} > 0 )); then
        caches+=("${ADDITIONAL_BINARY_CACHES[@]}")
    fi

    printf '%s\n' "${caches[@]}"
}

get_binary_cache_public_keys() {
    local -a keys=(
        "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
        "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
        "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
    )

    if [[ "${GPU_TYPE:-}" == "nvidia" ]]; then
        keys+=("cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E=")
    fi

    if (( ${#ADDITIONAL_BINARY_CACHE_KEYS[@]} > 0 )); then
        keys+=("${ADDITIONAL_BINARY_CACHE_KEYS[@]}")
    fi

    printf '%s\n' "${keys[@]}"
}

format_kernel_preference_string() {
    # Helper to render the configured kernel preference order using arrows.
    # Args: $@ → kernel attribute names in preference order.
    if (( $# == 0 )); then
        echo ""
        return
    fi

    local joined=""
    local first=true

    for kernel in "$@"; do
        if $first; then
            joined="$kernel"
            first=false
        else
            joined+=$' → '
            joined+="$kernel"
        fi
    done

    printf '%s' "$joined"
}

append_unique_value() {
    local -n target_array="$1"
    local value="$2"

    if [[ -z "$value" ]]; then
        return 0
    fi

    local existing
    for existing in "${target_array[@]}"; do
        if [[ "$existing" == "$value" ]]; then
            return 0
        fi
    done

    target_array+=("$value")
}

# Convenience wrappers for the arrays exported in config/variables.sh. These
# keep call sites tidy when auxiliary modules register extra cache endpoints or
# remote builders.
register_additional_binary_cache() {
    append_unique_value ADDITIONAL_BINARY_CACHES "$1"
}

register_additional_binary_cache_key() {
    append_unique_value ADDITIONAL_BINARY_CACHE_KEYS "$1"
}

register_remote_builder_spec() {
    append_unique_value REMOTE_BUILDER_SPECS "$1"
    if (( ${#REMOTE_BUILDER_SPECS[@]} > 0 )); then
        REMOTE_BUILDERS_ENABLED=true
    fi
}

# Sanitize a generated hardware-configuration.nix by removing:
#   1. Transient Podman/overlay fileSystems entries (prevents nixos-rebuild from
#      trying to mount ephemeral runtime paths, which breaks local-fs.target).
#   2. Stale UUID-based fileSystems entries whose /dev/disk/by-uuid/ symlink no
#      longer exists on the running system (prevents systemd-fsck@ failures at
#      boot when disks are removed or repartitioned).
# Sanitize HM hardware config (defaults defined in config/variables.sh:589) so
# nixos-rebuild ignores transient container mounts added by Podman.
sanitize_hardware_configuration() {
    local config_file="${1:-${HARDWARE_CONFIG_FILE:-}}"

    if [[ -z "$config_file" || ! -f "$config_file" ]]; then
        return 0
    fi

    local -a removed_mounts=()
    if ! mapfile -t removed_mounts < <(
        python3 - "$config_file" <<'PY'
import pathlib
import re
import sys

config_path = pathlib.Path(sys.argv[1])
text = config_path.read_text(encoding="utf-8")
lines = text.splitlines()
endswith_newline = text.endswith("\n")

# Transient container mount prefixes to always drop
container_prefixes = (
    "/var/lib/containers/storage/overlay",
    "/var/lib/containers/storage/overlay-containers",
)

# Regex to extract a by-uuid device path from a fileSystems block
uuid_device_re = re.compile(r'device\s*=\s*"(/dev/disk/by-uuid/[^"]+)"')

result = []
removed = []
i = 0
total = len(lines)

while i < total:
    line = lines[i]
    stripped = line.lstrip()
    if stripped.startswith('fileSystems."'):
        try:
            mount = stripped.split('fileSystems."', 1)[1].split('"', 1)[0]
        except IndexError:
            result.append(line)
            i += 1
            continue

        block = [line]
        i += 1
        while i < total:
            block.append(lines[i])
            if lines[i].strip() == '};':
                i += 1
                break
            i += 1
        else:
            # Unbalanced block; keep original text to avoid corruption.
            result.extend(block)
            continue

        # Check 1: transient container overlay mounts
        should_drop = any(
            mount == prefix or mount.startswith(f"{prefix}/")
            for prefix in container_prefixes
        )

        # Check 2: stale UUID-based device references
        if not should_drop:
            block_text = "\n".join(block)
            uuid_match = uuid_device_re.search(block_text)
            if uuid_match:
                device_path = pathlib.Path(uuid_match.group(1))
                if not device_path.exists():
                    should_drop = True

        if should_drop:
            removed.append(mount)
            continue

        result.extend(block)
        continue

    result.append(line)
    i += 1

new_text = "\n".join(result)
if endswith_newline and (new_text or not result):
    new_text += "\n"

if new_text != text:
    config_path.write_text(new_text, encoding="utf-8")

for mount in removed:
    print(mount)
PY
    ); then
        print_warning "Failed to sanitize hardware-configuration.nix; rerun Phase 3 before switching."
        return 1
    fi

    if (( ${#removed_mounts[@]} > 0 )); then
        print_info "Removed stale or transient mounts from $(basename "$config_file"):"
        local mount_point
        for mount_point in "${removed_mounts[@]}"; do
            print_info "  - $mount_point"
        done
    fi

    return 0
}

# ==========================================================================
# Podman rootless storage helper
# ==========================================================================

# Generate the services.podman.settings.storage override that Home Manager
# injects. Depends on PRIMARY_HOME (config/variables.sh:450) so rootless Podman
# data stays inside the user's home directory.
build_rootless_podman_storage_block() {
    local default_driver="${DEFAULT_PODMAN_STORAGE_DRIVER:-vfs}"
    local system_driver="${PODMAN_STORAGE_DRIVER:-$default_driver}"

    case "$default_driver" in
        vfs|btrfs|zfs)
            ;;
        *)
            print_warning "DEFAULT_PODMAN_STORAGE_DRIVER=${default_driver} unsupported; falling back to vfs."
            default_driver="vfs"
            ;;
    esac

    if [[ "${PODMAN_STORAGE_DETECTION_RUN:-false}" != true ]] \
        && declare -F detect_container_storage_backend >/dev/null 2>&1; then
        detect_container_storage_backend
        system_driver="${PODMAN_STORAGE_DRIVER:-$system_driver}"
    fi

    if [[ -z "$system_driver" ]]; then
        system_driver="$default_driver"
    fi

    case "$system_driver" in
        vfs|btrfs|zfs)
            ;;
        *)
            print_warning "PODMAN_STORAGE_DRIVER=${system_driver} unsupported; using ${default_driver} for rootless storage."
            system_driver="$default_driver"
            ;;
    esac

    local rootless_home="${PRIMARY_HOME:-$HOME}"
    local home_fs
    home_fs=$(get_filesystem_type_for_path "$rootless_home" "unknown")
    local home_fs_display="${home_fs:-unknown}"

    local driver_choice="$system_driver"
    local fallback_driver="$default_driver"
    local comment=""

    case "$system_driver" in
        btrfs)
            if [[ "$home_fs" == "btrfs" ]]; then
                driver_choice="btrfs"
                comment="Home directory resides on btrfs; matching rootless Podman storage driver."
            else
                driver_choice="$fallback_driver"
                if [[ "$home_fs_display" == "unknown" ]]; then
                    comment="System Podman uses btrfs; falling back to ${fallback_driver} for rootless compatibility on an undetected home filesystem."
                else
                    comment="System Podman uses btrfs but ${rootless_home} resides on ${home_fs_display}; using ${fallback_driver} driver for rootless compatibility."
                fi
            fi
            ;;
        zfs|zfs_member)
            driver_choice="$fallback_driver"
            if [[ "$home_fs" == "zfs" || "$home_fs" == "zfs_member" ]]; then
                comment="Home directory resides on ZFS; using ${driver_choice} driver for rootless compatibility."
            else
                if [[ "$home_fs_display" == "unknown" ]]; then
                    comment="System Podman uses ZFS but the home directory filesystem could not be detected; using ${driver_choice} driver for rootless compatibility."
                else
                    comment="System Podman uses ZFS but ${rootless_home} resides on ${home_fs_display}; using ${driver_choice} driver for rootless compatibility."
                fi
            fi
            ;;
        *)
            driver_choice="$system_driver"
            if [[ -z "$driver_choice" ]]; then
                driver_choice="$fallback_driver"
            fi
            ;;
    esac

    if [[ -z "$comment" ]]; then
        if [[ "$home_fs_display" == "unknown" ]]; then
            comment="Using ${driver_choice} driver for rootless Podman storage."
        else
            comment="Rootless storage path on ${home_fs_display}; using ${driver_choice} driver."
        fi
    fi

    comment=${comment//$'\n'/ }
    comment=${comment//\'/}

    local rootless_storage_options_block=""
    if [[ "$driver_choice" == "vfs" ]]; then
        rootless_storage_options_block=$'    storage.options = {\n      ignore_chown_errors = "true";\n    };\n'
    fi

    PODMAN_ROOTLESS_STORAGE_BLOCK=$(cat <<EOF
  # ==========================================================================
  # Rootless Podman storage (per-user override)
  # ==========================================================================
  services.podman.settings.storage = {
    storage = {
      # ${comment}
      driver = "${driver_choice}";
      runroot = "/run/user/\${let
        hmUid = if config.home ? uidNumber then config.home.uidNumber else null;
        osUsers =
          if config ? users && config.users ? users then config.users.users else {};
        osUser = osUsers.\${config.home.username} or null;
        osUserUid = if osUser != null && osUser ? uid then osUser.uid else null;
        accountUsers =
          if config ? accounts && config.accounts ? users then config.accounts.users else {};
        accountUser = accountUsers.\${config.home.username} or null;
        accountUid =
          if accountUser != null && accountUser ? uid then accountUser.uid else null;
        resolvedUid =
          if hmUid != null then hmUid
          else if osUserUid != null then osUserUid
          else if accountUid != null then accountUid
      else 1000;
      in toString resolvedUid}/containers";
      graphroot = "\${config.home.homeDirectory}/.local/share/containers/storage";
    };

__ROOTLESS_STORAGE_OPTIONS__
  };
EOF
)
    PODMAN_ROOTLESS_STORAGE_BLOCK=${PODMAN_ROOTLESS_STORAGE_BLOCK//__ROOTLESS_STORAGE_OPTIONS__/$rootless_storage_options_block}
}

probe_performance_kernel_availability() {
    # Determine which performance kernel packages are available in the current
    # nixpkgs channel by probing the provided attribute names. The function
    # returns a comma-separated list of detected attributes. If the `nix`
    # command is unavailable or the probe fails, an empty string is returned.
    # Args: $@ → kernel attribute names to probe.
    if (( $# == 0 )); then
        return
    fi

    if ! command -v nix >/dev/null 2>&1; then
        return
    fi

    local -a kernel_names=("$@")
    local quoted_names
    quoted_names=$(printf '"%s" ' "${kernel_names[@]}")
    quoted_names=${quoted_names% }

    local -a nix_eval_cmd=("nix" "--extra-experimental-features" "nix-command flakes" "eval" "--raw" "--expr")

    local legacy_probe
    legacy_probe="let pkgs = import <nixpkgs> {}; names = [ ${quoted_names} ]; available = builtins.filter (name: builtins.hasAttr name pkgs) names; in builtins.concatStringsSep \"\\n\" available"

    local result=""
    result=$("${nix_eval_cmd[@]}" "$legacy_probe" 2>/dev/null || true)
    if [[ -n "$result" ]]; then
        printf '%s' "$result"
        return
    fi

    local flake_probe
    flake_probe=$(cat <<'EOF'
let
  inherit (builtins) concatStringsSep filter hasAttr currentSystem getFlake;
  names = NAMES_PLACEHOLDER;
  legacyPackages = (getFlake "nixpkgs").legacyPackages;
  pkgs = legacyPackages.${currentSystem};
  available = filter (name: hasAttr name pkgs) names;
in concatStringsSep "\n" available
EOF
)
    flake_probe=${flake_probe//NAMES_PLACEHOLDER/[ ${quoted_names} ]}

    result=$("${nix_eval_cmd[@]}" "$flake_probe" 2>/dev/null || true)
    if [[ -n "$result" ]]; then
        printf '%s' "$result"
    fi
}

# Resolve TOTAL_RAM_GB (mutable cache defined in config/variables.sh:533) so
# later tuning code can reuse the detected value without duplicating logic.
resolve_total_ram_gb() {
    local cached="${TOTAL_RAM_GB:-}"
    if [[ "$cached" =~ ^[0-9]+$ && "$cached" -gt 0 ]]; then
        echo "$cached"
        return 0
    fi

    local mem_kib=""
    if [[ -r /proc/meminfo ]]; then
        mem_kib=$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)
    fi

    if [[ "$mem_kib" =~ ^[0-9]+$ && "$mem_kib" -gt 0 ]]; then
        local computed=$(( (mem_kib + 1048575) / 1048576 ))
        if (( computed < 1 )); then
            computed=1
        fi
        TOTAL_RAM_GB="$computed"
        export TOTAL_RAM_GB
        echo "$computed"
        return 0
    fi

    if command -v free >/dev/null 2>&1; then
        local mem_mb=""
        mem_mb=$(free -m | awk '/^Mem:/ {print $2}' 2>/dev/null)
        if [[ "$mem_mb" =~ ^[0-9]+$ && "$mem_mb" -gt 0 ]]; then
            local computed=$(( (mem_mb + 1023) / 1024 ))
            if (( computed < 1 )); then
                computed=1
            fi
            TOTAL_RAM_GB="$computed"
            export TOTAL_RAM_GB
            echo "$computed"
            return 0
        fi
    fi

    echo "0"
}

# Decide nix build parallelism based on TOTAL_RAM_GB/CPU_CORES (placeholders
# exported from config/variables.sh). Returns a tuple used when rendering
# nix.conf sections.
determine_nixos_parallelism() {
    local detected_ram="${TOTAL_RAM_GB:-}"
    if [[ ! "$detected_ram" =~ ^[0-9]+$ ]]; then
        detected_ram=$(resolve_total_ram_gb)
    elif (( detected_ram <= 0 )); then
        detected_ram=$(resolve_total_ram_gb)
    fi

    local detected_cores="${CPU_CORES:-}"
    local available_cores

    if [[ "$detected_cores" =~ ^[0-9]+$ && "$detected_cores" -ge 1 ]]; then
        available_cores="$detected_cores"
    elif command -v nproc >/dev/null 2>&1; then
        available_cores=$(nproc 2>/dev/null || printf '1')
    else
        available_cores=1
    fi

    local max_jobs="auto"
    local core_limit=0
    local message=""
    local ram_value

    if [[ "$detected_ram" =~ ^[0-9]+$ ]]; then
        ram_value="$detected_ram"
    else
        ram_value=0
    fi

    if (( ram_value < 8 )); then
        max_jobs="1"
        core_limit=1
    elif (( ram_value < 16 )); then
        max_jobs="2"
        core_limit=2
    fi

    if [[ "$core_limit" != "0" ]]; then
        if (( core_limit > available_cores )); then
            core_limit="$available_cores"
        fi

        if (( core_limit < 1 )); then
            core_limit=1
        fi

        if [[ "$max_jobs" != "auto" ]] && (( max_jobs > core_limit )); then
            max_jobs="$core_limit"
        fi

        message="Detected ${ram_value}GB RAM and ${available_cores} CPU core(s); limiting nixos-rebuild to ${max_jobs} parallel job(s) across ${core_limit} core(s) to avoid out-of-memory conditions."
    fi

    printf '%s\n' "$max_jobs"
    printf '%s\n' "$core_limit"
    printf '%s\n' "$message"
}

build_nixos_rebuild_options() {
    local use_caches="${1:-${USE_BINARY_CACHES:-true}}"
    local -a parallelism
    mapfile -t parallelism < <(determine_nixos_parallelism)

    local computed_max_jobs="${parallelism[0]:-auto}"
    local computed_core_limit="${parallelism[1]:-0}"
    local throttle_message="${parallelism[2]:-}"

    if [[ -n "$throttle_message" ]]; then
        print_info "$throttle_message" >&2
    fi

    local -a opts=(
        "--option" "max-jobs" "$computed_max_jobs"
        "--option" "cores" "$computed_core_limit"
        "--option" "keep-outputs" "true"
        "--option" "keep-derivations" "true"
    )

    if [[ "$use_caches" == "true" ]]; then
        opts+=("--option" "builders-use-substitutes" "true")
        opts+=("--option" "fallback" "true")

        local -a substituters=()
        local -a keys=()
        mapfile -t substituters < <(get_binary_cache_sources)
        mapfile -t keys < <(get_binary_cache_public_keys)

        if (( ${#substituters[@]} > 0 )); then
            local substituters_list
            substituters_list=$(printf '%s ' "${substituters[@]}")
            substituters_list=${substituters_list% }
            opts+=("--option" "substituters" "$substituters_list")
        fi

        if (( ${#keys[@]} > 0 )); then
            local keys_list
            keys_list=$(printf '%s ' "${keys[@]}")
            keys_list=${keys_list% }
            opts+=("--option" "trusted-public-keys" "$keys_list")
        fi

        opts+=("--option" "connect-timeout" "10")
        opts+=("--option" "stalled-download-timeout" "300")
    else
        opts+=("--option" "builders-use-substitutes" "false")
        opts+=("--option" "substitute" "false")
        opts+=("--option" "fallback" "false")
    fi

    if [[ "${REMOTE_BUILDERS_ENABLED:-false}" == "true" && ${#REMOTE_BUILDER_SPECS[@]} -gt 0 ]]; then
        local builder_payload
        builder_payload=$(printf '%s\n' "${REMOTE_BUILDER_SPECS[@]}")
        builder_payload=${builder_payload%$'\n'}
        if [[ -n "$builder_payload" ]]; then
            opts+=("--option" "builders" "$builder_payload")
        fi
    fi

    printf '%s\n' "${opts[@]}"
}

activate_build_acceleration_context() {
    if [[ "${REMOTE_BUILDERS_ENABLED:-false}" == "true" ]]; then
        if [[ -n "${REMOTE_BUILDER_SSH_KEY:-}" && -f "$REMOTE_BUILDER_SSH_KEY" ]]; then
            local ssh_fragment="-i ${REMOTE_BUILDER_SSH_KEY}"
            if [[ -n "${REMOTE_BUILDER_SSH_OPTIONS:-}" ]]; then
                ssh_fragment+=" ${REMOTE_BUILDER_SSH_OPTIONS}"
            fi

            if [[ -n "${NIX_SSHOPTS:-}" ]]; then
                if [[ " $NIX_SSHOPTS " != *" ${ssh_fragment} "* ]]; then
                    export NIX_SSHOPTS="$NIX_SSHOPTS $ssh_fragment"
                fi
            else
                export NIX_SSHOPTS="$ssh_fragment"
            fi
        fi
    fi

    if [[ -n "${CACHIX_AUTH_TOKEN:-}" ]]; then
        export CACHIX_AUTH_TOKEN
    fi
}

describe_remote_build_context() {
    # Summarize build strategy for logs and troubleshooting.
    local strategy="binary caches (default)"
    if [[ "${USE_BINARY_CACHES:-true}" != "true" ]]; then
        strategy="local source builds (binary caches disabled)"
    fi
    if [[ "${REMOTE_BUILD_ACCELERATION_MODE:-}" == "remote-builders" ]]; then
        strategy="binary caches + remote builders"
    fi
    print_info "Build strategy: ${strategy}"

    if [[ "${REMOTE_BUILDERS_ENABLED:-false}" == "true" && ${#REMOTE_BUILDER_SPECS[@]} -gt 0 ]]; then
        print_info "Remote builders enabled (${#REMOTE_BUILDER_SPECS[@]} target(s))"
    fi

    if (( ${#CACHIX_CACHE_NAMES[@]} > 0 )); then
        local joined_caches
        joined_caches=$(printf '%s, ' "${CACHIX_CACHE_NAMES[@]}")
        joined_caches=${joined_caches%%, }
        print_info "Cachix caches configured: ${joined_caches}"
    fi
}

gather_remote_build_acceleration_preferences() {
    print_section "Remote Builder & Cachix Configuration"
    echo ""

    local builder_specs_added=0

    if confirm "Register SSH remote builders for this deployment?" "y"; then
        while true; do
            local spec
            spec=$(prompt_user "Remote builder spec (ssh://host platform - jobs speed). Leave blank when done" "")
            if [[ -z "$spec" ]]; then
                break
            fi

            register_remote_builder_spec "$spec"
            ((builder_specs_added++))
            print_success "Registered remote builder: $spec"
        done

        if (( builder_specs_added > 0 )); then
            local key_candidate
            key_candidate=$(prompt_user "SSH private key for remote builders" "${REMOTE_BUILDER_SSH_KEY:-}")
            if [[ -n "$key_candidate" ]]; then
                if [[ -f "$key_candidate" ]]; then
                    REMOTE_BUILDER_SSH_KEY="$key_candidate"
                    print_info "Using SSH key: $REMOTE_BUILDER_SSH_KEY"
                else
                    print_warning "SSH key path $key_candidate does not exist; using default agent configuration"
                fi
            fi

            local extra_opts
            extra_opts=$(prompt_user "Additional ssh options for remote builders" "${REMOTE_BUILDER_SSH_OPTIONS:-}")
            if [[ -n "$extra_opts" ]]; then
                REMOTE_BUILDER_SSH_OPTIONS="$extra_opts"
            fi
        else
            print_warning "No remote builder definitions provided; skipping SSH builder registration"
            REMOTE_BUILDERS_ENABLED=false
        fi
    fi

    local -a selected_caches=()
    if confirm "Configure private or custom Cachix caches?" "n"; then
        while true; do
            local cache_name
            cache_name=$(prompt_user "Cachix cache name (blank to finish)" "")
            if [[ -z "$cache_name" ]]; then
                break
            fi
            append_unique_value selected_caches "$cache_name"
        done

        if (( ${#selected_caches[@]} > 0 )); then
            CACHIX_CACHE_NAMES=("${selected_caches[@]}")
            print_info "Selected Cachix caches: ${CACHIX_CACHE_NAMES[*]}"

            local supplied_token
            supplied_token=$(prompt_secret "Cachix auth token" "leave blank for read-only caches")
            if [[ -n "$supplied_token" ]]; then
                CACHIX_AUTH_TOKEN="$supplied_token"
                CACHIX_AUTH_ENABLED=true
            else
                CACHIX_AUTH_ENABLED=false
            fi
            : "${CACHIX_AUTH_ENABLED}"

            if ! command -v cachix >/dev/null 2>&1; then
                if declare -F ensure_prerequisite_installed >/dev/null 2>&1; then
                    ensure_prerequisite_installed "cachix" "nixpkgs#cachix" "cachix CLI" || true
                fi
            fi

            if command -v cachix >/dev/null 2>&1 && [[ -n "$CACHIX_AUTH_TOKEN" ]]; then
                if run_as_primary_user cachix authtoken "$CACHIX_AUTH_TOKEN" >/dev/null 2>&1; then
                    print_success "Stored Cachix auth token for current user"
                else
                    print_warning "Failed to register Cachix auth token automatically"
                fi
            elif [[ -n "$CACHIX_AUTH_TOKEN" ]]; then
                print_warning "cachix CLI not available; unable to register auth token automatically"
            fi

            local cache
            for cache in "${CACHIX_CACHE_NAMES[@]}"; do
                local substituter="https://${cache}.cachix.org"
                register_additional_binary_cache "$substituter"

                local signing_key=""
                if command -v cachix >/dev/null 2>&1; then
                    local show_output
                    show_output=$(run_as_primary_user cachix show "$cache" 2>/dev/null || cachix show "$cache" 2>/dev/null || true)
                    signing_key=$(printf '%s\n' "$show_output" | awk -F': ' '/Public key/ {print $2}' | head -n1 | tr -d '\r')
                fi

                if [[ -z "$signing_key" ]]; then
                    signing_key=$(prompt_user "Public signing key for ${cache}" "")
                fi

                if [[ -n "$signing_key" ]]; then
                    register_additional_binary_cache_key "$signing_key"
                else
                    print_warning "No public key recorded for Cachix cache '${cache}'"
                fi
            done
        else
            print_info "No Cachix caches selected"
        fi
    fi

    if (( builder_specs_added == 0 )) && (( ${#CACHIX_CACHE_NAMES[@]} == 0 )); then
        print_info "Remote acceleration unchanged"
    fi

    if [[ -n "$REMOTE_BUILDERS_PREFERENCE_FILE" ]]; then
        local pref_dir
        pref_dir=$(dirname "$REMOTE_BUILDERS_PREFERENCE_FILE")
        if safe_mkdir "$pref_dir"; then
            if cat >"$REMOTE_BUILDERS_PREFERENCE_FILE" <<EOF
REMOTE_BUILDERS_ENABLED=${REMOTE_BUILDERS_ENABLED}
REMOTE_BUILDER_COUNT=${#REMOTE_BUILDER_SPECS[@]}
EOF
            then
                chmod 600 "$REMOTE_BUILDERS_PREFERENCE_FILE" 2>/dev/null || true
                safe_chown_user_dir "$REMOTE_BUILDERS_PREFERENCE_FILE" || true
            fi
        fi
    fi

    echo ""
}

# ============================================================================
# Workspace Preparation Helpers
# ============================================================================

normalize_dotfiles_paths() {
    local resolved_user="${PRIMARY_USER:-${USER:-}}"
    local resolved_home=""

    if declare -F resolve_user_home_directory >/dev/null 2>&1; then
        resolved_home=$(resolve_user_home_directory "$resolved_user" 2>/dev/null || true)
    fi

    if [[ -z "$resolved_home" ]]; then
        resolved_home=$(getent passwd "$resolved_user" 2>/dev/null | cut -d: -f6)
    fi

    if [[ -z "$resolved_home" ]]; then
        home_root="/${HOME_ROOT_DIR:-home}"
        if [[ -d "${home_root}/${resolved_user}" ]]; then
            resolved_home="${home_root}/${resolved_user}"
        fi
    fi
    if [[ -z "$resolved_home" && "$resolved_user" == "root" && -d "/root" ]]; then
        resolved_home="/root"
    fi

    if [[ -z "$resolved_home" || ! -d "$resolved_home" ]]; then
        resolved_home="${HOME:-}"
    fi

    if [[ -z "$resolved_home" ]]; then
        return 0
    fi

    if [[ -z "${PRIMARY_HOME:-}" || ! -d "$PRIMARY_HOME" || "$PRIMARY_HOME" == /nix/store/* || "$PRIMARY_HOME" == /build/* ]]; then
        PRIMARY_HOME="$resolved_home"
    fi

    if [[ -z "${DOTFILES_ROOT:-}" || "$DOTFILES_ROOT" == /nix/store/* || "$DOTFILES_ROOT" == /build/* || "$DOTFILES_ROOT" == /homeless-shelter ]]; then
        DOTFILES_ROOT="$resolved_home/.dotfiles"
    elif [[ "$DOTFILES_ROOT" != /* ]]; then
        DOTFILES_ROOT="$resolved_home/$DOTFILES_ROOT"
    fi

    DEV_HOME_ROOT="$DOTFILES_ROOT"
    HM_CONFIG_DIR="$DOTFILES_ROOT/home-manager"
    FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
    HOME_MANAGER_FILE="$HM_CONFIG_DIR/home.nix"
    SYSTEM_CONFIG_FILE="$HM_CONFIG_DIR/configuration.nix"
    HARDWARE_CONFIG_FILE="$HM_CONFIG_DIR/hardware-configuration.nix"
}

ensure_flake_workspace() {
    local created_root=false
    local created_dir=false

    normalize_dotfiles_paths

    if [[ -z "${DEV_HOME_ROOT:-}" || -z "${HM_CONFIG_DIR:-}" ]]; then
        print_error "ensure_flake_workspace: workspace paths are not defined"
        return 1
    fi

    if [[ ! -d "$DEV_HOME_ROOT" ]]; then
        if safe_mkdir "$DEV_HOME_ROOT"; then
            created_root=true
        else
            print_error "Failed to create flake workspace root: $DEV_HOME_ROOT"
            return 1
        fi
    fi

    safe_chown_user_dir "$DEV_HOME_ROOT" || true

    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        if safe_mkdir "$HM_CONFIG_DIR"; then
            created_dir=true
        else
            print_error "Failed to create flake directory: $HM_CONFIG_DIR"
            return 1
        fi
    fi

    safe_chown_user_dir "$HM_CONFIG_DIR" || true

    if $created_root; then
        print_success "Created flake workspace root at $DEV_HOME_ROOT"
    fi

    if $created_dir; then
        print_success "Created flake configuration directory at $HM_CONFIG_DIR"
    fi

    return 0
}

verify_home_manager_flake_ready() {
    local missing=()

    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        missing+=("directory $HM_CONFIG_DIR")
    fi

    if [[ ! -f "$HM_CONFIG_DIR/flake.nix" ]]; then
        missing+=("flake.nix")
    fi

    if [[ ! -f "$HM_CONFIG_DIR/home.nix" ]]; then
        missing+=("home.nix")
    fi

    if (( ${#missing[@]} > 0 )); then
        print_error "Home Manager flake is incomplete: ${missing[*]}"
        print_info "Phase 3 (Configuration Generation) should create these files."
        print_info "Re-run Phase 3 or restore the flake directory before continuing."
        return 1
    fi

    return 0
}

ensure_flake_git_tracking() {
    if [[ -z "${HM_CONFIG_DIR:-}" || ! -d "$HM_CONFIG_DIR" ]]; then
        return 0
    fi

    local toplevel=""
    toplevel=$(run_git_safe -C "$HM_CONFIG_DIR" rev-parse --show-toplevel 2>/dev/null || true)

    # If the flake lives inside another repo, create a nested repo to avoid
    # "path is not tracked by git" errors during nix flake evaluation.
    if [[ -n "$toplevel" && "$toplevel" != "$HM_CONFIG_DIR" ]]; then
        if [[ ! -d "$HM_CONFIG_DIR/.git" ]]; then
            run_git_safe -C "$HM_CONFIG_DIR" init -q >/dev/null 2>&1 || return 0
        fi
        run_git_safe -C "$HM_CONFIG_DIR" add -A >/dev/null 2>&1 || true
    fi
}

seed_flake_lock_from_template() {
    local backup_dir="${1:-}"
    local backup_stamp="${2:-$(date +%Y%m%d_%H%M%S)}"
    local template_file="$SCRIPT_DIR/templates/flake.lock"
    local target_file="$HM_CONFIG_DIR/flake.lock"

    if [[ ! -f "$template_file" ]]; then
        return 0
    fi

    if [[ "$RESTORE_KNOWN_GOOD_FLAKE_LOCK" == true ]]; then
        if [[ -f "$target_file" && -n "$backup_dir" ]]; then
            safe_mkdir "$backup_dir" || true
            local backup_target="$backup_dir/flake.lock.backup.$backup_stamp"
            safe_copy_file_silent "$target_file" "$backup_target" && \
                print_success "Backed up existing flake.lock before restoring baseline"
        fi

        if safe_copy_file "$template_file" "$target_file"; then
            safe_chown_user_dir "$target_file" || true
            print_success "Restored flake.lock from bundled baseline"
            return 0
        fi

        print_error "Failed to restore flake.lock from template baseline"
        return 1
    fi

    if [[ -f "$target_file" ]]; then
        return 0
    fi

    if safe_copy_file "$template_file" "$target_file"; then
        safe_chown_user_dir "$target_file" || true
        print_success "Seeded flake.lock from bundled baseline"
        return 0
    fi

    print_error "Failed to seed flake.lock from template baseline"
    return 1
}

# ============================================================================
# Validate Flake Lock Completeness
# ============================================================================
# Purpose: Ensure flake.lock contains entries for ALL inputs declared in
#          flake.nix. Missing entries cause silent failures during
#          home-manager switch (e.g., nix-vscode-extensions overlay not
#          available → VSCodium marketplace extensions not installed).
#
# How it works:
#   1. Parse flake.nix to extract declared input names
#   2. Parse flake.lock root.inputs to extract locked input names
#   3. If any declared inputs are missing from the lock, run `nix flake lock`
#      to resolve them WITHOUT updating already-pinned inputs
#
# Arguments:
#   $1 - Path to the flake directory (defaults to $HM_CONFIG_DIR)
#
# Returns:
#   0 - Lock file is complete (or was repaired)
#   1 - Lock file could not be repaired
# ============================================================================
validate_flake_lock_inputs() {
    local flake_dir="${1:-$HM_CONFIG_DIR}"
    local flake_file="$flake_dir/flake.nix"
    local lock_file="$flake_dir/flake.lock"

    if [[ ! -f "$flake_file" ]]; then
        return 0
    fi

    if [[ ! -f "$lock_file" ]]; then
        print_warning "No flake.lock found — will be created on first evaluation"
        return 0
    fi

    if ! command -v jq >/dev/null 2>&1; then
        print_info "jq not available; skipping flake.lock completeness check"
        return 0
    fi

    # Extract declared input names from flake.nix
    # Matches patterns like:  home-manager = {   or   sops-nix = {
    # Avoids matching attribute assignments like nixpkgs.url = ...
    local -a declared_inputs=()
    while IFS= read -r input_name; do
        [[ -n "$input_name" ]] && declared_inputs+=("$input_name")
    done < <(
        awk '
            BEGIN { in_inputs=0; depth=0 }
            /^[[:space:]]*inputs[[:space:]]*=/ {
                in_inputs=1
                depth=1
                next
            }
            in_inputs {
                if (depth == 1) {
                    if (match($0, /^[[:space:]]*([A-Za-z0-9_-]+)[[:space:]]*(=|\.|{)/, m)) {
                        print m[1]
                    }
                }
                open_braces = gsub(/{/, "{")
                close_braces = gsub(/}/, "}")
                depth += open_braces - close_braces
                if (depth <= 0) {
                    in_inputs=0
                }
            }
        ' "$flake_file" | sort -u
    )

    if [[ ${#declared_inputs[@]} -eq 0 ]]; then
        print_info "Could not parse flake inputs — skipping lock validation"
        return 0
    fi

    # Extract locked input names from flake.lock root.inputs
    local -a locked_inputs=()
    while IFS= read -r input_name; do
        [[ -n "$input_name" ]] && locked_inputs+=("$input_name")
    done < <(jq -r '.nodes.root.inputs // {} | keys[]' "$lock_file" 2>/dev/null)

    # Find missing inputs
    local -a missing_inputs=()
    for declared in "${declared_inputs[@]}"; do
        local found=false
        for locked in "${locked_inputs[@]}"; do
            if [[ "$declared" == "$locked" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == false ]]; then
            missing_inputs+=("$declared")
        fi
    done

    if [[ ${#missing_inputs[@]} -eq 0 ]]; then
        print_success "Flake lock file contains all declared inputs (${#declared_inputs[@]} inputs)"
        return 0
    fi

    print_warning "Flake lock is missing ${#missing_inputs[@]} input(s): ${missing_inputs[*]}"
    print_info "Running 'nix flake lock' to resolve missing inputs..."

    # Ensure git tracking is up to date (flake eval requires tracked files)
    ensure_flake_git_tracking

    local -a flake_lock_cmd=(nix flake lock)
    if [[ "$(get_effective_max_jobs)" == "0" ]]; then
        print_warning "max-jobs=0 detected; forcing max-jobs=1 for nix flake lock."
        flake_lock_cmd=(env NIX_CONFIG="max-jobs = 1" nix flake lock)
    fi

    local lock_output=""
    local lock_status=0
    if ! lock_output=$(cd "$flake_dir" && "${flake_lock_cmd[@]}" 2>&1); then
        lock_status=$?
    fi

    if (( lock_status == 0 )); then
        # Verify the lock was updated
        local -a still_missing=()
        local -a new_locked=()
        while IFS= read -r input_name; do
            [[ -n "$input_name" ]] && new_locked+=("$input_name")
        done < <(jq -r '.nodes.root.inputs // {} | keys[]' "$lock_file" 2>/dev/null)

        for missing in "${missing_inputs[@]}"; do
            local resolved=false
            for locked in "${new_locked[@]}"; do
                if [[ "$missing" == "$locked" ]]; then
                    resolved=true
                    break
                fi
            done
            if [[ "$resolved" == false ]]; then
                still_missing+=("$missing")
            fi
        done

        if [[ ${#still_missing[@]} -eq 0 ]]; then
            print_success "Resolved all missing flake inputs: ${missing_inputs[*]}"
            # Re-add the updated lock to git tracking
            if [[ -d "$flake_dir/.git" ]]; then
                run_git_safe -C "$flake_dir" add flake.lock >/dev/null 2>&1 || true
            fi
            return 0
        else
            print_warning "Still missing after lock: ${still_missing[*]}"
            print_info "These inputs may need manual resolution"
            return 1
        fi
    else
        print_warning "nix flake lock encountered issues:"
        [[ -n "$lock_output" ]] && echo "$lock_output" | sed 's/^/  /'
        print_info "The deployment will attempt to continue; nix may fetch missing inputs during evaluation"
        return 1
    fi
}

describe_binary_cache_usage() {
    local context="${1:-operation}"

    if [[ "${USE_BINARY_CACHES:-true}" != "true" ]]; then
        print_info "Binary caches disabled for ${context}; packages will be built from source."
        return 0
    fi

    local -a substituters=()
    mapfile -t substituters < <(get_binary_cache_sources)
    if (( ${#substituters[@]} == 0 )); then
        return 0
    fi

    local joined=""
    local index=0
    local url
    for url in "${substituters[@]}"; do
        if (( index > 0 )); then
            joined+=", "
        fi
        joined+="$url"
        ((index+=1))
    done

    print_info "Binary caches enabled for ${context}: ${joined}"
}

generate_binary_cache_settings() {
    local use_caches="${1:-${USE_BINARY_CACHES:-true}}"
    local -a substituters=()
    local -a keys=()

    if [[ "$use_caches" == "true" ]]; then
        mapfile -t substituters < <(get_binary_cache_sources)
        mapfile -t keys < <(get_binary_cache_public_keys)
    fi

    local binary_cache_settings=$'\n      # ======================================================================\n'
    binary_cache_settings+=$'      # Build Performance Optimizations\n'
    binary_cache_settings+=$'      # ======================================================================\n\n'
    binary_cache_settings+=$'      # Parallel builds: Use all available CPU cores\n'
    binary_cache_settings+=$'      # max-jobs and cores are defined in the main configuration.\n'
    binary_cache_settings+=$'      # Override them here only when necessary to avoid duplicate definitions.\n\n'

    if [[ "$use_caches" == "true" ]]; then
        binary_cache_settings+=$'      # Binary caches: Download pre-built packages instead of building from source\n'
        binary_cache_settings+=$'      # This dramatically reduces build times on the first deployment\n'
    else
        binary_cache_settings+=$'      # Binary caches disabled: build every package from source during deployment\n'
        binary_cache_settings+=$'      # Expect significantly longer build times depending on system resources\n'
    fi

    binary_cache_settings+=$'      substituters = [\n'

    local url
    for url in "${substituters[@]}"; do
        binary_cache_settings+=$'        "'
        binary_cache_settings+="$url"
        binary_cache_settings+=$'"\n'
    done

    binary_cache_settings+=$'      ];\n\n'
    binary_cache_settings+=$'      # Public keys for verifying binary cache signatures\n'
    binary_cache_settings+=$'      trusted-public-keys = [\n'

    local key
    for key in "${keys[@]}"; do
        binary_cache_settings+=$'        "'
        binary_cache_settings+="$key"
        binary_cache_settings+=$'"\n'
    done

    binary_cache_settings+=$'      ];\n\n'

    if [[ "$use_caches" == "true" ]]; then
        binary_cache_settings+=$'      # Download pre-built dependencies during builds\n'
        binary_cache_settings+=$'      builders-use-substitutes = true;\n'
        binary_cache_settings+=$'      substitute = true;\n'
    else
        binary_cache_settings+=$'      # Force local builds for all derivations\n'
        binary_cache_settings+=$'      builders-use-substitutes = false;\n'
        binary_cache_settings+=$'      substitute = false;\n'
    fi
    binary_cache_settings+=$'\n'

    binary_cache_settings+=$'      # Retain build artifacts to speed up future rebuilds\n'
    binary_cache_settings+=$'      keep-outputs = true;\n'
    binary_cache_settings+=$'      keep-derivations = true;\n\n'

    if [[ "$use_caches" == "true" ]]; then
        binary_cache_settings+=$'      # Fallback to building from source if a binary is unavailable\n'
        binary_cache_settings+=$'      fallback = true;\n'
        binary_cache_settings+=$'\n'
        binary_cache_settings+=$'      # Network timeout settings for binary cache downloads\n'
        binary_cache_settings+=$'      connect-timeout = 10;\n'
        binary_cache_settings+=$'      stalled-download-timeout = 300;\n'
    else
        binary_cache_settings+=$'      # Fallback disabled because all builds are already local\n'
        binary_cache_settings+=$'      fallback = false;\n'
    fi

    binary_cache_settings+=$'\n      # Warn about dirty git trees in flakes\n'
    binary_cache_settings+=$'      warn-dirty = false;\n'

    printf '%s' "$binary_cache_settings"
}

# Verify that no template markers remain in a rendered file.
# Additional regex patterns can be provided to catch non-@ tokens
# such as *_PLACEHOLDER or HOMEUSERNAME style markers.
nix_verify_no_placeholders() {
    local target_file="$1"
    local context_label="$2"
    shift 2 || true

    if [[ -z "$target_file" || -z "$context_label" ]]; then
        return 1
    fi

    if [[ ! -f "$target_file" ]]; then
        print_error "Placeholder verification failed: $target_file does not exist"
        return 1
    fi

    local -a patterns=("@[A-Z0-9_]+@")
    if [[ $# -gt 0 ]]; then
        patterns+=("$@")
    fi

    local unresolved=""
    local pattern
    for pattern in "${patterns[@]}"; do
        local matches
        matches=$(grep -nE "$pattern" "$target_file" 2>/dev/null || true)
        if [[ -n "$matches" ]]; then
            if [[ -n "$unresolved" ]]; then
                unresolved+=$'\n'
            fi
            unresolved+="$matches"
        fi
    done

    if [[ -n "$unresolved" ]]; then
        print_error "Unresolved template placeholders detected in $context_label ($target_file):"
        while IFS= read -r line; do
            [[ -n "$line" ]] && print_error "  $line"
        done <<<"$unresolved"
        return 1
    fi

    return 0
}

nix_quote_string() {
    local input="$1"

    input=${input//\\/\\\\}
    input=${input//"/\\"}
    input=${input//$'\n'/\\n}
    input=${input//$'\r'/\\r}
    input=${input//$'\t'/\\t}
    input=${input//\$/\\\$}

    printf '"%s"' "$input"
}

prompt_enable_gitea() {
    local changed="false"
    local default_choice="n"

    if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
        default_choice="y"
    fi

    if confirm "Do you want to enable the Gitea self-hosted Git service?" "$default_choice"; then
        if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
            changed="true"
        fi
        GITEA_ENABLE="true"
    else
        if [[ "${GITEA_ENABLE,,}" != "false" ]]; then
            changed="true"
        fi
        GITEA_ENABLE="false"
        print_info "Gitea service will be disabled"
    fi

    if [[ "$changed" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

prompt_configure_gitea_admin() {
    local changed="false"
    local default_choice="n"

    if [[ "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        default_choice="y"
        GITEA_BOOTSTRAP_ADMIN="true"
    else
        GITEA_BOOTSTRAP_ADMIN="false"
    fi

    if confirm "Do you want to bootstrap a Gitea admin account now?" "$default_choice"; then
        if [[ "$GITEA_BOOTSTRAP_ADMIN" != "true" ]]; then
            changed="true"
        fi

        GITEA_BOOTSTRAP_ADMIN="true"

        local default_user="${GITEA_ADMIN_USER:-gitea-admin}"
        local admin_user
        while true; do
            admin_user=$(prompt_user "Gitea admin username" "$default_user")
            if [[ -z "$admin_user" ]]; then
                admin_user="$default_user"
            fi
            if validate_username "$admin_user" 2>/dev/null; then break; fi
            print_warning "Username must start with a letter/underscore, then lowercase alphanumeric."
        done
        if [[ "$admin_user" != "$GITEA_ADMIN_USER" ]]; then
            GITEA_ADMIN_USER="$admin_user"
            changed="true"
        fi

        local detected_domain="${HOSTNAME:-}"
        if [[ -z "$detected_domain" ]]; then
            detected_domain=$(hostname 2>/dev/null || echo "localhost")
        fi

        local default_email
        if [[ -n "$GITEA_ADMIN_EMAIL" ]]; then
            default_email="$GITEA_ADMIN_EMAIL"
        else
            default_email="${GITEA_ADMIN_USER}@${detected_domain}"
        fi

        local admin_email
        admin_email=$(prompt_user "Gitea admin email" "$default_email")
        if [[ -z "$admin_email" ]]; then
            admin_email="$default_email"
        fi
        if [[ "$admin_email" != "$GITEA_ADMIN_EMAIL" ]]; then
            GITEA_ADMIN_EMAIL="$admin_email"
            changed="true"
        fi

        local password_note
        if [[ -n "$GITEA_ADMIN_PASSWORD" ]]; then
            password_note="leave blank to keep the existing password"
        else
            password_note="leave blank to generate a secure random password"
        fi

        local password_input
        password_input=$(prompt_secret "Gitea admin password" "$password_note")

        if [[ -z "$password_input" ]]; then
            if [[ -n "$GITEA_ADMIN_PASSWORD" ]]; then
                print_info "Keeping the previously cached Gitea admin password"
            else
                local generated_password
                if ! generated_password=$(generate_password 20); then
                    print_error "Failed to generate Gitea admin password"
                    return 1
                fi
                GITEA_ADMIN_PASSWORD="$generated_password"
                changed="true"
                print_success "Generated a new random Gitea admin password"
            fi
        else
            if [[ "$password_input" != "$GITEA_ADMIN_PASSWORD" ]]; then
                GITEA_ADMIN_PASSWORD="$password_input"
                changed="true"
            fi
        fi

        if [[ "$changed" == "true" ]]; then
            print_info "Gitea admin bootstrap will run after the next system switch"
        else
            print_info "Reusing existing Gitea admin bootstrap settings"
        fi

        if [[ -n "$GITEA_SECRETS_CACHE_FILE" ]]; then
            print_info "Secrets cache will be written to: $GITEA_SECRETS_CACHE_FILE"
        fi
    else
        if [[ "$GITEA_BOOTSTRAP_ADMIN" != "false" ]]; then
            changed="true"
        fi
        GITEA_BOOTSTRAP_ADMIN="false"
        print_info "Skipping declarative Gitea admin bootstrap for this run"
        if [[ -n "$GITEA_SECRETS_CACHE_FILE" ]]; then
            print_info "You can enable it later by rerunning the installer and opting into the admin bootstrap"
        fi
    fi

    if [[ "$changed" == "true" ]]; then
        GITEA_PROMPT_CHANGED="true"
    else
        GITEA_PROMPT_CHANGED="false"
    fi

    return 0
}

ensure_gitea_secrets_ready() {
    local mode="${1:---interactive}"
    local interactive="true"
    local updated="false"

    case "$mode" in
        --noninteractive|--hydrate)
            interactive="false"
            ;;
        --interactive)
            interactive="true"
            ;;
        *)
            interactive="true"
            ;;
    esac

    if [[ -n "$GITEA_SECRETS_CACHE_FILE" && -f "$GITEA_SECRETS_CACHE_FILE" ]]; then
        # shellcheck disable=SC1090
        . "$GITEA_SECRETS_CACHE_FILE"
    fi

    # In interactive mode, prompt to enable Gitea FIRST before checking if it's enabled
    # This ensures the user sees the prompt even if GITEA_ENABLE defaults to false
    if [[ "$interactive" == "true" ]]; then
        local needs_prompt="false"
        if [[ "${GITEA_ADMIN_PROMPTED,,}" != "true" ]]; then
            needs_prompt="true"
        fi

        if [[ "$needs_prompt" == "true" ]]; then
            # First ask if user wants to enable Gitea at all
            print_section "Gitea Self-Hosted Git Service"
            echo ""
            if prompt_enable_gitea; then
                updated="true"
            fi
        fi
    fi

    # After prompting (or if non-interactive), check if Gitea is enabled
    # If not enabled, skip secret generation and admin prompts
    if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
        GITEA_ADMIN_PROMPTED="true"
        GITEA_PROMPT_CHANGED="false"
        return 0
    fi

    # Generate secrets with fallback to openssl if generate_hex_secret fails
    # Define this helper function before using it
    generate_secret_with_fallback() {
        local length="$1"
        local secret_name="$2"
        local secret_value=""
        
        # Try primary method (Python-based)
        if declare -F generate_hex_secret >/dev/null 2>&1; then
            if secret_value=$(generate_hex_secret "$length" 2>/dev/null); then
                if [[ -n "$secret_value" ]]; then
                    echo "$secret_value"
                    return 0
                fi
            fi
        fi
        
        # Fallback to openssl
        if command -v openssl >/dev/null 2>&1; then
            if secret_value=$(openssl rand -hex "$length" 2>/dev/null); then
                if [[ -n "$secret_value" ]]; then
                    echo "$secret_value"
                    return 0
                fi
            fi
        fi
        
        # Last resort: use /dev/urandom with od
        if [[ -r /dev/urandom ]]; then
            # Generate hex string of appropriate length
            local hex_length=$((length * 2))
            if secret_value=$(od -An -N "$length" -tx1 /dev/urandom 2>/dev/null | tr -d ' \n' | head -c "$hex_length"); then
                if [[ -n "$secret_value" && ${#secret_value} -ge $((length / 2)) ]]; then
                    echo "$secret_value"
                    return 0
                fi
            fi
        fi
        
        print_error "Failed to generate $secret_name - all methods failed"
        return 1
    }

    if [[ -z "${GITEA_SECRET_KEY:-}" ]]; then
        local generated_secret
        if ! generated_secret=$(generate_secret_with_fallback 32 "Gitea secret key"); then
            print_error "Failed to generate Gitea secret key - Gitea may not start properly"
            print_info "You can manually set GITEA_SECRET_KEY and rerun the deployment"
            # Don't return 1 - allow deployment to continue, user can fix manually
        else
            GITEA_SECRET_KEY="$generated_secret"
            updated="true"
        fi
    fi

    if [[ -z "${GITEA_INTERNAL_TOKEN:-}" ]]; then
        local internal_token
        if ! internal_token=$(generate_secret_with_fallback 32 "Gitea internal token"); then
            print_error "Failed to generate Gitea internal token - Gitea may not start properly"
            print_info "You can manually set GITEA_INTERNAL_TOKEN and rerun the deployment"
        else
            GITEA_INTERNAL_TOKEN="$internal_token"
            updated="true"
        fi
    fi

    if [[ -z "${GITEA_LFS_JWT_SECRET:-}" ]]; then
        local lfs_jwt_secret
        if ! lfs_jwt_secret=$(generate_secret_with_fallback 32 "Gitea LFS JWT secret"); then
            print_error "Failed to generate Gitea LFS JWT secret - LFS features may not work"
            print_info "You can manually set GITEA_LFS_JWT_SECRET and rerun the deployment"
        else
            GITEA_LFS_JWT_SECRET="$lfs_jwt_secret"
            updated="true"
        fi
    fi

    if [[ -z "${GITEA_JWT_SECRET:-}" ]]; then
        local oauth_secret
        if ! oauth_secret=$(generate_secret_with_fallback 32 "Gitea OAuth2 secret"); then
            print_error "Failed to generate Gitea OAuth2 secret - OAuth features may not work"
            print_info "You can manually set GITEA_JWT_SECRET and rerun the deployment"
        else
            GITEA_JWT_SECRET="$oauth_secret"
            updated="true"
        fi
    fi

    # Now prompt for admin configuration if needed (Gitea is enabled at this point)
    local needs_admin_prompt="false"
    if [[ "$interactive" == "true" && "${GITEA_ADMIN_PROMPTED,,}" != "true" ]]; then
        needs_admin_prompt="true"
    elif [[ "$interactive" != "true" && "${GITEA_ADMIN_PROMPTED,,}" != "true" ]]; then
        needs_admin_prompt="true"
    fi

    if [[ "$needs_admin_prompt" == "true" ]]; then
        if [[ "$interactive" != "true" ]]; then
            # In non-interactive mode, Gitea is enabled but admin not configured
            print_warning "Gitea admin bootstrap settings not initialized; rerun Phase 1 to configure."
            print_info "Continuing without Gitea admin setup - you can configure it later."
            # Don't return 1 - allow deployment to continue
            GITEA_ADMIN_PROMPTED="true"
            GITEA_PROMPT_CHANGED="false"
        else
            # Interactive mode - prompt for admin configuration
            # Only prompt for admin if Gitea is enabled (which it is at this point)
            GITEA_PROMPT_CHANGED="false"
            if ! prompt_configure_gitea_admin; then
                print_warning "Gitea admin configuration was cancelled or failed."
                print_info "You can configure Gitea admin later via the web interface."
                # Don't fail completely - allow user to configure later
                GITEA_ADMIN_PROMPTED="true"
                GITEA_PROMPT_CHANGED="false"
            else
                GITEA_ADMIN_PROMPTED="true"
                if [[ "$GITEA_PROMPT_CHANGED" == "true" ]]; then
                    updated="true"
                fi
            fi
        fi
    fi

    if [[ "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        if [[ -z "${GITEA_ADMIN_USER:-}" ]]; then
            GITEA_ADMIN_USER="gitea-admin"
            updated="true"
        fi

        if [[ -z "${GITEA_ADMIN_EMAIL:-}" ]]; then
            local fallback_domain="${HOSTNAME:-}"
            if [[ -z "$fallback_domain" ]]; then
                fallback_domain=$(hostname 2>/dev/null || echo "localhost")
            fi
            GITEA_ADMIN_EMAIL="${GITEA_ADMIN_USER}@${fallback_domain}"
            updated="true"
        fi

        if [[ -z "${GITEA_ADMIN_PASSWORD:-}" ]]; then
            local bootstrap_password
            if ! bootstrap_password=$(generate_password 20); then
                print_error "Failed to generate Gitea admin password"
                return 1
            fi
            GITEA_ADMIN_PASSWORD="$bootstrap_password"
            updated="true"
            print_success "Generated a new random Gitea admin password"
        fi
    fi

    if [[ "$updated" == "true" && -n "$GITEA_SECRETS_CACHE_FILE" ]]; then
        local cache_dir
        cache_dir=$(dirname "$GITEA_SECRETS_CACHE_FILE")
        if safe_mkdir "$cache_dir"; then
            chmod 700 "$cache_dir" 2>/dev/null || true
            if cat >"$GITEA_SECRETS_CACHE_FILE" <<EOF
GITEA_SECRET_KEY=$GITEA_SECRET_KEY
GITEA_INTERNAL_TOKEN=$GITEA_INTERNAL_TOKEN
GITEA_LFS_JWT_SECRET=$GITEA_LFS_JWT_SECRET
GITEA_JWT_SECRET=$GITEA_JWT_SECRET
GITEA_ADMIN_USER=$GITEA_ADMIN_USER
GITEA_ADMIN_EMAIL=$GITEA_ADMIN_EMAIL
GITEA_ADMIN_PASSWORD=$GITEA_ADMIN_PASSWORD
GITEA_BOOTSTRAP_ADMIN=$GITEA_BOOTSTRAP_ADMIN
GITEA_ADMIN_PROMPTED=$GITEA_ADMIN_PROMPTED
EOF
            then
                chmod 600 "$GITEA_SECRETS_CACHE_FILE" 2>/dev/null || true
                safe_chown_user_dir "$cache_dir" || true
                safe_chown_user_dir "$GITEA_SECRETS_CACHE_FILE" || true
                print_success "Updated cached Gitea secrets for declarative setup"
                print_info "Stored secrets at: $GITEA_SECRETS_CACHE_FILE"
                if [[ "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
                    print_info "Admin user: $GITEA_ADMIN_USER"
                    print_warning "Admin password stored in secrets file under GITEA_ADMIN_PASSWORD"
                fi
            else
                print_warning "Failed to write Gitea secrets cache file: $GITEA_SECRETS_CACHE_FILE"
            fi
        else
            print_warning "Unable to create Gitea secrets cache directory: $cache_dir"
        fi
    fi

    return 0
}

# ============================================================================
# Password Provisioning Helpers
# ============================================================================

generate_password_hash() {
    local password="$1"

    if [[ -z "$password" ]]; then
        return 1
    fi

    if command -v python3 >/dev/null 2>&1; then
        PASSWORD_INPUT="$password" python3 - <<'PY'
import crypt
import os
password = os.environ.get("PASSWORD_INPUT", "")
if not password:
    raise SystemExit(1)
print(crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512)))
PY
        return $?
    fi

    if command -v openssl >/dev/null 2>&1; then
        printf '%s' "$password" | openssl passwd -6 -stdin 2>/dev/null
        return $?
    fi

    return 1
}

get_shadow_password_hash() {
    local account="$1"
    local entry=""

    if [[ -z "$account" ]]; then
        return 1
    fi

    if command -v sudo >/dev/null 2>&1; then
        entry=$(sudo grep "^${account}:" /etc/shadow 2>/dev/null || true)
    else
        entry=$(grep "^${account}:" /etc/shadow 2>/dev/null || true)
    fi

    if [[ -z "$entry" ]]; then
        return 0
    fi

    local hash
    hash=$(printf '%s' "$entry" | cut -d: -f2)

    if is_locked_password_field "$hash"; then
        return 0
    fi

    printf '%s' "$hash"
}

is_locked_password_field() {
    local value="$1"
    [[ -z "$value" || "$value" == "!" || "$value" == "*" || "$value" == "!!" || "$value" == \!* || "$value" == \** ]]
}

extract_user_password_snippet_from_config() {
    local config_path="$1"
    local target_user="$2"

    if [[ -z "$config_path" || -z "$target_user" ]]; then
        return 1
    fi

    if [[ ! -f "$config_path" ]]; then
        return 0
    fi

    local snippet=""
    if ! snippet=$(
        CONFIG_PATH="$config_path" TARGET_USER="$target_user" run_python - <<'PY'
import os
import re
import sys
from pathlib import Path

config_path = Path(os.environ.get("CONFIG_PATH", ""))
target_user = os.environ.get("TARGET_USER", "")

if not target_user or not config_path.is_file():
    raise SystemExit(0)

text = config_path.read_text(encoding="utf-8", errors="ignore")
pattern = re.compile(
    r"users\.users\.(?:\"{0}\"|'{0}'|{0})\s*=\s*\{{".format(re.escape(target_user)),
    re.MULTILINE,
)

match = pattern.search(text)
if not match:
    raise SystemExit(0)

idx = match.end()
depth = 0
snippet_chars = []
in_string = False
string_char = ""
escape = False

while idx < len(text):
    ch = text[idx]
    if in_string:
        snippet_chars.append(ch)
        if escape:
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == string_char:
            in_string = False
    else:
        if ch in ('"', "'"):
            if depth > 0:
                snippet_chars.append(ch)
            in_string = True
            string_char = ch
        elif ch == '{':
            depth += 1
            if depth > 1:
                snippet_chars.append(ch)
        elif ch == '}':
            if depth <= 0:
                break
            depth -= 1
            if depth > 0:
                snippet_chars.append(ch)
            else:
                break
        else:
            if depth > 0:
                snippet_chars.append(ch)
    idx += 1

block = ''.join(snippet_chars)
lines = []
for raw in block.splitlines():
    stripped = raw.strip()
    if not stripped or '=' not in stripped:
        continue
    if re.search(r'(hashedPassword|hashedPasswordFile|passwordFile|initialHashedPassword|initialPassword|forceInitialPassword)', stripped):
        lines.append(raw.rstrip())

if lines:
    print('\n'.join(lines))
PY
    ); then
        return 1
    fi

    if [[ -n "$snippet" ]]; then
        printf '%s' "$snippet"
    fi

    return 0
}

hydrate_primary_user_password_block() {
    if [[ -n "${USER_PASSWORD_BLOCK:-}" ]]; then
        return 0
    fi

    local -a search_paths=()

    if [[ -n "${SYSTEM_CONFIG_FILE:-}" && -f "$SYSTEM_CONFIG_FILE" ]]; then
        search_paths+=("$SYSTEM_CONFIG_FILE")
    fi

    search_paths+=("/etc/nixos/configuration.nix")

    local candidate
    for candidate in "${search_paths[@]}"; do
        local snippet=""
        if snippet=$(extract_user_password_snippet_from_config "$candidate" "$PRIMARY_USER"); then
            if [[ -n "$snippet" ]]; then
                if [[ "$snippet" =~ hashedPassword[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
                    local preserved_hash="${BASH_REMATCH[1]}"
                    if is_locked_password_field "$preserved_hash"; then
                        print_warning "Ignoring locked hashedPassword directive for $PRIMARY_USER from ${candidate}"
                        continue
                    fi
                fi
                USER_PASSWORD_BLOCK="$snippet"
                [[ "$USER_PASSWORD_BLOCK" != *$'\n' ]] && USER_PASSWORD_BLOCK+=$'\n'
                print_success "Preserved password directives for $PRIMARY_USER from ${candidate}"
                return 0
            fi
        else
            print_warning "Failed to inspect password directives in ${candidate}"
        fi
    done

    local shadow_hash=""
    if shadow_hash=$(get_shadow_password_hash "$PRIMARY_USER"); then
        if [[ -n "$shadow_hash" ]]; then
            printf -v USER_PASSWORD_BLOCK '    hashedPassword = "%s";\n' "$shadow_hash"
            print_success "Migrated password hash for $PRIMARY_USER from /etc/shadow"
            return 0
        fi
    fi

    local temp_password=""
    if temp_password=$(generate_password 20); then
        USER_TEMP_PASSWORD="$temp_password"
        printf -v USER_PASSWORD_BLOCK '    initialPassword = "%s";\n' "$temp_password"
        print_warning "No existing password configuration found. Generated temporary password for $PRIMARY_USER."
        print_info "Temporary password (change after first login): $USER_TEMP_PASSWORD"
        return 0
    fi

    print_warning "Unable to derive password settings automatically for $PRIMARY_USER."
    return 1
}

provision_primary_user_password() {
    if [[ -n "${USER_PASSWORD_BLOCK:-}" ]]; then
        return 0
    fi

    print_info "No existing password directives detected for $PRIMARY_USER"
    echo "  1) Generate a salted password hash now (recommended)"
    echo "  2) Provide an existing hashed password string"
    echo "  3) Skip (retain manual placeholder in configuration.nix)"

    local choice
    choice=$(prompt_user "Select password provisioning option (1-3)" "1")

    case "$choice" in
        2)
            local hashed_value
            hashed_value=$(prompt_user "Paste hashed password" "")
            if [[ -n "$hashed_value" ]]; then
                printf -v USER_PASSWORD_BLOCK '    hashedPassword = "%s";\n' "$hashed_value"
                print_success "Captured hashed password for $PRIMARY_USER"
            else
                USER_PASSWORD_BLOCK=$'    # (no password directives detected; update manually if required)\n'
                print_warning "No hashed password supplied; manual update still required"
            fi
            ;;
        3)
            USER_PASSWORD_BLOCK=$'    # (no password directives detected; update manually if required)\n'
            print_warning "Leaving password configuration unchanged"
            ;;
        *)
            local attempt
            for attempt in 1 2 3; do
                local first
                local second
                first=$(prompt_secret "Enter new password for $PRIMARY_USER")
                second=$(prompt_secret "Confirm password")

                if [[ -z "$first" ]]; then
                    print_warning "Empty password provided; try again"
                    continue
                fi

                if [[ "$first" != "$second" ]]; then
                    print_warning "Passwords did not match (attempt $attempt of 3)"
                    continue
                fi

                local hashed
                hashed=$(generate_password_hash "$first")
                unset first second

                if [[ -n "$hashed" ]]; then
                    printf -v USER_PASSWORD_BLOCK '    hashedPassword = "%s";\n' "$hashed"
                    print_success "Stored hashed password directive for $PRIMARY_USER"
                    return 0
                fi

                print_error "Unable to generate password hash automatically"
                break
            done

            if [[ -z "${USER_PASSWORD_BLOCK:-}" ]]; then
                USER_PASSWORD_BLOCK=$'    # (no password directives detected; update manually if required)\n'
            fi
            ;;
    esac

    return 0
}

resolve_primary_user_password_hash() {
    local extracted=""

    if [[ -n "${USER_PASSWORD_BLOCK:-}" ]]; then
        if [[ "$USER_PASSWORD_BLOCK" =~ hashedPassword[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
            extracted="${BASH_REMATCH[1]}"
        fi
    fi

    if [[ -z "$extracted" ]]; then
        local shadow_hash=""
        if shadow_hash=$(get_shadow_password_hash "$PRIMARY_USER" 2>/dev/null || true); then
            extracted="$shadow_hash"
        fi
    fi

    if is_locked_password_field "$extracted"; then
        extracted=""
    fi

    printf '%s' "$extracted"
}

render_sops_secrets_file() {
    local backup_dir="$1"
    local backup_timestamp="$2"

    if [[ -z "${HM_CONFIG_DIR:-}" ]]; then
        print_error "HM_CONFIG_DIR is undefined; cannot prepare secrets.yaml"
        return 1
    fi

    if ! declare -F init_sops >/dev/null 2>&1 || ! declare -F encrypt_secrets_file >/dev/null 2>&1 || ! declare -F validate_encrypted_secrets >/dev/null 2>&1; then
        print_error "Secrets management helpers are unavailable; ensure lib/secrets.sh is loaded"
        return 1
    fi

    local secrets_template="${SCRIPT_DIR}/templates/secrets.yaml"
    local secrets_target="${HM_CONFIG_DIR}/secrets.yaml"

    if [[ ! -f "$secrets_template" ]]; then
        print_error "Secrets template not found: $secrets_template"
        return 1
    fi

    # Try to initialize sops, but don't fail deployment if unavailable
    if ! init_sops; then
        print_warning "Failed to initialize sops prerequisites (age/sops not available)"
        print_warning "Secrets will NOT be encrypted in this deployment"
        print_warning "To enable encryption: nix-env -iA nixpkgs.age nixpkgs.sops"
        print_info "Continuing with unencrypted secrets (development only)"
        # Skip encryption but continue deployment
        return 0
    fi

    if ! render_sops_config_file "$HM_CONFIG_DIR" "$backup_dir" "$backup_timestamp"; then
        print_warning "Failed to generate .sops.yaml configuration"
        print_warning "Continuing without secrets encryption"
        return 0
    fi

    if [[ -f "$secrets_target" ]]; then
        if grep -q '^sops:' "$secrets_target" 2>/dev/null; then
            print_success "Encrypted secrets.yaml already present: $secrets_target"
            return 0
        fi

        print_warning "Found existing secrets.yaml without sops metadata; creating a backup before regenerating"
        backup_generated_file "$secrets_target" "secrets.yaml" "${backup_dir:-$HM_CONFIG_DIR/backup}" "${backup_timestamp:-$(date +%Y%m%d_%H%M%S)}" || true
    fi

    print_info "Rendering secrets template into $secrets_target"
    if ! cp "$secrets_template" "$secrets_target"; then
        print_error "Failed to copy secrets template"
        return 1
    fi

    chmod 600 "$secrets_target" 2>/dev/null || true
    safe_chown_user_dir "$secrets_target" || true

    yaml_quote_string() {
        local value="$1"
        value=${value//$'\r'/}
        value=${value//$'\n'/}
        value=${value//\'/\'\'}
        printf "'%s'" "$value"
    }

    local gitea_secret_literal
    local gitea_internal_literal
    local gitea_lfs_literal
    local gitea_jwt_literal
    local gitea_admin_password_literal
    local huggingface_literal
    local user_password_hash_literal

    gitea_secret_literal=$(yaml_quote_string "${GITEA_SECRET_KEY:-}")
    gitea_internal_literal=$(yaml_quote_string "${GITEA_INTERNAL_TOKEN:-}")
    gitea_lfs_literal=$(yaml_quote_string "${GITEA_LFS_JWT_SECRET:-}")
    gitea_jwt_literal=$(yaml_quote_string "${GITEA_JWT_SECRET:-}")

    local admin_password_value=""
    if [[ "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        admin_password_value="${GITEA_ADMIN_PASSWORD:-}"
    fi
    gitea_admin_password_literal=$(yaml_quote_string "$admin_password_value")

    huggingface_literal=$(yaml_quote_string "${HUGGINGFACEHUB_API_TOKEN:-}")

    local resolved_password_hash=""
    resolved_password_hash=$(resolve_primary_user_password_hash)
    if [[ -z "$resolved_password_hash" ]]; then
        print_warning "Unable to determine an existing password hash for $PRIMARY_USER; secrets.yaml will store an empty value"
    fi
    user_password_hash_literal=$(yaml_quote_string "$resolved_password_hash")

    # Remove Gitea secrets section if Gitea is disabled
    if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
        print_info "Gitea is disabled; removing Gitea secrets section from secrets.yaml"
        # Remove lines from "# Gitea Secrets" through "admin_password: ..." (lines 19-25 in template)
        if command -v sed >/dev/null 2>&1; then
            sed -i '/^# Gitea Secrets$/,/^$/{ /^# Gitea Secrets$/d; /^gitea:$/d; /^  secret_key:/d; /^  internal_token:/d; /^  lfs_jwt_secret:/d; /^  jwt_secret:/d; /^  admin_password:/d; }' "$secrets_target"
        fi
    else
        replace_placeholder "$secrets_target" "GITEA_SECRET_KEY_PLACEHOLDER" "$gitea_secret_literal"
        replace_placeholder "$secrets_target" "GITEA_INTERNAL_TOKEN_PLACEHOLDER" "$gitea_internal_literal"
        replace_placeholder "$secrets_target" "GITEA_LFS_JWT_SECRET_PLACEHOLDER" "$gitea_lfs_literal"
        replace_placeholder "$secrets_target" "GITEA_JWT_SECRET_PLACEHOLDER" "$gitea_jwt_literal"
        replace_placeholder "$secrets_target" "GITEA_ADMIN_PASSWORD_PLACEHOLDER" "$gitea_admin_password_literal"
    fi

    replace_placeholder "$secrets_target" "HUGGINGFACE_TOKEN_PLACEHOLDER" "$huggingface_literal"
    replace_placeholder "$secrets_target" "USER_PASSWORD_HASH_PLACEHOLDER" "$user_password_hash_literal"

    if ! nix_verify_no_placeholders "$secrets_target" "secrets.yaml" "GITEA_[A-Z_]+_PLACEHOLDER" "HUGGINGFACE_TOKEN_PLACEHOLDER" "USER_PASSWORD_HASH_PLACEHOLDER"; then
        print_warning "Placeholders remain in secrets.yaml"
    fi

    if ! command -v sops >/dev/null 2>&1; then
        print_error "sops binary is not available; cannot encrypt secrets.yaml"
        return 1
    fi

    local sops_config="${HM_CONFIG_DIR}/.sops.yaml"
    if [[ ! -f "$sops_config" ]]; then
        print_error ".sops.yaml missing from ${HM_CONFIG_DIR}; cannot encrypt secrets."
        return 1
    fi

    export SOPS_CONFIG="$sops_config"
    print_info "Encrypting secrets.yaml..."
    if ! encrypt_secrets_file "$secrets_target"; then
        print_error "Failed to encrypt secrets.yaml"
        return 1
    fi

    if ! validate_encrypted_secrets "$secrets_target"; then
        print_error "Encrypted secrets.yaml validation failed"
        return 1
    fi

    print_success "Encrypted secrets.yaml prepared at $secrets_target"
    print_info "Use 'sops secrets.yaml' from $HM_CONFIG_DIR to edit values going forward"
    return 0
}

render_sops_config_file() {
    local destination_dir="$1"
    local backup_dir="$2"
    local backup_timestamp="$3"

    if [[ -z "$destination_dir" ]]; then
        print_error "render_sops_config_file: destination directory is required"
        return 1
    fi

    local sops_template="${SCRIPT_DIR}/templates/.sops.yaml"
    local sops_target="${destination_dir}/.sops.yaml"

    if [[ ! -f "$sops_template" ]]; then
        print_error "sops configuration template not found: $sops_template"
        return 1
    fi

    local public_key=""
    if ! public_key=$(get_age_public_key 2>/dev/null); then
        print_error "Unable to read age public key for sops configuration"
        return 1
    fi

    if [[ -z "$public_key" ]]; then
        print_error "Age public key is empty; generate the key via init_sops first"
        return 1
    fi

    if [[ -f "$sops_target" ]]; then
        if grep -q "$public_key" "$sops_target" 2>/dev/null; then
            print_success ".sops.yaml already references current age public key"
            return 0
        fi

        print_warning "Existing .sops.yaml does not match current key; creating a backup before regenerating"
        backup_generated_file "$sops_target" ".sops.yaml" "${backup_dir:-$destination_dir/backup}" "${backup_timestamp:-$(date +%Y%m%d_%H%M%S)}" || true
    fi

    if ! cp "$sops_template" "$sops_target"; then
        print_error "Failed to copy sops configuration template"
        return 1
    fi

    replace_placeholder "$sops_target" "AGE_PUBLIC_KEY_PLACEHOLDER" "$public_key"

    if ! nix_verify_no_placeholders "$sops_target" ".sops.yaml" "AGE_PUBLIC_KEY_PLACEHOLDER"; then
        return 1
    fi

    chmod 600 "$sops_target" 2>/dev/null || true
    safe_chown_user_dir "$sops_target" || true
    print_success "Generated $sops_target for sops encryption"
    return 0
}
# ============================================================================
# Generate NixOS System Configuration
# ============================================================================
# Purpose: Generate NixOS configuration files from templates
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
generate_nixos_system_config() {
    normalize_dotfiles_paths
    print_section "Generating NixOS Configuration"

    # ========================================================================
    # Detect System Information
    # ========================================================================
    local HOSTNAME
    HOSTNAME=$(hostname)
    local DETECTED_NIXOS_VERSION
    DETECTED_NIXOS_VERSION=$(derive_system_release_version)
    local NIXOS_VERSION="${SELECTED_NIXOS_VERSION:-$DETECTED_NIXOS_VERSION}"
    local STATE_VERSION="$NIXOS_VERSION"
    local SYSTEM_ARCH
    SYSTEM_ARCH=$(uname -m)

    # Convert arch names
    case "$SYSTEM_ARCH" in
        x86_64) SYSTEM_ARCH="x86_64-linux" ;;
        aarch64) SYSTEM_ARCH="aarch64-linux" ;;
        *) SYSTEM_ARCH="x86_64-linux" ;;
    esac

    if [[ "$NIXOS_VERSION" != "unstable" ]]; then
        local resolved_state_version
        local requested_state_version
        requested_state_version=$(normalize_release_version "$NIXOS_VERSION")
        resolved_state_version=$(resolve_nixos_release_version "$NIXOS_VERSION")
        emit_nixos_channel_fallback_notice
        NIXOS_VERSION="$resolved_state_version"
        if [[ "$requested_state_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
            STATE_VERSION="$requested_state_version"
        else
            STATE_VERSION="$resolved_state_version"
        fi
    else
        # When tracking unstable, keep detected release information for templates/stateVersion
        STATE_VERSION="$DETECTED_NIXOS_VERSION"
    fi

    print_info "System: $HOSTNAME"
    print_info "Architecture: $SYSTEM_ARCH"
    print_info "NixOS Version: $NIXOS_VERSION"
    print_info "State Version: $STATE_VERSION"
    echo ""

    # ========================================================================
    # Determine Channels
    # ========================================================================
    local NIXOS_CHANNEL_NAME="${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${NIXOS_VERSION}}"
    local HM_CHANNEL_NAME="${SYNCHRONIZED_HOME_MANAGER_CHANNEL:-}"
    local resolved_hm_version=""

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        resolved_hm_version=$(resolve_home_manager_release_version "$STATE_VERSION")
        HM_CHANNEL_NAME="release-${resolved_hm_version}"
    elif [[ "$HM_CHANNEL_NAME" =~ ^release-([0-9]+\.[0-9]+)$ ]]; then
        resolved_hm_version=$(resolve_home_manager_release_version "${BASH_REMATCH[1]}")
        HM_CHANNEL_NAME="release-${resolved_hm_version}"
    fi
    emit_home_manager_fallback_notice

    # If using unstable, adjust home-manager channel
    if [[ "$NIXOS_CHANNEL_NAME" == "nixos-unstable" ]]; then
        HM_CHANNEL_NAME="master"
    fi

    print_info "NixOS channel: $NIXOS_CHANNEL_NAME"
    print_info "Home-manager channel: $HM_CHANNEL_NAME"
    echo ""

    # ========================================================================
    # Detect Timezone and Locale
    # ========================================================================
    local TIMEZONE="${SELECTED_TIMEZONE:-$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")}"
    local LOCALE
    LOCALE=$(localectl status | grep "LANG=" | cut -d= -f2 | tr -d ' ' 2>/dev/null || echo "en_US.UTF-8")

    print_info "Timezone: $TIMEZONE"
    print_info "Locale: $LOCALE"
    echo ""

    # ========================================================================
    # Ensure Config Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating configuration directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR
        PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
        if [[ ! -d "$PARENT_DIR" ]]; then
            if ! mkdir -p "$PARENT_DIR"; then
                print_error "Failed to create parent directory: $PARENT_DIR"
                return 1
            fi
        fi

        # Create the config directory
        if ! mkdir -p "$HM_CONFIG_DIR"; then
            print_error "Failed to create directory: $HM_CONFIG_DIR"
            return 1
        fi

        # Set ownership to current user
        # Use sudo if we're running as root but need to set ownership to a non-root user
        if [[ "$EUID" -eq 0 ]] && [[ -n "$SUDO_USER" ]]; then
            # Running with sudo - set ownership to the original user
            chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        elif [[ "$EUID" -eq 0 ]]; then
            # Running as root without sudo - set to PRIMARY_USER
            chown -R "$PRIMARY_USER:$(id -gn "$PRIMARY_USER" 2>/dev/null || echo "users")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        fi
        # If running as normal user, ownership is already correct from mkdir

        print_success "Created configuration directory"
    else
        print_success "Configuration directory exists: $HM_CONFIG_DIR"
    fi
    echo ""

    # ========================================================================
    # Backup Existing Configurations
    # ========================================================================
    local BACKUP_TIMESTAMP
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local BACKUP_DIR="${HM_BACKUP_DIR}"

    backup_generated_file "$SYSTEM_CONFIG_FILE" "configuration.nix" "$BACKUP_DIR" "$BACKUP_TIMESTAMP" || true
    backup_generated_file "$FLAKE_FILE" "flake.nix" "$BACKUP_DIR" "$BACKUP_TIMESTAMP" || true

    # ========================================================================
    # Generate Hardware Configuration
    # ========================================================================
    print_info "Generating hardware configuration..."
    if ! materialize_hardware_configuration; then
        print_warning "Hardware configuration generation had issues"
        # Continue anyway as it might already exist
    fi

    # ========================================================================
    # Copy Configuration Template
    # ========================================================================
    local TEMPLATE_DIR="${SCRIPT_DIR}/templates"
    if [[ ! -d "$TEMPLATE_DIR" ]]; then
        print_error "Template directory not found: $TEMPLATE_DIR"
        return 1
    fi

    local CONFIG_TEMPLATE="$TEMPLATE_DIR/configuration.nix"
    if [[ ! -f "$CONFIG_TEMPLATE" ]]; then
        print_error "Configuration template not found: $CONFIG_TEMPLATE"
        return 1
    fi

    print_info "Copying configuration template..."
    if ! cp "$CONFIG_TEMPLATE" "$SYSTEM_CONFIG_FILE"; then
        print_error "Failed to copy configuration template"
        return 1
    fi

    # Normalize Avahi disablement to avoid unit failures and activation script issues.
    if [[ -f "$SYSTEM_CONFIG_FILE" ]]; then
        # Remove unsupported systemd.maskedServices/sockets entries.
        local tmp_normalized
        tmp_normalized=$(mktemp)
        grep -v 'systemd\.maskedServices' "$SYSTEM_CONFIG_FILE" | grep -v 'systemd\.maskedSockets' > "$tmp_normalized" || true
        mv "$tmp_normalized" "$SYSTEM_CONFIG_FILE"
    fi

    local support_module="python-overrides.nix"
    print_info "Syncing $support_module into system configuration workspace..."
    if ! sync_support_module "$support_module" "$TEMPLATE_DIR" "$HM_CONFIG_DIR" "$BACKUP_DIR" "$BACKUP_TIMESTAMP"; then
        return 1
    fi

    # ========================================================================
    # Copy NixOS Improvements Directory
    # ========================================================================
    # Copy the nixos-improvements module directory to both system and home-manager
    # config directories so the imports in configuration.nix and home.nix work
    if [[ -d "$TEMPLATE_DIR/nixos-improvements" ]]; then
        print_info "Syncing nixos-improvements modules to system configuration..."
        local system_improvements_dir="/etc/nixos/nixos-improvements"

        local system_improvements_synced=false

        # Create backup if directory already exists.
        # Best-effort only: missing sudo auth should not abort template rendering.
        if [[ -d "$system_improvements_dir" ]]; then
            local backup_improvements_dir="$BACKUP_DIR/nixos-improvements-$BACKUP_TIMESTAMP"
            print_info "Backing up existing nixos-improvements to $backup_improvements_dir"
            if ! sudo -n cp -r "$system_improvements_dir" "$backup_improvements_dir" 2>/dev/null; then
                print_warning "Could not backup existing nixos-improvements directory (sudo auth unavailable or copy failed)"
            fi
        fi

        # Copy improvements to system config.
        # Non-fatal when sudo auth is unavailable (for non-interactive/test runs).
        if sudo -n cp -r "$TEMPLATE_DIR/nixos-improvements" "/etc/nixos/" 2>/dev/null; then
            system_improvements_synced=true
            print_success "NixOS improvements modules copied to /etc/nixos/nixos-improvements"
        else
            print_warning "Skipping /etc/nixos/nixos-improvements sync (sudo auth unavailable or copy failed)"
        fi

        local mobile_workstation_file="$system_improvements_dir/mobile-workstation.nix"
        if [[ "$system_improvements_synced" == true && -f "$mobile_workstation_file" ]]; then
            print_info "Ensuring lid close uses suspend-then-hibernate (12h) in $mobile_workstation_file"
            sudo -n sed -i \
                -e 's/HandleLidSwitch = lib.mkDefault "[^"]*";/HandleLidSwitch = lib.mkDefault "suspend-then-hibernate";/' \
                -e 's/HandleLidSwitchDocked = lib.mkDefault "[^"]*";/HandleLidSwitchDocked = lib.mkDefault "suspend-then-hibernate";/' \
                -e 's/HandleLidSwitchExternalPower = lib.mkDefault "[^"]*";/HandleLidSwitchExternalPower = lib.mkDefault "suspend-then-hibernate";/' \
                -e 's/HibernateDelaySec=[0-9][0-9]*/HibernateDelaySec=43200/' \
                "$mobile_workstation_file" || print_warning "Failed to enforce lid-close suspend-then-hibernate defaults"
        fi

        # Also copy to home-manager config for testing.nix
        print_info "Syncing nixos-improvements to home-manager configuration..."
        local hm_improvements_dir="$HM_CONFIG_DIR/nixos-improvements"
        if [[ -d "$hm_improvements_dir" ]]; then
            local backup_hm_improvements="$BACKUP_DIR/hm-nixos-improvements-$BACKUP_TIMESTAMP"
            print_info "Backing up existing home-manager nixos-improvements"
            cp -r "$hm_improvements_dir" "$backup_hm_improvements" 2>/dev/null || true
        fi

        if ! cp -r "$TEMPLATE_DIR/nixos-improvements" "$HM_CONFIG_DIR/"; then
            print_error "Failed to copy nixos-improvements to home-manager config"
            return 1
        fi
        print_success "NixOS improvements modules copied to $HM_CONFIG_DIR/nixos-improvements"
    else
        print_info "No nixos-improvements directory found in templates (optional)"
    fi

    if declare -F detect_container_storage_backend >/dev/null 2>&1; then
        if [[ "${FORCE_CONTAINER_STORAGE_REDETECT:-false}" == true ]]; then
            print_info "Forcing container storage backend re-detection (FORCE_CONTAINER_STORAGE_REDETECT=true)"
            detect_container_storage_backend
        elif [[ "${PODMAN_STORAGE_DETECTION_RUN:-false}" != true ]]; then
            print_info "Detecting container storage backend compatibility..."
            detect_container_storage_backend
        elif [[ -n "${PODMAN_STORAGE_DRIVER:-}" ]]; then
            local cached_comment="${PODMAN_STORAGE_COMMENT:-Using previously detected container storage driver.}"
            print_info "Using cached container storage backend: ${PODMAN_STORAGE_DRIVER} (${cached_comment})"
        fi
    fi

    # ========================================================================
    # Replace Placeholders in configuration.nix
    # ========================================================================
    print_info "Customizing configuration..."

    if [[ -z "${ZSWAP_ZPOOL:-}" ]] && declare -F select_zswap_memory_pool >/dev/null 2>&1; then
        select_zswap_memory_pool
    fi

    local enable_zswap="${ENABLE_ZSWAP_CONFIGURATION:-false}"
    local zswap_percent="${ZSWAP_MAX_POOL_PERCENT:-20}"
    local zswap_compressor="${ZSWAP_COMPRESSOR:-zstd}"
    local zswap_zpool="${ZSWAP_ZPOOL:-}"

    local kernel_package_attr=""
    if declare -F resolve_preferred_kernel_package_attr >/dev/null 2>&1; then
        kernel_package_attr=$(resolve_preferred_kernel_package_attr 2>/dev/null || echo "")
    fi

    local zswap_pool_verified=false
    if [[ -n "$kernel_package_attr" ]] && declare -F choose_supported_zswap_zpool_for_kernel >/dev/null 2>&1; then
        local adjusted_zswap_pool=""
        adjusted_zswap_pool=$(choose_supported_zswap_zpool_for_kernel "$zswap_zpool" "$kernel_package_attr" 2>/dev/null || echo "")
        if [[ -n "$adjusted_zswap_pool" ]]; then
            zswap_pool_verified=true
            if [[ -z "$zswap_zpool" ]]; then
                print_info "Kernel package ${kernel_package_attr} supports ${adjusted_zswap_pool}; selecting automatically."
            elif [[ "$adjusted_zswap_pool" != "$zswap_zpool" ]]; then
                print_warning "Kernel package ${kernel_package_attr} lacks ${zswap_zpool}; switching zswap pool to supported ${adjusted_zswap_pool}."
            fi
            zswap_zpool="$adjusted_zswap_pool"
            ZSWAP_ZPOOL="$adjusted_zswap_pool"
        fi
    fi

    if [[ "$zswap_pool_verified" != true ]]; then
        if [[ -n "$zswap_zpool" && "$zswap_zpool" != "zsmalloc" ]]; then
            local target_kernel_label="${kernel_package_attr:-selected kernel}"
            print_warning "Unable to verify ${zswap_zpool} support for ${target_kernel_label}; defaulting zswap pool to zsmalloc."
        elif [[ -z "$zswap_zpool" ]]; then
            print_info "Zswap pool not specified; defaulting to safe zsmalloc backend."
        fi
        zswap_zpool="zsmalloc"
        ZSWAP_ZPOOL="$zswap_zpool"
    fi

    local -a performance_kernel_preference=(
        "linuxPackages_latest"
        "linuxPackages_tkg"
        "linuxPackages_xanmod"
        "linuxPackages_lqx"
        "linuxPackages_zen"
    )

    local kernel_preference_string
    kernel_preference_string=$(format_kernel_preference_string "${performance_kernel_preference[@]}")

    if [[ -n "$kernel_preference_string" ]]; then
        print_info "Kernel preference: ${kernel_preference_string}"
    fi

    local available_performance_kernels=""
    if command -v nix >/dev/null 2>&1; then
        available_performance_kernels=$(probe_performance_kernel_availability "${performance_kernel_preference[@]}")
        if [[ -n "$available_performance_kernels" ]]; then
            available_performance_kernels=${available_performance_kernels//$'\n'/', '}
            print_success "Performance kernels available in current channel: ${available_performance_kernels}"
        else
            print_warning "Could not confirm performance kernel availability via nix; falling back to preference order above"
        fi
    else
        print_warning "nix command not found in PATH; skipping kernel availability probe"
    fi

    print_info "configuration.nix will select the first available kernelPackages attribute from that order."

    # GPU monitoring packages
    local GPU_MONITORING_PACKAGES="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES="[ pkgs.radeontop pkgs.amdgpu_top ]"
    elif [[ "$GPU_TYPE" == "nvidia" ]]; then
        GPU_MONITORING_PACKAGES="[ pkgs.nvtop ]"
    fi

    local generated_at
    generated_at=$(date --iso-8601=seconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)

    local primary_user="${PRIMARY_USER:-$USER}"
    local cpu_vendor_label="Unknown"
    case "${CPU_VENDOR:-unknown}" in
        intel) cpu_vendor_label="Intel" ;;
        amd) cpu_vendor_label="AMD" ;;
    esac

    local -a initrd_kernel_modules_entries=()
    local early_kms_policy
    early_kms_policy=$(printf '%s' "${EARLY_KMS_POLICY:-off}" | tr '[:upper:]' '[:lower:]')
    local early_kms_module=""
    local early_kms_label=""
    case "${GPU_TYPE:-unknown}" in
        intel)
            early_kms_module="i915"
            early_kms_label="Intel"
            ;;
        amd)
            early_kms_module="amdgpu"
            early_kms_label="AMD"
            ;;
    esac

    local enable_early_kms=true
    case "$early_kms_policy" in
        off|false|0|disable)
            enable_early_kms=false
            ;;
        auto|"")
            early_kms_policy="auto"
            ;;
        force|on|true|1|enable)
            early_kms_policy="force"
            ;;
        *)
            print_warning "Unknown EARLY_KMS_POLICY='$early_kms_policy'; using off."
            early_kms_policy="off"
            ;;
    esac

    if [[ -n "$early_kms_module" && "$enable_early_kms" == true ]]; then
        local module_available=true
        local module_skip_reason=""
        if [[ "$early_kms_policy" == "auto" ]]; then
            # Guardrail: avoid forcing AMD initrd early-KMS in auto mode.
            # Some systems still boot more reliably when amdgpu is left to
            # hardware-configuration defaults or loaded later in userspace.
            if [[ "$early_kms_module" == "amdgpu" ]]; then
                module_available=false
                module_skip_reason="auto mode skips forced amdgpu initrd preload (use EARLY_KMS_POLICY=force to override)"
            elif command -v modinfo >/dev/null 2>&1; then
                if ! modinfo "$early_kms_module" >/dev/null 2>&1; then
                    module_available=false
                    module_skip_reason="module not available on current kernel"
                fi
            fi
        fi

        if [[ "$module_available" == true ]]; then
            initrd_kernel_modules_entries+=(
                "      # ${early_kms_label} GPU early KMS (auto-detected)"
                "      \"${early_kms_module}\""
            )
        else
            if [[ -n "$module_skip_reason" ]]; then
                print_warning "Skipping early KMS module '${early_kms_module}' (${module_skip_reason})."
            else
                print_warning "Skipping early KMS module '${early_kms_module}'."
            fi
        fi
    fi

    if [[ "${enable_zswap,,}" == "true" && "${zswap_zpool}" != "zsmalloc" ]]; then
        initrd_kernel_modules_entries+=(
            "      # Zswap allocator required before kernel selects a zpool"
            "      \"${zswap_zpool}\""
        )
        print_info "Preloading ${zswap_zpool} in initrd so zswap can initialize with the requested zpool."
    fi

    local initrd_kernel_modules
    if ((${#initrd_kernel_modules_entries[@]} > 0)); then
        local initrd_lines
        printf -v initrd_lines '%s\n' "${initrd_kernel_modules_entries[@]}"
        initrd_lines=${initrd_lines%$'\n'}
        initrd_kernel_modules=$'    initrd.availableKernelModules = [\n'"${initrd_lines}"$'\n    ];'
    else
        initrd_kernel_modules="    # initrd.availableKernelModules handled by hardware-configuration.nix"
    fi

    local microcode_section="# hardware.cpu microcode updates managed automatically"
    if [[ -n "${CPU_MICROCODE:-}" && "${CPU_VENDOR:-unknown}" != "unknown" ]]; then
        microcode_section="hardware.cpu.${CPU_VENDOR}.updateMicrocode = true;  # Enable ${cpu_vendor_label} microcode updates"
    fi

    case "${CPU_VENDOR:-unknown}" in
        intel)
            if [[ -n "${CPU_MICROCODE:-}" ]]; then
                print_success "Enabling Intel microcode updates."
            else
                print_warning "Intel CPU detected but microcode package unavailable; leaving microcode settings unchanged."
            fi
            ;;
        amd)
            if [[ -n "${CPU_MICROCODE:-}" ]]; then
                print_success "Enabling AMD microcode updates."
            else
                print_warning "AMD CPU detected but microcode package unavailable; leaving microcode settings unchanged."
            fi
            ;;
        *)
            print_info "CPU vendor unknown; microcode updates and early KMS stay at distro defaults."
            ;;
    esac

    if [[ -n "$early_kms_module" && "$enable_early_kms" == true ]]; then
        if [[ "$early_kms_policy" == "force" ]]; then
            print_warning "Early KMS policy 'force': module '${early_kms_module}' will be preloaded in initrd."
        else
            print_info "Early KMS policy '${early_kms_policy}': module '${early_kms_module}' configured when available."
        fi
    elif [[ "$enable_early_kms" != true ]]; then
        print_info "Early KMS policy disabled via EARLY_KMS_POLICY=${early_kms_policy}."
    fi

    local binary_cache_settings
    binary_cache_settings=$(generate_binary_cache_settings "${USE_BINARY_CACHES:-true}")

    local enable_gaming_value
    enable_gaming_value=$(printf '%s' "${ENABLE_GAMING_STACK:-true}" | tr '[:upper:]' '[:lower:]')
    local gaming_stack_enabled=false
    case "$enable_gaming_value" in
        true|1|yes|on)
            gaming_stack_enabled=true
            ;;
    esac

    resolve_mangohud_preferences

    local mangohud_profile="$RESOLVED_MANGOHUD_PROFILE"
    local mangohud_profile_origin="$RESOLVED_MANGOHUD_PROFILE_ORIGIN"
    local mangohud_desktop_window_mode="$RESOLVED_MANGOHUD_DESKTOP_MODE"
    local mangohud_injects_into_apps="$RESOLVED_MANGOHUD_INJECTS"

    local glf_os_definitions

    local mangohud_definition
    mangohud_definition=$(generate_mangohud_nix_definitions)
    local cosmic_blacklist_block
    cosmic_blacklist_block=$(render_cosmic_blacklist_block)
    mangohud_definition="${mangohud_definition//__MANGOHUD_PROFILE__/$mangohud_profile}"
    mangohud_definition="${mangohud_definition//__COSMIC_BLACKLIST_ENTRIES__/$cosmic_blacklist_block}"

    if [[ "$gaming_stack_enabled" == true ]]; then
        print_info "Applying MangoHud overlay profile: $mangohud_profile (${mangohud_profile_origin})"
        if [[ "$mangohud_desktop_window_mode" == true ]]; then
            if [[ "$mangohud_injects_into_apps" == true ]]; then
                print_info "Desktop overlay window will auto-start while MangoHud continues to inject into supported applications."
            else
                print_info "Desktop-only overlay mode enabled: MangoHud stays in mangoapp and skips injection into normal applications."
            fi
        fi

        glf_os_definitions=$(cat <<EOF
${mangohud_definition}
  glfLutrisWithGtk =
    if pkgs ? lutris then
      pkgs.lutris.override { extraLibraries = p: [ p.libadwaita p.gtk4 ]; }
    else
      null;
  glfGamingPackages =
    lib.optionals (glfLutrisWithGtk != null) [ glfLutrisWithGtk ]
    # Heroic is currently excluded from defaults because the electron build in
    # nixos-25.05 is marked insecure and breaks evaluation.
    ++ lib.optionals (pkgs ? joystickwake) [ pkgs.joystickwake ]
    ++ lib.optionals (pkgs ? mangohud) [ pkgs.mangohud ]
    ++ lib.optionals (pkgs ? mesa-demos) [ pkgs.mesa-demos ]
    ++ lib.optionals (pkgs ? oversteer) [ pkgs.oversteer ]
    ++ lib.optionals (builtins.hasAttr "umu-launcher" pkgs) [ pkgs."umu-launcher" ]
    ++ lib.optionals (pkgs ? wineWowPackages && pkgs.wineWowPackages ? staging)
      [ pkgs.wineWowPackages.staging ]
    ++ lib.optionals (pkgs ? winetricks) [ pkgs.winetricks ]
    ++ lib.optionals (pkgs ? linuxPackages_latest && pkgs.linuxPackages_latest ? hid-tmff2)
      [ pkgs.linuxPackages_latest.hid-tmff2 ];
  glfSteamPackage =
    if pkgs ? steam then
      pkgs.steam.override {
        extraEnv = {
          MANGOHUD = if glfMangoHudInjectsIntoApps then "1" else "0";
          OBS_VKCAPTURE = "1";
        };
      }
    else
      null;
  glfSteamCompatPackages =
    lib.optionals (pkgs ? proton-ge-bin) [ pkgs.proton-ge-bin ];
  glfSystemUtilities =
    lib.optionals (pkgs ? exfatprogs) [ pkgs.exfatprogs ]
    ++ lib.optionals (pkgs ? fastfetch) [ pkgs.fastfetch ]
    ++ lib.optionals (pkgs ? ffmpeg) [ pkgs.ffmpeg ]
    ++ lib.optionals (pkgs ? ffmpegthumbnailer) [ pkgs.ffmpegthumbnailer ]
    ++ lib.optionals (pkgs ? libva-utils) [ pkgs.libva-utils ]
    ++ lib.optionals (pkgs ? usbutils) [ pkgs.usbutils ]
    ++ lib.optionals (pkgs ? hunspell) [ pkgs.hunspell ]
    ++ lib.optionals (
      pkgs ? hunspellDicts && builtins.hasAttr "fr-any" pkgs.hunspellDicts
    ) [ pkgs.hunspellDicts.fr-any ]
    ++ lib.optionals (pkgs ? hyphen) [ pkgs.hyphen ]
    ++ lib.optionals (
      pkgs ? texlivePackages
      && builtins.hasAttr "hyphen-french" pkgs.texlivePackages
    ) [ pkgs.texlivePackages.hyphen-french ];
EOF
)
    else
        print_info "Gaming stack disabled; MangoHud profile set to $mangohud_profile (${mangohud_profile_origin})."
        if [[ "$mangohud_desktop_window_mode" == true ]]; then
            if [[ "$mangohud_injects_into_apps" == true ]]; then
                print_info "Desktop overlay window will auto-start while MangoHud continues to inject into supported applications."
            else
                print_info "Desktop-only overlay mode enabled: MangoHud stays in mangoapp and skips injection into normal applications."
            fi
        fi

        glf_os_definitions=$(cat <<EOF
${mangohud_definition}
  glfLutrisWithGtk = if pkgs ? lutris then pkgs.lutris else null;
  glfGamingPackages = [];
  glfSteamPackage = if pkgs ? steam then pkgs.steam else null;
  glfSteamCompatPackages = [];
  glfSystemUtilities =
    lib.optionals (pkgs ? mangohud) [ pkgs.mangohud ];
EOF
)
    fi

    local glf_gaming_stack_section
    if [[ "$gaming_stack_enabled" == true ]]; then
        glf_gaming_stack_section=$(cat <<'EOF'
  # ===========================================================================
  # Gaming Stack (GLF OS integration)
  # ===========================================================================
  hardware.steam-hardware.enable = true;
  hardware.xone.enable = true;
  hardware.xpadneo.enable = true;
  hardware.opentabletdriver.enable = true;

  services.udev = {
    extraRules = lib.mkAfter ''
      # Pin block devices that support it to BFQ without touching zram or partitions
      ACTION=="add|change", SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", KERNEL!="zram*", TEST=="queue/scheduler", ATTR{queue/scheduler}="bfq"

      # Ignore DualSense/DualShock touchpads so they do not wake the desktop
      ATTRS{name}=="Sony Interactive Entertainment Wireless Controller Touchpad", ENV{LIBINPUT_IGNORE_DEVICE}="1"
      ATTRS{name}=="Sony Interactive Entertainment DualSense Wireless Controller Touchpad", ENV{LIBINPUT_IGNORE_DEVICE}="1"
      ATTRS{name}=="Wireless Controller Touchpad", ENV{LIBINPUT_IGNORE_DEVICE}="1"
      ATTRS{name}=="DualSense Wireless Controller Touchpad", ENV{LIBINPUT_IGNORE_DEVICE}="1"
    '';
    packages = lib.mkAfter (
      lib.optionals (pkgs ? oversteer) [ pkgs.oversteer ]
    );
  };

  programs.gamemode.enable = true;

  programs.gamescope = {
    enable = true;
    capSysNice = true;
  };

  programs.steam = lib.mkIf (glfSteamPackage != null) {
    enable = true;
    gamescopeSession.enable = true;
    package = glfSteamPackage;
    remotePlay.openFirewall = true;
    localNetworkGameTransfers.openFirewall = true;
    extraCompatPackages = glfSteamCompatPackages;
  };

  environment.etc."gamemode.ini".text = lib.mkForce ''
    [general]
    inhibit_screensaver=1
    renice=10
    softrealtime=on
    ioprio=0

    [gpu]
    apply_gpu_optimisations=auto
  '';

  environment.etc."systemd/zram-generator.conf".text = lib.mkForce ''
    [zram0]
    zram-size = ram / 4
    compression-algorithm = zstd
    swap-priority = 5
    max-parallel = 0
  '';
EOF
)
    else
        glf_gaming_stack_section=$(cat <<'EOF'
  # Gaming stack disabled via ENABLE_GAMING_STACK; gamemode, gamescope, steam, and zram overrides are omitted.
EOF
)
    fi

    local lact_service_block=""
    local enable_lact_value
    enable_lact_value=$(printf '%s' "${ENABLE_LACT:-auto}" | tr '[:upper:]' '[:lower:]')
    local lact_should_enable="false"

    case "$enable_lact_value" in
        true|1|yes|on)
            lact_should_enable="true"
            ;;
        auto)
            case "${GPU_TYPE:-unknown}" in
                nvidia|amd|intel)
                    lact_should_enable="true"
                    ;;
            esac
            ;;
        *)
            lact_should_enable="false"
            ;;
    esac

    if [[ "$lact_should_enable" == "true" ]]; then
        lact_service_block=$(cat <<'EOF'
  services.lact = {
    enable = true;
  };
EOF
)
    fi

    local selected_flatpak_profile="${SELECTED_FLATPAK_PROFILE:-${DEFAULT_FLATPAK_PROFILE:-core}}"
    local flatpak_packages_block=""
    if (( ${#DEFAULT_FLATPAK_APPS[@]} > 0 )); then
        flatpak_packages_block=$'  # Flatpak applications managed by profile: '"${selected_flatpak_profile}"$'\n'
        flatpak_packages_block+=$'  flathubPackages = [\n'
        local flatpak_app_id
        for flatpak_app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
            flatpak_packages_block+=$'    '"\"${flatpak_app_id}\""$'\n'
        done
        flatpak_packages_block+=$'  ];\n'
    else
        flatpak_packages_block=$'  # Selected Flatpak profile does not provision GUI applications.\n  flathubPackages = [];\n'
    fi

    local default_podman_driver="${DEFAULT_PODMAN_STORAGE_DRIVER:-zfs}"
    local podman_storage_driver="${PODMAN_STORAGE_DRIVER:-$default_podman_driver}"
    case "$podman_storage_driver" in
        vfs|btrfs|zfs)
            ;;
        overlay)
            print_warning "Overlay storage driver is not recommended for system-level Podman; converting to zfs."
            print_info "Note: Overlay requires fuse-overlayfs and can cause systemd mount issues."
            podman_storage_driver="zfs"
            ;;
        *)
            print_warning "Unknown Podman storage driver '${podman_storage_driver}'; defaulting to zfs."
            podman_storage_driver="zfs"
            ;;
    esac
    local podman_storage_comment="${PODMAN_STORAGE_COMMENT:-Using ${podman_storage_driver} driver on detected filesystem.}"
    podman_storage_comment=${podman_storage_comment//$'\n'/ }
    podman_storage_comment=${podman_storage_comment//\'/}

    local storage_options_block=""
    if [[ "$podman_storage_driver" == "vfs" ]]; then
        storage_options_block=$'    storage.options = {\n      ignore_chown_errors = "true";\n    };\n'
    fi

    local podman_storage_block
    podman_storage_block=$(cat <<'EOF'
  # ===========================================================================
  # Container storage backend (auto-detected) - SYSTEM-LEVEL ONLY
  # ===========================================================================
  # NOTE: This configures system-level podman storage (root).
  # User-level (rootless) podman uses overlay with fuse-overlayfs configured
  # via Home Manager in home.nix to prevent VFS bloat while avoiding boot issues.
  # System-level stays on VFS/btrfs/zfs to prevent systemd overlay mount failures.
  virtualisation.containers.storage.settings = {
    storage = {
      # __PODMAN_STORAGE_COMMENT__
      driver = "__PODMAN_STORAGE_DRIVER__";
      graphroot = "/var/lib/containers/storage";
      runroot = "/run/containers/storage";
    };

__PODMAN_STORAGE_OPTIONS__
  };
EOF
)
    podman_storage_block=${podman_storage_block//__PODMAN_STORAGE_COMMENT__/$podman_storage_comment}
    podman_storage_block=${podman_storage_block//__PODMAN_STORAGE_DRIVER__/$podman_storage_driver}
    podman_storage_block=${podman_storage_block//__PODMAN_STORAGE_OPTIONS__/$storage_options_block}

    local gpu_hardware_section
    case "${GPU_TYPE:-software}" in
        intel)
            gpu_hardware_section=$(cat <<'EOF'
  hardware.graphics = {
    enable = true;
    enable32Bit = true;  # For 32-bit applications
    extraPackages = with pkgs; [
      intel-media-driver  # VAAPI driver for Broadwell+ (>= 5th gen)
      vaapiIntel          # Older VAAPI driver for Haswell and older
      vaapiVdpau
      libvdpau-va-gl
      intel-compute-runtime  # OpenCL support
    ];
  };
EOF
)
            ;;
        amd)
            gpu_hardware_section=$(cat <<'EOF'
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
    extraPackages =
      let
        rocmOpenclPackages =
          lib.optionals (pkgs ? rocm-opencl-icd) [ pkgs.rocm-opencl-icd ]
          ++ lib.optionals (
            pkgs ? rocmPackages
            && builtins.hasAttr "clr" pkgs.rocmPackages
            && builtins.hasAttr "icd" pkgs.rocmPackages.clr
          ) [ pkgs.rocmPackages.clr.icd ];
      in
      (with pkgs; [
        mesa              # Open-source AMD drivers (includes RADV Vulkan)
      ])
      ++ rocmOpenclPackages;
  };
EOF
)
            ;;
        nvidia)
            gpu_hardware_section=$(cat <<'EOF'
  # NVIDIA GPU configuration (auto-detected)
  # Note: NVIDIA on Wayland requires additional setup
  services.xserver.videoDrivers = [ "nvidia" ];
  hardware.nvidia = {
    modesetting.enable = true;  # Required for Wayland
    open = false;  # Use proprietary driver (better performance)
    nvidiaSettings = true;  # Enable nvidia-settings GUI
  };
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
  };
EOF
)
            ;;
        *)
            gpu_hardware_section="# No dedicated GPU configuration required (software rendering)"
            ;;
    esac

    case "${GPU_TYPE:-software}" in
        intel)
            print_success "Applying Intel GPU acceleration block with VA-API and compute runtime packages."
            ;;
        amd)
            print_success "Applying AMD GPU acceleration block with Mesa and ROCm OpenCL support."
            ;;
        nvidia)
            print_success "Applying NVIDIA GPU configuration with proprietary driver and VA-API shim."
            ;;
        software)
            print_info "No dedicated GPU detected; configuration keeps software rendering defaults."
            ;;
        *)
            print_warning "Unrecognized GPU type '${GPU_TYPE:-unknown}'; falling back to software rendering settings."
            ;;
    esac

    local gpu_driver_packages_block="[]"
    case "${GPU_TYPE:-software}" in
        intel)
            gpu_driver_packages_block="(lib.optionals (pkgs ? intel-media-driver) [ intel-media-driver ] ++ lib.optionals (pkgs ? vaapiIntel) [ vaapiIntel ])"
            ;;
        amd)
            gpu_driver_packages_block="(lib.optionals (pkgs ? mesa) [ mesa ] ++ lib.optionals (pkgs ? rocm-opencl-icd) [ pkgs.rocm-opencl-icd ] ++ lib.optionals (pkgs ? rocmPackages && builtins.hasAttr \"clr\" pkgs.rocmPackages && builtins.hasAttr \"icd\" pkgs.rocmPackages.clr) [ pkgs.rocmPackages.clr.icd ])"
            ;;
        nvidia)
            gpu_driver_packages_block="(lib.optionals (pkgs ? nvidia-vaapi-driver) [ nvidia-vaapi-driver ])"
            ;;
    esac

    local gpu_session_variables
    if [[ "${GPU_TYPE:-software}" != "software" && "${GPU_TYPE:-unknown}" != "unknown" && -n "${LIBVA_DRIVER:-}" ]]; then
        local gpu_label="${GPU_TYPE^}"
        gpu_session_variables=$(cat <<EOF

    # Hardware acceleration enabled (auto-detected: ${gpu_label} GPU)
    # VA-API driver: ${LIBVA_DRIVER} for video decode/encode acceleration
    LIBVA_DRIVER_NAME = "${LIBVA_DRIVER}";
    # Enable touch/gesture support for trackpads
    MOZ_USE_XINPUT2 = "1";
EOF
)
    else
        gpu_session_variables=$(cat <<'EOF'

    # No dedicated GPU detected - using software rendering
    # Hardware acceleration disabled
EOF
)
    fi

    local total_ram_value="${TOTAL_RAM_GB:-0}"
    local resume_device_hint="${RESUME_DEVICE_HINT:-}"
    local resume_device_literal=""

    if [[ -n "$resume_device_hint" ]]; then
        resume_device_literal=$(nix_quote_string "$resume_device_hint")
    fi

    local resume_device_directive
    if [[ -n "$resume_device_literal" ]]; then
        resume_device_directive=$(cat <<EOF
    # Resume device reused from previous deployment
    resumeDevice = ${resume_device_literal};
EOF
)
    else
        resume_device_directive=$(cat <<'EOF'
    # Resume device will be detected automatically via hardware-configuration.nix
    resumeDevice = lib.mkDefault "";  # Auto-detected from swapDevices
EOF
)
    fi

    local resume_offset_hint=""
    if [[ "${RESUME_OFFSET_HINT:-}" =~ ^[0-9]+$ && "${RESUME_OFFSET_HINT:-}" -gt 0 ]]; then
        resume_offset_hint="$RESUME_OFFSET_HINT"
        print_info "Preserving resume offset hint: $resume_offset_hint"
    fi

    local resume_offset_line=""
    if [[ -n "$resume_offset_hint" ]]; then
        printf -v resume_offset_line '        "resume_offset=%s"\n' "$resume_offset_hint"
    fi

    local kernel_modules_placeholder=""
    local kernel_modules_header="      # Kernel modules automatically loaded for generated services"
    local -a kernel_module_lines=()

    filter_supported_sysctl_entries() {
        local block="$1"
        local filtered=""

        if [[ -z "$block" ]]; then
            printf '%s' ""
            return
        fi

        while IFS= read -r line || [ -n "$line" ]; do
            local trimmed
            trimmed=$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//')

            if [[ -z "$trimmed" || "$trimmed" == \#* ]]; then
                filtered+="$line"$'\n'
                continue
            fi

            if [[ "$trimmed" == "\""*"\""* ]]; then
                local key="${trimmed#\"}"
                key="${key%%\"*}"
                local path="/proc/sys/${key//./\/}"
                if [[ -e "$path" ]]; then
                    filtered+="$line"$'\n'
                else
                    print_warning "Skipping unsupported sysctl '$key' (no /proc/sys entry present)."
                fi
            else
                filtered+="$line"$'\n'
            fi
        done <<< "$block"

        printf '%s' "$filtered"
    }

    local kernel_sysctl_tunables=""
    local kernel_sysctl_hardening
    kernel_sysctl_hardening=$(cat <<'EOF'

      # Kernel hardening defaults preserved from the deprecated quick-deploy script
      "kernel.dmesg_restrict" = 1;
      "kernel.perf_event_paranoid" = 3;
      "kernel.yama.ptrace_scope" = 1;
      "fs.protected_fifos" = 2;
      "fs.protected_regular" = 2;
      "dev.tty.ldisc_autoload" = 0;
EOF
)
    kernel_sysctl_hardening=$(filter_supported_sysctl_entries "$kernel_sysctl_hardening")

    local kernel_sysctl_network
    kernel_sysctl_network=$(cat <<'EOF'

      # Network stack tuning carried over from the legacy deployment flow
      "net.core.default_qdisc" = "fq";
      "net.core.rmem_default" = 16777216;
      "net.core.wmem_default" = 16777216;
      "net.core.rmem_max" = 134217728;
      "net.core.wmem_max" = 134217728;
      "net.ipv4.tcp_congestion_control" = "bbr";
      "net.ipv4.tcp_low_latency" = 1;
      "net.ipv4.tcp_mtu_probing" = 1;
      "net.ipv4.tcp_no_metrics_save" = 1;
      "net.ipv4.tcp_slow_start_after_idle" = 0;
      "net.ipv4.tcp_fin_timeout" = 15;
      "net.ipv4.tcp_keepalive_time" = 600;
      "net.ipv4.tcp_keepalive_intvl" = 30;
      "net.ipv4.tcp_keepalive_probes" = 5;
      "net.ipv4.ip_local_port_range" = "1024 65535";
      "net.ipv4.conf.all.accept_redirects" = 0;
      "net.ipv4.conf.default.accept_redirects" = 0;
      "net.ipv4.conf.all.send_redirects" = 0;
      "net.ipv6.conf.all.accept_redirects" = 0;
      "net.ipv6.conf.default.accept_redirects" = 0;
EOF
)
    kernel_sysctl_network=$(filter_supported_sysctl_entries "$kernel_sysctl_network")

    kernel_sysctl_tunables="${kernel_sysctl_hardening}${kernel_sysctl_network}"

    print_info "Preserving legacy kernel hardening sysctl overrides."
    print_info "Preserving legacy network performance sysctl overrides."

    local kernel_params_block
    kernel_params_block=$(cat <<EOF
    kernelParams = lib.mkAfter (
      (lib.optional (lib.elem "kvm-amd" config.boot.kernelModules) "amd_pstate=active")
      ++ [
        "nosplit_lock_mitigate"
        "clearcpuid=514"
${resume_offset_line}

        # Quiet boot (cleaner boot messages)
        "quiet"
        "splash"

        # Performance: Disable CPU security mitigations (OPTIONAL - commented for security)
        # WARNING: Only enable on trusted systems where performance > security
        # "mitigations=off"
      ]
    );
EOF
)

    local swap_and_hibernation_block
    local host_swap_limits_block=""
    if [[ "${HOST_SWAP_LIMIT_ENABLED:-false}" == "true" ]]; then
        local swap_limit_value="${HOST_SWAP_LIMIT_VALUE:-}"
        if [[ -z "$swap_limit_value" && "${HOST_SWAP_LIMIT_GB:-}" =~ ^[0-9]+$ ]]; then
            if (( HOST_SWAP_LIMIT_GB <= 0 )); then
                swap_limit_value="infinity"
            else
                swap_limit_value="${HOST_SWAP_LIMIT_GB}G"
            fi
        fi

        if [[ -n "$swap_limit_value" ]]; then
            host_swap_limits_block=$(cat <<EOF

  # Swap accounting + limit for user units.
  # System-wide Manager limit is intentionally omitted to stay compatible
  # across nixpkgs option transitions (systemd.settings.Manager vs extraConfig).

  systemd.user.extraConfig = ''
    DefaultMemoryAccounting=yes
    DefaultMemorySwapMax=${swap_limit_value}
  '';
EOF
)
        fi
    fi
    local hibernation_swap_value="${HIBERNATION_SWAP_SIZE_GB:-$total_ram_value}"
    if [[ "${enable_zswap,,}" == "true" ]]; then
        local swap_device_path="/swapfile.nixos-zswap"
        local swap_device_literal
        swap_device_literal=$(nix_quote_string "$swap_device_path")

        local swap_size_directive
        if [[ "$hibernation_swap_value" =~ ^[0-9]+$ && "$hibernation_swap_value" -gt 0 ]]; then
            local swap_size_mb
            swap_size_mb=$(( hibernation_swap_value * 1024 ))
            printf -v swap_size_directive '      size = %s;  # %sGB target\n' "$swap_size_mb" "$hibernation_swap_value"
        else
            printf -v swap_size_directive '      # size omitted: invalid swap size input (%s)\n' "$hibernation_swap_value"
        fi

        if [[ "${zswap_zpool}" != "zsmalloc" ]]; then
            kernel_module_lines+=(
                "      # Zswap allocator module required for compressed swap"
                "      \"${zswap_zpool}\""
            )
        else
            kernel_module_lines+=(
                "      # Zswap allocator uses built-in zsmalloc backend (no extra modules required)"
            )
        fi

        local kernel_sysctl_memory
        kernel_sysctl_memory=$(cat <<EOF

      # Memory management tunables for swap-backed hibernation (auto-tuned)
      "vm.dirty_ratio" = 10;
      "vm.dirty_background_ratio" = 5;
      "fs.inotify.max_user_watches" = 524288;
      "fs.inotify.max_user_instances" = 512;
      "fs.inotify.max_queued_events" = 32768;
      "kernel.shmmax" = 17179869184;  # 16GB
      "kernel.shmall" = 4194304;      # 16GB in pages (4KB pages)
EOF
)

        kernel_sysctl_memory=$(filter_supported_sysctl_entries "$kernel_sysctl_memory")

        kernel_sysctl_tunables+="$kernel_sysctl_memory"
        print_info "Applying legacy memory management sysctl overrides for zswap-backed hibernation."

        kernel_params_block=$(cat <<EOF
    kernelParams = lib.mkAfter (
      (lib.optional (lib.elem "kvm-amd" config.boot.kernelModules) "amd_pstate=active")
      ++ [
        "nosplit_lock_mitigate"
        "clearcpuid=514"

        # Zswap: Compressed swap cache tuned for ${total_ram_value}GB RAM systems
        "zswap.enabled=1"
        "zswap.compressor=${zswap_compressor}"
        "zswap.max_pool_percent=${zswap_percent}"
        "zswap.zpool=${zswap_zpool}"
${resume_offset_line}

        # Quiet boot (cleaner boot messages)
        "quiet"
        "splash"

        # Performance: Disable CPU security mitigations (OPTIONAL - commented for security)
        # WARNING: Only enable on trusted systems where performance > security
        # "mitigations=off"
      ]
    );
EOF
)

        swap_and_hibernation_block=$(cat <<EOF
  # Declarative swap provisioning for zswap-backed hibernation
  # NixOS manages the lifecycle of the swapfile below on every rebuild.
  # mkForce ensures we replace any swapDevices defined by hardware-configuration.nix,
  # matching the override semantics recommended in the NixOS manual for managing swap.
  swapDevices = lib.mkForce [
    {
      device = ${swap_device_literal};
${swap_size_directive}
      priority = 100;  # Prefer the dedicated hibernation swapfile
    }
  ];

  # Target disk-backed swap capacity: ~${hibernation_swap_value}GB

  # Systemd sleep/hibernate configuration
  systemd.sleep.extraConfig = ''
    # Hibernate after 2 hours of suspend (saves battery)
    HibernateDelaySec=2h
  '';

  # Power Management (for hibernation support)
  powerManagement = {
    enable = true;
    # Allow hibernation if swap is configured
    # Requires: swapDevices with sufficient size (>= RAM size)
  };
EOF
)
        swap_and_hibernation_block+="${host_swap_limits_block}"
    else
        swap_and_hibernation_block=$(cat <<'EOF'
  # Swap configuration is inherited from hardware-configuration.nix
  # Previous deployment did not enable swap-backed hibernation; leaving defaults unchanged.
EOF
)
        swap_and_hibernation_block+="${host_swap_limits_block}"
        print_info "Legacy memory management sysctl overrides skipped (zswap disabled)."
    fi

    if ((${#kernel_module_lines[@]} > 0)); then
        printf -v kernel_modules_placeholder "%s\n" "$kernel_modules_header" "${kernel_module_lines[@]}"
        kernel_modules_placeholder=${kernel_modules_placeholder%$'\n'}
    else
        kernel_modules_placeholder="      # No additional kernel modules configured by the generator"
    fi

    # -----------------------------------------------------------------------
    # Kernel module blacklist: prevent loading drivers for absent hardware.
    # Reduces attack surface and avoids known CVEs in vendor-specific modules
    # (e.g., Huawei/HiSilicon crypto and perf drivers).
    # Users can extend via EXTRA_BLACKLISTED_KERNEL_MODULES in variables.sh.
    # -----------------------------------------------------------------------
    local -a blacklisted_modules=(
        # Huawei/HiSilicon crypto drivers (CVE-2024-42147, CVE-2024-47730)
        "hisi_zip"
        "hisi_hpre"
        "hisi_sec2"
        "hisi_qm"
        # Huawei/HiSilicon perf and network drivers (CVE-2024-38568, CVE-2024-38569)
        "hisi_pcie_pmu"
        "hns3"
        "hns_roce"
        "hclge"
        "hclgevf"
        "hnae3"
        # Huawei/HiSilicon misc
        "hisi_sas_main"
        "hisi_sas_v3_hw"
    )

    # Append user-defined extra blacklist entries if provided
    if [[ -n "${EXTRA_BLACKLISTED_KERNEL_MODULES:-}" ]]; then
        local mod
        for mod in $EXTRA_BLACKLISTED_KERNEL_MODULES; do
            blacklisted_modules+=("$mod")
        done
    fi

    local blacklisted_kernel_modules_block
    if ((${#blacklisted_modules[@]} > 0)); then
        local -a nix_mod_lines=()
        local mod
        for mod in "${blacklisted_modules[@]}"; do
            nix_mod_lines+=("      \"${mod}\"")
        done
        local nix_mod_joined
        printf -v nix_mod_joined '%s\n' "${nix_mod_lines[@]}"
        nix_mod_joined=${nix_mod_joined%$'\n'}
        blacklisted_kernel_modules_block=$(cat <<EOF
    blacklistedKernelModules = [
${nix_mod_joined}
    ];
EOF
)
    else
        blacklisted_kernel_modules_block="    # blacklistedKernelModules: none configured"
    fi

    local -a nix_parallelism_settings
    mapfile -t nix_parallelism_settings < <(determine_nixos_parallelism)
    local nix_max_jobs_value="${nix_parallelism_settings[0]:-auto}"
    local nix_core_limit_value="${nix_parallelism_settings[1]:-0}"
    local nix_throttle_message="${nix_parallelism_settings[2]:-}"

    if [[ "$nix_max_jobs_value" != "auto" && ! "$nix_max_jobs_value" =~ ^-?[0-9]+$ ]]; then
        nix_max_jobs_value="auto"
    fi

    if ! [[ "$nix_core_limit_value" =~ ^-?[0-9]+$ ]]; then
        nix_core_limit_value="0"
    fi

    local nix_max_jobs_literal
    if [[ "$nix_max_jobs_value" == "auto" ]]; then
        nix_max_jobs_literal="\"auto\""
    else
        nix_max_jobs_literal="$nix_max_jobs_value"
    fi

    local nix_cores_literal="$nix_core_limit_value"

    local nix_parallel_comment
    if [[ -n "$nix_throttle_message" ]]; then
        nix_parallel_comment="capped at ${nix_max_jobs_value} job(s) / ${nix_core_limit_value} core(s) for ${total_ram_value}GB RAM"
    else
        nix_parallel_comment="using upstream defaults (auto jobs, 0 cores)"
    fi

    if ! hydrate_primary_user_password_block; then
        print_warning "Automatic password detection failed; prompting for manual configuration."
    fi

    if [[ -z "${USER_PASSWORD_BLOCK:-}" ]]; then
        provision_primary_user_password || true
    fi

    local user_password_block
    if [[ -n "${USER_PASSWORD_BLOCK:-}" ]]; then
        user_password_block="$USER_PASSWORD_BLOCK"
    else
        user_password_block=$'    # (no password directives detected; update manually if required)\n'
    fi

    # Generate ROOT_PASSWORD_BLOCK for emergency/rescue mode access
    # Root uses the same password as the primary user for single-user convenience
    local root_password_block
    if [[ "$user_password_block" =~ hashedPassword[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
        local extracted_hash="${BASH_REMATCH[1]}"
        printf -v root_password_block '    hashedPassword = "%s";\n' "$extracted_hash"
        print_success "Root password synced with primary user for emergency mode access"
    elif [[ "$user_password_block" =~ initialPassword[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
        local extracted_initial="${BASH_REMATCH[1]}"
        printf -v root_password_block '    initialPassword = "%s";\n' "$extracted_initial"
        print_success "Root initial password synced with primary user for emergency mode access"
    else
        # Fallback: Set a minimal emergency password (user should change this)
        root_password_block=$'    # WARNING: No password configured - root access disabled in emergency mode\n    # To enable emergency mode access, add: hashedPassword = "<your-hash>";\n'
        print_warning "No root password configured - emergency/rescue mode access will be limited"
    fi

    if ! ensure_gitea_secrets_ready --noninteractive; then
        return 1
    fi

    if ! render_sops_secrets_file "$BACKUP_DIR" "$BACKUP_TIMESTAMP"; then
        print_error "Failed to prepare encrypted secrets.yaml for sops-nix"
        return 1
    fi

    local gitea_enabled_literal="true"
    if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
        gitea_enabled_literal="false"
    fi

    local gitea_admin_secrets_set
    local gitea_admin_variables_block
    local gitea_admin_service_block

    if [[ "$gitea_enabled_literal" == "true" && "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        gitea_admin_secrets_set=$(cat <<'EOF'
{
    adminPassword = @GITEA_ADMIN_PASSWORD@;
  }
EOF
)
        gitea_admin_variables_block=$(cat <<'EOF'
  giteaAdminUser = @GITEA_ADMIN_USER@;
  giteaAdminEmail = @GITEA_ADMIN_EMAIL@;
  giteaAdminUserPattern = lib.escapeRegex giteaAdminUser;
  giteaAdminBootstrapScript = pkgs.writeShellScript "gitea-admin-bootstrap" ''
    set -euo pipefail

    export HOME=${lib.escapeShellArg giteaStateDir}
    export GITEA_WORK_DIR=${lib.escapeShellArg giteaStateDir}
    export GITEA_CUSTOM=${lib.escapeShellArg ("${giteaStateDir}/custom")}
    export GITEA_APP_INI=${lib.escapeShellArg ("${giteaStateDir}/custom/conf/app.ini")}

    attempts=0
    while true; do
      if output=$(${pkgs.gitea}/bin/gitea admin user list --admin 2>/dev/null); then
        if printf '%s\n' "$output" | ${pkgs.gnugrep}/bin/grep -Eq '(^|[[:space:]])${giteaAdminUserPattern}\\b'; then
          exit 0
        fi
        break
      fi

      attempts=$((attempts + 1))
      if [ "$attempts" -ge 30 ]; then
        echo "gitea-admin-bootstrap: timed out waiting for gitea admin CLI" >&2
        exit 1
      fi
      ${pkgs.coreutils}/bin/sleep 2
    done

    if ! create_output=$(${pkgs.gitea}/bin/gitea admin user create \
      --username ${lib.escapeShellArg giteaAdminUser} \
      --password ${lib.escapeShellArg giteaAdminSecrets.adminPassword} \
      --email ${lib.escapeShellArg giteaAdminEmail} \
      --must-change-password=false \
      --admin 2>&1); then
      create_rc=$?
      if printf '%s\n' "$create_output" | ${pkgs.gnugrep}/bin/grep -qi 'user already exists'; then
        exit 0
      fi
      printf '%s\n' "$create_output" >&2
      exit "$create_rc"
    fi
  '';
EOF
)
        gitea_admin_service_block=$(cat <<'EOF'
  systemd.services.gitea-admin-bootstrap = lib.mkIf giteaEnabled {
    description = "Bootstrap default Gitea administrator";
    wantedBy = [ "multi-user.target" ];
    after = [ "gitea.service" ];
    requires = [ "gitea.service" ];
    serviceConfig = {
      Type = "oneshot";
      User = "gitea";
      Group = "gitea";
      ExecStart = giteaAdminBootstrapScript;
    };
  };
EOF
)
    elif [[ "$gitea_enabled_literal" == "true" ]]; then
        gitea_admin_secrets_set=$(cat <<'EOF'
{
  # Add `adminPassword = "your-strong-password";` to enable declarative admin bootstrapping.
}
EOF
)
        gitea_admin_variables_block=$(cat <<'EOF'
  # Gitea admin bootstrap is disabled by the installer.
  # Uncomment and customize the block below to create an admin automatically.
  # giteaAdminUser = "gitea-admin";
  # giteaAdminEmail = "gitea-admin@example.local";
  # giteaAdminUserPattern = lib.escapeRegex giteaAdminUser;
  # giteaAdminBootstrapScript = pkgs.writeShellScript "gitea-admin-bootstrap" ''
  #   set -euo pipefail
  #
  #   export HOME=${lib.escapeShellArg giteaStateDir}
  #   export GITEA_WORK_DIR=${lib.escapeShellArg giteaStateDir}
  #   export GITEA_CUSTOM=${lib.escapeShellArg ("${giteaStateDir}/custom")}
  #   export GITEA_APP_INI=${lib.escapeShellArg ("${giteaStateDir}/custom/conf/app.ini")}
  #
  #   ${pkgs.gitea}/bin/gitea admin user create \
  #     --username ${lib.escapeShellArg "<gitea-admin>"} \
  #     --password ${lib.escapeShellArg "<replace-with-password>"} \
  #     --email ${lib.escapeShellArg "gitea-admin@example.local"} \
  #     --must-change-password=false \
  #     --admin
  # '';
EOF
)
        gitea_admin_service_block=$(cat <<'EOF'
  # systemd.services.gitea-admin-bootstrap = lib.mkIf giteaEnabled {
  #   description = "Bootstrap default Gitea administrator";
  #   wantedBy = [ "multi-user.target" ];
  #   after = [ "gitea.service" ];
  #   requires = [ "gitea.service" ];
  #   serviceConfig = {
  #     Type = "oneshot";
  #     User = "gitea";
  #     Group = "gitea";
  #     ExecStart = giteaAdminBootstrapScript;
  #   };
  # };
EOF
)
    else
        gitea_admin_secrets_set=$(cat <<'EOF'
{
  # Gitea admin bootstrap disabled because the service is not enabled.
}
EOF
)
        gitea_admin_variables_block=$(cat <<'EOF'
  # Gitea service is disabled. Enable it to configure admin bootstrap values.
EOF
)
        gitea_admin_service_block=$(cat <<'EOF'
  # Gitea service disabled; no admin bootstrap unit generated.
EOF
)
    fi

    local gitea_admin_user_literal=""
    local gitea_admin_email_literal=""
    local gitea_admin_password_literal=""

    if [[ "$gitea_enabled_literal" == "true" && "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        gitea_admin_user_literal=$(nix_quote_string "$GITEA_ADMIN_USER")
        gitea_admin_email_literal=$(nix_quote_string "$GITEA_ADMIN_EMAIL")
        gitea_admin_password_literal=$(nix_quote_string "$GITEA_ADMIN_PASSWORD")
    fi

    replace_placeholder "$SYSTEM_CONFIG_FILE" "@SCRIPT_VERSION@" "$SCRIPT_VERSION"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GENERATED_AT@" "$generated_at"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@HOSTNAME@" "$HOSTNAME"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@USER@" "$primary_user"
    # @CPU_VENDOR_LABEL@, @INITRD_KERNEL_MODULES@, @KERNEL_MODULES_PLACEHOLDER@,
    # @KERNEL_SYSCTL_TUNABLES@, @BOOT_KERNEL_PARAMETERS_BLOCK@, @MICROCODE_SECTION@,
    # @BINARY_CACHE_SETTINGS@, @GPU_HARDWARE_SECTION@, @GPU_SESSION_VARIABLES@,
    # @GPU_DRIVER_PACKAGES@: removed from templates/configuration.nix.
    # Hardware configuration is now fully declarative via nix/modules/hardware/.
    # CPU/GPU/storage/RAM modules are loaded by the flake through facts.nix
    # (generated at Phase 1 by lib/hardware-detect.sh::detect_and_write_hardware_facts).
    #
    # @BLACKLISTED_KERNEL_MODULES_BLOCK@: retained — user-extensible via
    # EXTRA_BLACKLISTED_KERNEL_MODULES in config/variables.sh.
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@BLACKLISTED_KERNEL_MODULES_BLOCK@" "$blacklisted_kernel_modules_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@RESUME_DEVICE_DIRECTIVE@" "$resume_device_directive"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GLF_OS_DEFINITIONS@" "$glf_os_definitions"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GLF_GAMING_STACK_SECTION@" "$glf_gaming_stack_section"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@FLATPAK_MANAGED_PACKAGES@" "$flatpak_packages_block"
    # @LACT_SERVICE_BLOCK@: removed — handled by nix/modules/hardware/gpu/amd.nix
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@PODMAN_STORAGE_BLOCK@" "$podman_storage_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@SELECTED_TIMEZONE@" "$TIMEZONE"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@CURRENT_LOCALE@" "$LOCALE"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@NIXOS_VERSION@" "$NIXOS_VERSION"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@STATE_VERSION@" "$STATE_VERSION"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@SWAP_AND_HIBERNATION_BLOCK@" "$swap_and_hibernation_block"
    # @NIX_MAX_JOBS@, @NIX_BUILD_CORES@, @NIX_PARALLEL_COMMENT@: removed.
    # Adaptive Nix build parallelism is now set by nix/modules/hardware/ram-tuning.nix.
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@USERS_MUTABLE@" "${USERS_MUTABLE_SETTING:-true}"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@USER_PASSWORD_BLOCK@" "$user_password_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@ROOT_PASSWORD_BLOCK@" "$root_password_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ENABLE_FLAG@" "$gitea_enabled_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_SECRETS_SET@" "$gitea_admin_secrets_set"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_VARIABLES_BLOCK@" "$gitea_admin_variables_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_SERVICE_BLOCK@" "$gitea_admin_service_block"

    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_SECRET_KEY@" "$(nix_quote_string "$GITEA_SECRET_KEY")"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_INTERNAL_TOKEN@" "$(nix_quote_string "$GITEA_INTERNAL_TOKEN")"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_LFS_JWT_SECRET@" "$(nix_quote_string "$GITEA_LFS_JWT_SECRET")"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_JWT_SECRET@" "$(nix_quote_string "$GITEA_JWT_SECRET")"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_PASSWORD@" "$gitea_admin_password_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_USER@" "$gitea_admin_user_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GITEA_ADMIN_EMAIL@" "$gitea_admin_email_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "LOCAL_AI_STACK_ENABLED_PLACEHOLDER" "${LOCAL_AI_STACK_ENABLED:-false}"

    if ! nix_verify_no_placeholders "$SYSTEM_CONFIG_FILE" "configuration.nix"; then
        return 1
    fi

    print_success "Generated configuration.nix"
    echo ""

    # ========================================================================
    # Replace Placeholders in NixOS Improvements Modules
    # ========================================================================
    # Replace user-specific placeholders in improvement modules if they exist
    local improvements_virt_file="/etc/nixos/nixos-improvements/virtualization.nix"
    if [[ -f "$improvements_virt_file" ]]; then
        print_info "Customizing virtualization module for user: $primary_user"
        replace_placeholder "$improvements_virt_file" "@USER@" "$primary_user"
    fi

    # ========================================================================
    # Generate Flake Configuration
    # ========================================================================
    print_info "Generating flake configuration..."

    local FLAKE_TEMPLATE="$TEMPLATE_DIR/flake.nix"
    if [[ ! -f "$FLAKE_TEMPLATE" ]]; then
        print_error "Flake template not found: $FLAKE_TEMPLATE"
        return 1
    fi

    if ! cp "$FLAKE_TEMPLATE" "$FLAKE_FILE"; then
        print_error "Failed to copy flake template"
        return 1
    fi

    # Replace flake placeholders
    replace_placeholder "$FLAKE_FILE" "NIXPKGS_CHANNEL_PLACEHOLDER" "$NIXOS_CHANNEL_NAME"
    replace_placeholder "$FLAKE_FILE" "HM_CHANNEL_PLACEHOLDER" "$HM_CHANNEL_NAME"
    replace_placeholder "$FLAKE_FILE" "HOSTNAME_PLACEHOLDER" "$HOSTNAME"
    replace_placeholder "$FLAKE_FILE" "HOME_USERNAME_PLACEHOLDER" "$USER"
    replace_placeholder "$FLAKE_FILE" "SYSTEM_PLACEHOLDER" "$SYSTEM_ARCH"

    if ! nix_verify_no_placeholders "$FLAKE_FILE" "flake.nix" '\\b[A-Z0-9_]*PLACEHOLDER\\b'; then
        return 1
    fi

    print_success "Generated flake.nix"

    if ! seed_flake_lock_from_template "$BACKUP_DIR" "$BACKUP_TIMESTAMP"; then
        return 1
    fi

    # Validate that all flake inputs are locked (e.g., sops-nix, nix-vscode-extensions)
    # Missing lock entries cause silent failures during home-manager switch
    if ! validate_flake_lock_inputs "$HM_CONFIG_DIR"; then
        print_warning "Some flake inputs could not be locked — deployment will attempt to continue"
    fi

    echo ""

    print_success "NixOS system configuration generated successfully"
    print_info "Location: $SYSTEM_CONFIG_FILE"
    print_info "Flake: $FLAKE_FILE"
    echo ""

    return 0
}

# ============================================================================
# Create Home Manager Configuration
# ============================================================================
# Purpose: Generate home-manager configuration from template
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
create_home_manager_config() {
    normalize_dotfiles_paths
    print_section "Creating Home Manager Configuration"

    # ========================================================================
    # Detect Versions
    # ========================================================================
    local NIXOS_CHANNEL
    local HM_CHANNEL
    NIXOS_CHANNEL=$(sudo nix-channel --list 2>/dev/null | grep '^nixos' | awk '{print $2}')
    HM_CHANNEL=$(nix-channel --list 2>/dev/null | grep 'home-manager' | awk '{print $2}')
    local STATE_VERSION

    # Extract version from nixos channel
    if [[ "$NIXOS_CHANNEL" =~ nixos-([0-9]+\.[0-9]+) ]]; then
        STATE_VERSION="${BASH_REMATCH[1]}"
        print_info "Detected stateVersion: $STATE_VERSION"
    elif [[ "$NIXOS_CHANNEL" == *"unstable"* ]]; then
        STATE_VERSION=$(derive_system_release_version)
        print_info "Using unstable channel, stateVersion: $STATE_VERSION"
    else
        STATE_VERSION=$(derive_system_release_version)
        print_warning "Using system version: $STATE_VERSION"
    fi

    local NIXOS_CHANNEL_NAME="${SYNCHRONIZED_NIXOS_CHANNEL:-$(basename "$NIXOS_CHANNEL" 2>/dev/null)}"
    if [[ -z "$NIXOS_CHANNEL_NAME" ]]; then
        NIXOS_CHANNEL_NAME="nixos-${STATE_VERSION}"
    fi

    local selected_state="${SELECTED_NIXOS_VERSION:-$STATE_VERSION}"
    if [[ "$selected_state" != "unstable" ]]; then
        local requested_state_version
        requested_state_version=$(normalize_release_version "$selected_state")
        STATE_VERSION=$(resolve_nixos_release_version "$selected_state")
        emit_nixos_channel_fallback_notice
        if [[ "$requested_state_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
            STATE_VERSION="$requested_state_version"
        fi
    fi
    local HM_CHANNEL_NAME="${HOME_MANAGER_CHANNEL_REF:-$(normalize_channel_name "$HM_CHANNEL")}"
    local resolved_hm_version=""

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        resolved_hm_version=$(resolve_home_manager_release_version "$STATE_VERSION")
        HM_CHANNEL_NAME="release-${resolved_hm_version}"
    elif [[ "$HM_CHANNEL_NAME" =~ ^release-([0-9]+\.[0-9]+)$ ]]; then
        resolved_hm_version=$(resolve_home_manager_release_version "${BASH_REMATCH[1]}")
        HM_CHANNEL_NAME="release-${resolved_hm_version}"
    fi
    emit_home_manager_fallback_notice

    print_info "NixOS channel: $NIXOS_CHANNEL_NAME"
    print_info "Home-manager channel: $HM_CHANNEL_NAME"
    echo ""

    # ========================================================================
    # Ensure Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating home-manager directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR
        PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
        if [[ ! -d "$PARENT_DIR" ]]; then
            if ! mkdir -p "$PARENT_DIR"; then
                print_error "Failed to create parent directory: $PARENT_DIR"
                return 1
            fi
        fi

        # Create the config directory
        if ! mkdir -p "$HM_CONFIG_DIR"; then
            print_error "Failed to create directory: $HM_CONFIG_DIR"
            return 1
        fi

        # Set ownership to current user
        # Use sudo if we're running as root but need to set ownership to a non-root user
        if [[ "$EUID" -eq 0 ]] && [[ -n "$SUDO_USER" ]]; then
            # Running with sudo - set ownership to the original user
            chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        elif [[ "$EUID" -eq 0 ]]; then
            # Running as root without sudo - set to PRIMARY_USER
            chown -R "$PRIMARY_USER:$(id -gn "$PRIMARY_USER" 2>/dev/null || echo "users")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        fi
        # If running as normal user, ownership is already correct from mkdir

        print_success "Created home-manager directory"
    fi

    # ========================================================================
    # Backup Existing Configuration
    # ========================================================================
    local BACKUP_TIMESTAMP
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local BACKUP_DIR="${HM_BACKUP_DIR}"
    backup_generated_file "$HOME_MANAGER_FILE" "home.nix" "$BACKUP_DIR" "$BACKUP_TIMESTAMP" || true

    # ========================================================================
    # Copy Template
    # ========================================================================
    local TEMPLATE_DIR="${SCRIPT_DIR}/templates"
    local HOME_TEMPLATE="$TEMPLATE_DIR/home.nix"

    if [[ ! -f "$HOME_TEMPLATE" ]]; then
        print_error "Home template not found: $HOME_TEMPLATE"
        return 1
    fi

    print_info "Creating home.nix from template..."
    print_info "  Source: $HOME_TEMPLATE"
    print_info "  Destination: $HOME_MANAGER_FILE"

    if ! cp "$HOME_TEMPLATE" "$HOME_MANAGER_FILE"; then
        print_error "Failed to copy home template"
        print_error "  Check if source exists: $([ -f "$HOME_TEMPLATE" ] && echo 'YES' || echo 'NO')"
        print_error "  Check if destination dir exists: $([ -d "$(dirname "$HOME_MANAGER_FILE")" ] && echo 'YES' || echo 'NO')"
        print_error "  Check if destination dir is writable: $([ -w "$(dirname "$HOME_MANAGER_FILE")" ] && echo 'YES' || echo 'NO')"
        return 1
    fi

    # Verify the file was actually created
    if [[ ! -f "$HOME_MANAGER_FILE" ]]; then
        print_error "home.nix was not created at: $HOME_MANAGER_FILE"
        return 1
    fi

    # ========================================================================
    # Deploy Support Modules
    # ========================================================================
    local support_module="python-overrides.nix"
    print_info "Syncing $support_module into Home Manager workspace..."
    if ! sync_support_module "$support_module" "$TEMPLATE_DIR" "$HM_CONFIG_DIR" "$BACKUP_DIR" "$BACKUP_TIMESTAMP"; then
        return 1
    fi

    # Ensure the Powerlevel10k setup wizard script is present for home.nix source reference.
    local p10k_source="${SCRIPT_DIR}/scripts/p10k-setup-wizard.sh"
    local p10k_destination="${HM_CONFIG_DIR}/p10k-setup-wizard.sh"
    if [[ -f "$p10k_source" ]]; then
        if safe_copy_file "$p10k_source" "$p10k_destination"; then
            chmod +x "$p10k_destination" 2>/dev/null || true
            safe_chown_user_dir "$p10k_destination" || true
            print_success "Synced p10k-setup-wizard.sh into Home Manager workspace"
        else
            print_warning "Failed to sync p10k-setup-wizard.sh to $HM_CONFIG_DIR (home.nix may fail to evaluate)"
        fi
    else
        print_warning "p10k-setup-wizard.sh not found at $p10k_source (home.nix will skip it if optional)"
    fi

    # ========================================================================
    # Replace Placeholders
    # ========================================================================
    local TEMPLATE_HASH
    TEMPLATE_HASH=$(echo -n "AIDB-v4.0-packages-v${SCRIPT_VERSION:-4.0.0}" | sha256sum | cut -d' ' -f1 | cut -c1-16)
    local DEFAULT_EDITOR="${DEFAULT_EDITOR:-nano}"

    local enable_gaming_value
    enable_gaming_value=$(printf '%s' "${ENABLE_GAMING_STACK:-true}" | tr '[:upper:]' '[:lower:]')
    local gaming_stack_enabled=false
    case "$enable_gaming_value" in
        true|1|yes|on)
            gaming_stack_enabled=true
            ;;
    esac

    local gaming_stack_enabled_literal="false"
    if [[ "$gaming_stack_enabled" == true ]]; then
        gaming_stack_enabled_literal="true"
    fi

    resolve_mangohud_preferences "$gaming_stack_enabled"
    local mangohud_profile="$RESOLVED_MANGOHUD_PROFILE"

    # GPU monitoring packages
    local GPU_MONITORING_PACKAGES="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES="[ radeontop amdgpu_top ]"
    elif [[ "$GPU_TYPE" == "nvidia" ]]; then
        GPU_MONITORING_PACKAGES="[ nvtop ]"
    fi

    local mangohud_definition
    mangohud_definition=$(generate_mangohud_nix_definitions)
    local cosmic_blacklist_block
    cosmic_blacklist_block=$(render_cosmic_blacklist_block)
    mangohud_definition="${mangohud_definition//__MANGOHUD_PROFILE__/$mangohud_profile}"
    mangohud_definition="${mangohud_definition//__COSMIC_BLACKLIST_ENTRIES__/$cosmic_blacklist_block}"

    local glf_home_definitions
    glf_home_definitions=$(cat <<EOF
${mangohud_definition}
  glfLutrisWithGtk =
    if ${gaming_stack_enabled_literal} && pkgs ? lutris then
      pkgs.lutris.override { extraLibraries = p: [ p.libadwaita p.gtk4 ]; }
    else
      null;
  glfGamingPackages =
    if ${gaming_stack_enabled_literal} then
      (
        lib.optionals (glfLutrisWithGtk != null) [ glfLutrisWithGtk ]
        # Heroic is currently excluded from defaults because the electron build in
        # nixos-25.05 is marked insecure and breaks evaluation.
        ++ lib.optionals (pkgs ? joystickwake) [ pkgs.joystickwake ]
        ++ lib.optionals (pkgs ? mangohud) [ pkgs.mangohud ]
        ++ lib.optionals (pkgs ? mesa-demos) [ pkgs.mesa-demos ]
        ++ lib.optionals (pkgs ? oversteer) [ pkgs.oversteer ]
        ++ lib.optionals (builtins.hasAttr "umu-launcher" pkgs) [ pkgs."umu-launcher" ]
        ++ lib.optionals (pkgs ? wineWowPackages && pkgs.wineWowPackages ? staging)
          [ pkgs.wineWowPackages.staging ]
        ++ lib.optionals (pkgs ? winetricks) [ pkgs.winetricks ]
      )
    else
      [];
  glfSteamPackage =
    if ${gaming_stack_enabled_literal} && pkgs ? steam then
      pkgs.steam.override {
        extraEnv = {
          MANGOHUD = if glfMangoHudInjectsIntoApps then "1" else "0";
          OBS_VKCAPTURE = "1";
        };
      }
    else if pkgs ? steam then
      pkgs.steam
    else
      null;
  glfSteamCompatPackages =
    if ${gaming_stack_enabled_literal} then
      lib.optionals (pkgs ? proton-ge-bin) [ pkgs.proton-ge-bin ]
    else
      [];
  glfSystemUtilities =
    if ${gaming_stack_enabled_literal} then
      (
        lib.optionals (pkgs ? exfatprogs) [ pkgs.exfatprogs ]
        ++ lib.optionals (pkgs ? fastfetch) [ pkgs.fastfetch ]
        ++ lib.optionals (pkgs ? ffmpeg) [ pkgs.ffmpeg ]
        ++ lib.optionals (pkgs ? ffmpegthumbnailer) [ pkgs.ffmpegthumbnailer ]
        ++ lib.optionals (pkgs ? libva-utils) [ pkgs.libva-utils ]
        ++ lib.optionals (pkgs ? usbutils) [ pkgs.usbutils ]
        ++ lib.optionals (pkgs ? hunspell) [ pkgs.hunspell ]
        ++ lib.optionals (
          pkgs ? hunspellDicts && builtins.hasAttr "fr-any" pkgs.hunspellDicts
        ) [ pkgs.hunspellDicts.fr-any ]
        ++ lib.optionals (pkgs ? hyphen) [ pkgs.hyphen ]
        ++ lib.optionals (
          pkgs ? texlivePackages
          && builtins.hasAttr "hyphen-french" pkgs.texlivePackages
        ) [ pkgs.texlivePackages.hyphen-french ]
      )
    else
      lib.optionals (pkgs ? mangohud) [ pkgs.mangohud ];
EOF
)

    local flatpak_packages_block=""
    local selected_flatpak_profile="${SELECTED_FLATPAK_PROFILE:-${DEFAULT_FLATPAK_PROFILE:-core}}"
    local engineering_tools_expr="engineeringToolsPackages"

    # Map Flatpak profiles to an engineering environment profile:
    # - core / ai_workstation → full engineering toolchain
    # - minimal               → slim (no heavy PCB/CAD/IC tools by default)
    case "$selected_flatpak_profile" in
        minimal)
            engineering_tools_expr="[]"
            ;;
        *)
            engineering_tools_expr="engineeringToolsPackages"
            ;;
    esac
    if (( ${#DEFAULT_FLATPAK_APPS[@]} > 0 )); then
        flatpak_packages_block=$'  # Flatpak applications managed by profile: '"${selected_flatpak_profile}"$'\n'
        flatpak_packages_block+=$'  flathubPackages = [\n'
        local flatpak_app_id
        for flatpak_app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
            flatpak_packages_block+=$'    '"\"${flatpak_app_id}\""$'\n'
        done
        flatpak_packages_block+=$'  ];\n'
    else
        flatpak_packages_block=$'  # Selected Flatpak profile does not provision GUI applications.\n  flathubPackages = [];\n'
    fi

    print_info "Customizing home.nix..."

    if ! ensure_gitea_secrets_ready --noninteractive; then
        return 1
    fi

    # NOTE: build_rootless_podman_storage_block() is no longer used.
    # Podman storage configuration is now defined directly in templates/home.nix
    # within the services.podman block to avoid duplicate attribute errors.
    # build_rootless_podman_storage_block

    local git_user_settings_block="{ }"
    if [[ -n "${GIT_USER_NAME:-}" && -n "${GIT_USER_EMAIL:-}" ]]; then
        local git_user_name_literal
        local git_user_email_literal
        git_user_name_literal=$(nix_quote_string "$GIT_USER_NAME")
        git_user_email_literal=$(nix_quote_string "$GIT_USER_EMAIL")
        git_user_settings_block=$(cat <<EOF
{
        user = {
          name = ${git_user_name_literal};
          email = ${git_user_email_literal};
        };
      }
EOF
)
    fi

    local huggingface_model_id_default="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    local huggingface_model_id="${HUGGINGFACE_MODEL_ID:-$huggingface_model_id_default}"
    local huggingface_scout_model_id_default="meta-llama/Llama-4-Scout-17B-16E"
    local huggingface_scout_model_id="${HUGGINGFACE_SCOUT_MODEL_ID:-$huggingface_scout_model_id_default}"
    local huggingface_tgi_endpoint_default="http://127.0.0.1:8000"
    local huggingface_tgi_endpoint="${HUGGINGFACE_TGI_ENDPOINT:-$huggingface_tgi_endpoint_default}"
    local huggingface_scout_tgi_endpoint_default="http://127.0.0.1:8001"
    local huggingface_scout_tgi_endpoint="${HUGGINGFACE_SCOUT_TGI_ENDPOINT:-$huggingface_scout_tgi_endpoint_default}"
    local huggingface_tgi_container_endpoint_default="http://host.containers.internal:8000"
    local huggingface_tgi_container_endpoint="${HUGGINGFACE_TGI_CONTAINER_ENDPOINT:-$huggingface_tgi_container_endpoint_default}"

    replace_placeholder "$HOME_MANAGER_FILE" "VERSIONPLACEHOLDER" "${SCRIPT_VERSION:-4.0.0}"
    replace_placeholder "$HOME_MANAGER_FILE" "HASHPLACEHOLDER" "$TEMPLATE_HASH"
    replace_placeholder "$HOME_MANAGER_FILE" "HOMEUSERNAME" "$USER"
    replace_placeholder "$HOME_MANAGER_FILE" "HOMEDIR" "$HOME"
    replace_placeholder "$HOME_MANAGER_FILE" "STATEVERSION_PLACEHOLDER" "$STATE_VERSION"
    replace_placeholder "$HOME_MANAGER_FILE" "@GPU_MONITORING_PACKAGES@" "$GPU_MONITORING_PACKAGES"
    replace_placeholder "$HOME_MANAGER_FILE" "@GLF_HOME_DEFINITIONS@" "$glf_home_definitions"
    replace_placeholder "$HOME_MANAGER_FILE" "@FLATPAK_MANAGED_PACKAGES@" "$flatpak_packages_block"
    replace_placeholder "$HOME_MANAGER_FILE" "ENGINEERING_TOOLS_PLACEHOLDER" "$engineering_tools_expr"
    # NOTE: @PODMAN_ROOTLESS_STORAGE@ placeholder removed from template to avoid duplicate services.podman
    # replace_placeholder "$HOME_MANAGER_FILE" "@PODMAN_ROOTLESS_STORAGE@" "${PODMAN_ROOTLESS_STORAGE_BLOCK:-}"
    replace_placeholder "$HOME_MANAGER_FILE" "GIT_USER_SETTINGS_PLACEHOLDER" "$git_user_settings_block"
    replace_placeholder "$HOME_MANAGER_FILE" "LOCAL_AI_STACK_ENABLED_PLACEHOLDER" "${LOCAL_AI_STACK_ENABLED:-false}"
    replace_placeholder "$HOME_MANAGER_FILE" "PYTHON_PREFER_PY314_PLACEHOLDER" "${PYTHON_PREFER_PY314:-false}"
    replace_placeholder "$HOME_MANAGER_FILE" "LLM_BACKEND_PLACEHOLDER" "$(nix_quote_string "${LLM_BACKEND:-llama_cpp}")"
    replace_placeholder "$HOME_MANAGER_FILE" "LLM_MODELS_PLACEHOLDER" "$(nix_quote_string "${LLM_MODELS:-qwen3-4b,sentence-transformers/all-MiniLM-L6-v2}")"
    replace_placeholder "$HOME_MANAGER_FILE" "NIXOS_QUICK_DEPLOY_ROOT_PLACEHOLDER" "$SCRIPT_DIR"
    replace_placeholder "$HOME_MANAGER_FILE" "HUGGINGFACE_MODEL_ID_PLACEHOLDER" "$(nix_quote_string "$huggingface_model_id")"
    replace_placeholder "$HOME_MANAGER_FILE" "HUGGINGFACE_SCOUT_MODEL_ID_PLACEHOLDER" "$(nix_quote_string "$huggingface_scout_model_id")"
    replace_placeholder "$HOME_MANAGER_FILE" "HUGGINGFACE_TGI_ENDPOINT_PLACEHOLDER" "$(nix_quote_string "$huggingface_tgi_endpoint")"
    replace_placeholder "$HOME_MANAGER_FILE" "HUGGINGFACE_SCOUT_TGI_ENDPOINT_PLACEHOLDER" "$(nix_quote_string "$huggingface_scout_tgi_endpoint")"
    replace_placeholder "$HOME_MANAGER_FILE" "HUGGINGFACE_TGI_CONTAINER_ENDPOINT_PLACEHOLDER" "$(nix_quote_string "$huggingface_tgi_container_endpoint")"
    replace_placeholder "$HOME_MANAGER_FILE" "DEFAULTEDITOR" "$DEFAULT_EDITOR"

    local HOME_HOSTNAME
    HOME_HOSTNAME=$(hostname)
    replace_placeholder "$HOME_MANAGER_FILE" "@HOSTNAME@" "$HOME_HOSTNAME"
    replace_placeholder "$HOME_MANAGER_FILE" "@GITEA_SECRET_KEY@" "$(nix_quote_string "$GITEA_SECRET_KEY")"
    replace_placeholder "$HOME_MANAGER_FILE" "@GITEA_INTERNAL_TOKEN@" "$(nix_quote_string "$GITEA_INTERNAL_TOKEN")"
    replace_placeholder "$HOME_MANAGER_FILE" "@GITEA_LFS_JWT_SECRET@" "$(nix_quote_string "$GITEA_LFS_JWT_SECRET")"
    replace_placeholder "$HOME_MANAGER_FILE" "@GITEA_JWT_SECRET@" "$(nix_quote_string "$GITEA_JWT_SECRET")"

    if ! nix_verify_no_placeholders "$HOME_MANAGER_FILE" "home.nix" '\\b[A-Z0-9_]*PLACEHOLDER\\b' '\\b(HOMEUSERNAME|HOMEDIR)\\b'; then
        return 1
    fi

    # Ensure flake.nix is updated if it exists (may have been created by generate_nixos_system_config)
    if [[ -f "$FLAKE_FILE" ]]; then
        replace_placeholder "$FLAKE_FILE" "HOME_USERNAME_PLACEHOLDER" "$USER"
        if ! nix_verify_no_placeholders "$FLAKE_FILE" "flake.nix" '\\b[A-Z0-9_]*PLACEHOLDER\\b'; then
            return 1
        fi
        print_success "Updated flake.nix with username"
    fi

    # ========================================================================
    # Final Verification
    # ========================================================================
    if [[ ! -f "$HOME_MANAGER_FILE" ]]; then
        print_error "VERIFICATION FAILED: home.nix does not exist after creation"
        print_error "Expected location: $HOME_MANAGER_FILE"
        return 1
    fi

    # Check file is readable
    if [[ ! -r "$HOME_MANAGER_FILE" ]]; then
        print_error "VERIFICATION FAILED: home.nix exists but is not readable"
        return 1
    fi

    # Check file has content
    local file_size
    file_size=$(stat -c%s "$HOME_MANAGER_FILE" 2>/dev/null || echo "0")
    if [[ "$file_size" -eq 0 ]]; then
        print_error "VERIFICATION FAILED: home.nix is empty"
        return 1
    fi

    print_success "Created home.nix"
    print_info "Location: $HOME_MANAGER_FILE"
    print_info "File size: $file_size bytes"
    echo ""

    ensure_flake_git_tracking

    return 0
}

# ============================================================================
# Materialize Hardware Configuration
# ============================================================================
# Purpose: Generate hardware-configuration.nix
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
materialize_hardware_configuration() {
    local HARDWARE_CONFIG="${HARDWARE_CONFIG_FILE:-$HM_CONFIG_DIR/hardware-configuration.nix}"

    # Check if already exists
    if [[ -f "$HARDWARE_CONFIG" ]]; then
        if ! sanitize_hardware_configuration "$HARDWARE_CONFIG"; then
            return 1
        fi
        print_success "Hardware configuration already exists"
        return 0
    fi

    # Generate using nixos-generate-config
    print_info "Generating hardware configuration..."
    local TEMP_DIR
    TEMP_DIR=$(mktemp -d)

    if sudo nixos-generate-config --dir "$TEMP_DIR" --show-hardware-config \
        > >(tee "$HARDWARE_CONFIG") 2>/dev/null; then
        safe_chown_user_dir "$HARDWARE_CONFIG"
        if ! sanitize_hardware_configuration "$HARDWARE_CONFIG"; then
            rm -rf "$TEMP_DIR"
            return 1
        fi
        print_success "Generated hardware-configuration.nix"
        rm -rf "$TEMP_DIR"
        return 0
    else
        print_warning "Could not generate hardware configuration"
        rm -rf "$TEMP_DIR"
        return 1
    fi
}

# ============================================================================
# Validate System Build Stage
# ============================================================================
# Purpose: Perform dry-run build to validate configuration
# Returns:
#   0 - Success (validation passed or warnings only)
#   1 - Failure (critical errors)
# ============================================================================
validate_system_build_stage() {
    normalize_dotfiles_paths
    print_section "Validating Configuration"

    local target_host
    target_host=$(hostname)
    local tmp_dir="${TMP_DIR:-/tmp}"
    local log_path="${tmp_dir}/nixos-rebuild-dry-build.log"

    if ! ensure_flake_workspace; then
        print_error "Unable to prepare Home Manager flake workspace at $HM_CONFIG_DIR"
        print_info "Phase 3 (Configuration Generation) must complete successfully before validation."
        echo ""
        return 1
    fi

    if ! verify_home_manager_flake_ready; then
        echo ""
        return 1
    fi

    print_info "Performing dry-run build validation..."
    print_info "This checks for syntax errors and missing dependencies"

    local -a nixos_rebuild_opts=()
    if declare -F activate_build_acceleration_context >/dev/null 2>&1; then
        activate_build_acceleration_context
    fi

    if declare -F build_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t nixos_rebuild_opts < <(build_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
    fi

    local dry_build_display="sudo nixos-rebuild dry-build --flake \"$HM_CONFIG_DIR#$target_host\""
    if (( ${#nixos_rebuild_opts[@]} > 0 )); then
        dry_build_display+=" ${nixos_rebuild_opts[*]}"
    fi

    print_info "Command: $dry_build_display"
    echo ""

    if declare -F describe_binary_cache_usage >/dev/null 2>&1; then
        describe_binary_cache_usage "nixos-rebuild dry-build"
    fi

    if declare -F describe_remote_build_context >/dev/null 2>&1; then
        describe_remote_build_context
    fi

    # Run dry-build (doesn't actually build, just evaluates)
    if sudo nixos-rebuild dry-build --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" \
        > >(tee "$log_path") 2>&1; then
        print_success "Configuration validation passed!"
        print_info "Log saved to: $log_path"
        echo ""
        return 0
    else
        local exit_code=$?
        print_warning "Validation had issues (exit code: $exit_code)"
        print_info "Log saved to: $log_path"
        print_info "Review the log for details"
        echo ""

        if [[ ! -d "$HM_CONFIG_DIR" ]]; then
            print_error "Home Manager flake directory is missing: $HM_CONFIG_DIR"
            print_info "Run Phase 3 to regenerate the configuration or restore your dotfiles."
        elif [[ ! -f "$HM_CONFIG_DIR/flake.nix" ]]; then
            print_error "flake.nix is missing from: $HM_CONFIG_DIR"
            print_info "Regenerate the configuration with Phase 3 or restore from backup."
        elif [[ ! -f "$HM_CONFIG_DIR/home.nix" ]]; then
            print_error "home.nix is missing from: $HM_CONFIG_DIR"
            print_info "Regenerate the configuration with Phase 3 or restore from backup."
        fi

        # Check if it's a critical error or just warnings
        if grep -qi "error:" "$log_path"; then
            print_error "Critical errors found in configuration"
            print_info "Please fix the errors before proceeding"
            return 1
        else
            print_warning "Warnings found but no critical errors"
            print_info "Proceeding with deployment"
            return 0
        fi
    fi
}

# ========================================================================
# Deploy MCP Configuration
# ========================================================================
deploy_mcp_configuration() {
    print_section "Deploying MCP Server Configuration"
    
    local mcp_config_dir="$HOME/.mcp"
    local mcp_template="$TEMPLATE_DIR/mcp-config-template.json"
    local mcp_config="$mcp_config_dir/config.json"
    
    # Create MCP config directory
    if ! mkdir -p "$mcp_config_dir"; then
        print_error "Failed to create MCP config directory"
        return 1
    fi
    
    # Copy template
    if [[ -f "$mcp_template" ]]; then
        print_info "Deploying MCP configuration..."
        
        # Replace placeholder with current date
        sed "s/@DEPLOYMENT_DATE@/$(date +%Y-%m-%d)/g" "$mcp_template" > "$mcp_config"
        
        # Create symlink for Claude Code
        local claude_mcp_config="$HOME/.config/claude/mcp.json"
        mkdir -p "$(dirname "$claude_mcp_config")"
        
        if [[ -L "$claude_mcp_config" ]] || [[ -f "$claude_mcp_config" ]]; then
            print_info "Backing up existing Claude MCP config..."
            mv "$claude_mcp_config" "${claude_mcp_config}.backup-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
        fi
        
        ln -sf "$mcp_config" "$claude_mcp_config"
        
        print_success "MCP configuration deployed"
        print_detail "Config: ~/.mcp/config.json"
        print_detail "Symlink: ~/.config/claude/mcp.json -> ~/.mcp/config.json"
    else
        print_warning "MCP template not found (optional)"
    fi
}
