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

# Replace placeholder tokens in template files using a Python helper to safely
# handle multi-line replacements.
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

    PLACEHOLDER_VALUE="$replacement" python3 - "$target_file" "$placeholder" <<'PY'
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

# Binary cache helpers keep runtime tooling and rendered configuration aligned.
get_binary_cache_sources() {
    local -a caches=(
        "https://cache.nixos.org"
        "https://nix-community.cachix.org"
        "https://devenv.cachix.org"
    )

    if [[ "${GPU_TYPE:-}" == "nvidia" ]]; then
        caches+=("https://cuda-maintainers.cachix.org")
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

    printf '%s\n' "${keys[@]}"
}

determine_nixos_parallelism() {
    local detected_ram="${TOTAL_RAM_GB:-}"
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

compose_nixos_rebuild_options() {
    local use_caches="${1:-${USE_BINARY_CACHES:-true}}"
    local -a parallelism
    mapfile -t parallelism < <(determine_nixos_parallelism)

    local computed_max_jobs="${parallelism[0]:-auto}"
    local computed_core_limit="${parallelism[1]:-0}"
    local throttle_message="${parallelism[2]:-}"

    if [[ -n "$throttle_message" ]]; then
        print_info "$throttle_message"
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

    printf '%s\n' "${opts[@]}"
}

# ============================================================================
# Workspace Preparation Helpers
# ============================================================================

ensure_flake_workspace() {
    local created_root=false
    local created_dir=false

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
        admin_user=$(prompt_user "Gitea admin username" "$default_user")
        if [[ -z "$admin_user" ]]; then
            admin_user="$default_user"
        fi
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
    local updated="false"

    if [[ -n "$GITEA_SECRETS_CACHE_FILE" && -f "$GITEA_SECRETS_CACHE_FILE" ]]; then
        # shellcheck disable=SC1090
        . "$GITEA_SECRETS_CACHE_FILE"
    fi

    if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
        GITEA_ADMIN_PROMPTED="true"
        GITEA_PROMPT_CHANGED="false"
        return 0
    fi

    if [[ -z "${GITEA_SECRET_KEY:-}" ]]; then
        local generated_secret
        if ! generated_secret=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea secret key"
            return 1
        fi
        GITEA_SECRET_KEY="$generated_secret"
        updated="true"
    fi

    if [[ -z "${GITEA_INTERNAL_TOKEN:-}" ]]; then
        local internal_token
        if ! internal_token=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea internal token"
            return 1
        fi
        GITEA_INTERNAL_TOKEN="$internal_token"
        updated="true"
    fi

    if [[ -z "${GITEA_LFS_JWT_SECRET:-}" ]]; then
        local lfs_jwt_secret
        if ! lfs_jwt_secret=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea LFS JWT secret"
            return 1
        fi
        GITEA_LFS_JWT_SECRET="$lfs_jwt_secret"
        updated="true"
    fi

    if [[ -z "${GITEA_JWT_SECRET:-}" ]]; then
        local oauth_secret
        if ! oauth_secret=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea OAuth2 secret"
            return 1
        fi
        GITEA_JWT_SECRET="$oauth_secret"
        updated="true"
    fi

    if [[ "${GITEA_ADMIN_PROMPTED,,}" != "true" ]]; then
        GITEA_PROMPT_CHANGED="false"
        if ! prompt_configure_gitea_admin; then
            return 1
        fi
        GITEA_ADMIN_PROMPTED="true"
        if [[ "$GITEA_PROMPT_CHANGED" == "true" ]]; then
            updated="true"
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
# Generate NixOS System Configuration
# ============================================================================
# Purpose: Generate NixOS configuration files from templates
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
generate_nixos_system_config() {
    print_section "Generating NixOS Configuration"

    # ========================================================================
    # Detect System Information
    # ========================================================================
    local HOSTNAME=$(hostname)
    local NIXOS_VERSION=$(derive_system_release_version)
    local STATE_VERSION="$NIXOS_VERSION"
    local SYSTEM_ARCH=$(uname -m)

    # Convert arch names
    case "$SYSTEM_ARCH" in
        x86_64) SYSTEM_ARCH="x86_64-linux" ;;
        aarch64) SYSTEM_ARCH="aarch64-linux" ;;
        *) SYSTEM_ARCH="x86_64-linux" ;;
    esac

    print_info "System: $HOSTNAME"
    print_info "Architecture: $SYSTEM_ARCH"
    print_info "NixOS Version: $NIXOS_VERSION"
    print_info "State Version: $STATE_VERSION"
    echo ""

    # ========================================================================
    # Determine Channels
    # ========================================================================
    local NIXOS_CHANNEL_NAME="${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${NIXOS_VERSION}}"
    local HM_CHANNEL_NAME="${SYNCHRONIZED_HOME_MANAGER_CHANNEL:-release-${NIXOS_VERSION}}"

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
    local LOCALE=$(localectl status | grep "LANG=" | cut -d= -f2 | tr -d ' ' 2>/dev/null || echo "en_US.UTF-8")

    print_info "Timezone: $TIMEZONE"
    print_info "Locale: $LOCALE"
    echo ""

    # ========================================================================
    # Ensure Config Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating configuration directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
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
    local BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    if [[ -f "$SYSTEM_CONFIG_FILE" ]]; then
        local BACKUP_FILE="$SYSTEM_CONFIG_FILE.backup.$BACKUP_TIMESTAMP"
        cp "$SYSTEM_CONFIG_FILE" "$BACKUP_FILE" 2>/dev/null || true
        print_success "Backed up configuration.nix"
    fi

    if [[ -f "$FLAKE_FILE" ]]; then
        safe_mkdir "$HM_CONFIG_DIR/backup" || print_warning "Could not create backup directory"
        safe_copy_file_silent "$FLAKE_FILE" "$HM_CONFIG_DIR/backup/flake.nix.backup.$BACKUP_TIMESTAMP" && \
            print_success "Backed up flake.nix"
    fi

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

    # ========================================================================
    # Replace Placeholders in configuration.nix
    # ========================================================================
    print_info "Customizing configuration..."

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

    local initrd_kernel_modules="# initrd.kernelModules handled by hardware-configuration.nix"
    case "${CPU_VENDOR:-}" in
        intel)
            initrd_kernel_modules='initrd.kernelModules = [ "i915" ];  # Intel GPU early KMS'
            ;;
        amd)
            initrd_kernel_modules='initrd.kernelModules = [ "amdgpu" ];  # AMD GPU early KMS'
            ;;
    esac

    local microcode_section="# hardware.cpu microcode updates managed automatically"
    if [[ -n "${CPU_MICROCODE:-}" && "${CPU_VENDOR:-unknown}" != "unknown" ]]; then
        microcode_section="hardware.cpu.${CPU_VENDOR}.updateMicrocode = true;  # Enable ${cpu_vendor_label} microcode updates"
    fi

    local binary_cache_settings
    binary_cache_settings=$(generate_binary_cache_settings "${USE_BINARY_CACHES:-true}")

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
    local zswap_percent="${ZSWAP_MAX_POOL_PERCENT:-20}"
    local zswap_compressor="${ZSWAP_COMPRESSOR:-zstd}"
    local zswap_zpool="${ZSWAP_ZPOOL:-z3fold}"
    local enable_zswap="${ENABLE_ZSWAP_CONFIGURATION:-false}"
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

    local kernel_modules_placeholder
    kernel_modules_placeholder=$(cat <<'EOF'
      # No additional kernel modules configured by the generator
EOF
)

    local kernel_sysctl_tunables=""

    local kernel_params_block
    kernel_params_block=$(cat <<'EOF'
    kernelParams = [
      # Quiet boot (cleaner boot messages)
      "quiet"
      "splash"

      # Performance: Disable CPU security mitigations (OPTIONAL - commented for security)
      # WARNING: Only enable on trusted systems where performance > security
      # "mitigations=off"
    ];
EOF
)

    local swap_and_hibernation_block
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

        kernel_modules_placeholder=$(cat <<EOF
      # Zswap allocator module required for compressed swap
      "${zswap_zpool}"
EOF
)

        kernel_sysctl_tunables=$(cat <<EOF

      # Memory management tunables for swap-backed hibernation (auto-tuned)
      "vm.swappiness" = 10;
      "vm.vfs_cache_pressure" = 50;
      "vm.dirty_ratio" = 10;
      "vm.dirty_background_ratio" = 5;
      "vm.max_map_count" = 262144;
      "fs.inotify.max_user_watches" = 524288;
      "fs.inotify.max_user_instances" = 512;
      "fs.inotify.max_queued_events" = 32768;
      "kernel.shmmax" = 17179869184;  # 16GB
      "kernel.shmall" = 4194304;      # 16GB in pages (4KB pages)
EOF
)

        kernel_params_block=$(cat <<EOF
    kernelParams = [
      # Zswap: Compressed swap cache tuned for ${total_ram_value}GB RAM systems
      "zswap.enabled=1"
      "zswap.compressor=${zswap_compressor}"
      "zswap.max_pool_percent=${zswap_percent}"
      "zswap.zpool=${zswap_zpool}"

      # Quiet boot (cleaner boot messages)
      "quiet"
      "splash"

      # Performance: Disable CPU security mitigations (OPTIONAL - commented for security)
      # WARNING: Only enable on trusted systems where performance > security
      # "mitigations=off"
    ];
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
      fileMode = "600";
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
    else
        swap_and_hibernation_block=$(cat <<'EOF'
  # Swap configuration is inherited from hardware-configuration.nix
  # Previous deployment did not enable swap-backed hibernation; leaving defaults unchanged.
EOF
)
    fi

    local -a nix_parallelism_settings
    mapfile -t nix_parallelism_settings < <(determine_nixos_parallelism)
    local nix_max_jobs_value="${nix_parallelism_settings[0]:-auto}"
    local nix_core_limit_value="${nix_parallelism_settings[1]:-0}"
    local nix_throttle_message="${nix_parallelism_settings[2]:-}"

    local nix_max_jobs_literal
    if [[ "$nix_max_jobs_value" == "auto" ]]; then
        nix_max_jobs_literal='"auto"'
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

    local user_password_block
    if [[ -n "${USER_PASSWORD_BLOCK:-}" ]]; then
        user_password_block="$USER_PASSWORD_BLOCK"
    else
        user_password_block=$'    # (no password directives detected; update manually if required)\n'
    fi

    if ! ensure_gitea_secrets_ready; then
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
        if printf '%s\n' "$output" | ${pkgs.gnugrep}/bin/grep -q '^${giteaAdminUserPattern}\\b'; then
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

    ${pkgs.gitea}/bin/gitea admin user create \
      --username ${lib.escapeShellArg giteaAdminUser} \
      --password ${lib.escapeShellArg giteaAdminSecrets.adminPassword} \
      --email ${lib.escapeShellArg giteaAdminEmail} \
      --must-change-password=false \
      --admin
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
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@CPU_VENDOR_LABEL@" "$cpu_vendor_label"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@INITRD_KERNEL_MODULES@" "$initrd_kernel_modules"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@KERNEL_MODULES_PLACEHOLDER@" "$kernel_modules_placeholder"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@KERNEL_SYSCTL_TUNABLES@" "$kernel_sysctl_tunables"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@RESUME_DEVICE_DIRECTIVE@" "$resume_device_directive"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@BOOT_KERNEL_PARAMETERS_BLOCK@" "$kernel_params_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@MICROCODE_SECTION@" "$microcode_section"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@BINARY_CACHE_SETTINGS@" "$binary_cache_settings"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GPU_HARDWARE_SECTION@" "$gpu_hardware_section"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GPU_SESSION_VARIABLES@" "$gpu_session_variables"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@GPU_DRIVER_PACKAGES@" "$gpu_driver_packages_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@SELECTED_TIMEZONE@" "$TIMEZONE"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@CURRENT_LOCALE@" "$LOCALE"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@NIXOS_VERSION@" "$NIXOS_VERSION"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@SWAP_AND_HIBERNATION_BLOCK@" "$swap_and_hibernation_block"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@NIX_MAX_JOBS@" "$nix_max_jobs_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@NIX_BUILD_CORES@" "$nix_cores_literal"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@NIX_PARALLEL_COMMENT@" "$nix_parallel_comment"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@USERS_MUTABLE@" "${USERS_MUTABLE_SETTING:-true}"
    replace_placeholder "$SYSTEM_CONFIG_FILE" "@USER_PASSWORD_BLOCK@" "$user_password_block"
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

    if ! nix_verify_no_placeholders "$SYSTEM_CONFIG_FILE" "configuration.nix"; then
        return 1
    fi

    print_success "Generated configuration.nix"
    echo ""

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
    print_section "Creating Home Manager Configuration"

    # ========================================================================
    # Detect Versions
    # ========================================================================
    local NIXOS_CHANNEL=$(sudo nix-channel --list 2>/dev/null | grep '^nixos' | awk '{print $2}')
    local HM_CHANNEL=$(nix-channel --list 2>/dev/null | grep 'home-manager' | awk '{print $2}')
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

    local NIXOS_CHANNEL_NAME=$(basename "$NIXOS_CHANNEL" 2>/dev/null || echo "nixos-${STATE_VERSION}")
    local HM_CHANNEL_NAME="${HOME_MANAGER_CHANNEL_REF:-$(normalize_channel_name "$HM_CHANNEL")}"

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        HM_CHANNEL_NAME="release-${STATE_VERSION}"
    fi

    print_info "NixOS channel: $NIXOS_CHANNEL_NAME"
    print_info "Home-manager channel: $HM_CHANNEL_NAME"
    echo ""

    # ========================================================================
    # Ensure Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating home-manager directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
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
    if [[ -f "$HOME_MANAGER_FILE" ]]; then
        local BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        local BACKUP_DIR="$HM_CONFIG_DIR/backup"
        safe_mkdir "$BACKUP_DIR" || print_warning "Could not create backup directory"

        safe_copy_file_silent "$HOME_MANAGER_FILE" "$BACKUP_DIR/home.nix.backup.$BACKUP_TIMESTAMP" && \
            print_success "Backed up existing home.nix"
    fi

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
    local support_module
    for support_module in "python-overrides.nix"; do
        local module_source="$TEMPLATE_DIR/$support_module"
        local module_destination="$HM_CONFIG_DIR/$support_module"

        print_info "Syncing $support_module into Home Manager workspace..."

        if [[ ! -f "$module_source" ]]; then
            print_error "Required template missing: $module_source"
            return 1
        fi

        if ! safe_copy_file "$module_source" "$module_destination"; then
            print_error "Failed to install $support_module into $HM_CONFIG_DIR"
            return 1
        fi

        safe_chown_user_dir "$module_destination" || true
        print_success "Installed $support_module"
    done

    # ========================================================================
    # Replace Placeholders
    # ========================================================================
    local TEMPLATE_HASH=$(echo -n "AIDB-v4.0-packages-v${SCRIPT_VERSION:-4.0.0}" | sha256sum | cut -d' ' -f1 | cut -c1-16)
    local DEFAULT_EDITOR="${DEFAULT_EDITOR:-nano}"

    # GPU monitoring packages
    local GPU_MONITORING_PACKAGES="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES="[ radeontop amdgpu_top ]"
    elif [[ "$GPU_TYPE" == "nvidia" ]]; then
        GPU_MONITORING_PACKAGES="[ nvtop ]"
    fi

    print_info "Customizing home.nix..."

    if ! ensure_gitea_secrets_ready; then
        return 1
    fi

    replace_placeholder "$HOME_MANAGER_FILE" "VERSIONPLACEHOLDER" "${SCRIPT_VERSION:-4.0.0}"
    replace_placeholder "$HOME_MANAGER_FILE" "HASHPLACEHOLDER" "$TEMPLATE_HASH"
    replace_placeholder "$HOME_MANAGER_FILE" "HOMEUSERNAME" "$USER"
    replace_placeholder "$HOME_MANAGER_FILE" "HOMEDIR" "$HOME"
    replace_placeholder "$HOME_MANAGER_FILE" "STATEVERSION_PLACEHOLDER" "$STATE_VERSION"
    replace_placeholder "$HOME_MANAGER_FILE" "@GPU_MONITORING_PACKAGES@" "$GPU_MONITORING_PACKAGES"

    local HOME_HOSTNAME=$(hostname)
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
    local file_size=$(stat -c%s "$HOME_MANAGER_FILE" 2>/dev/null || echo "0")
    if [[ "$file_size" -eq 0 ]]; then
        print_error "VERIFICATION FAILED: home.nix is empty"
        return 1
    fi

    print_success "Created home.nix"
    print_info "Location: $HOME_MANAGER_FILE"
    print_info "File size: $file_size bytes"
    echo ""

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
        print_success "Hardware configuration already exists"
        return 0
    fi

    # Generate using nixos-generate-config
    print_info "Generating hardware configuration..."
    local TEMP_DIR=$(mktemp -d)

    if sudo nixos-generate-config --dir "$TEMP_DIR" --show-hardware-config > "$HARDWARE_CONFIG" 2>/dev/null; then
        safe_chown_user_dir "$HARDWARE_CONFIG"
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
    print_section "Validating Configuration"

    local target_host=$(hostname)
    local log_path="/tmp/nixos-rebuild-dry-build.log"

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
    if declare -F compose_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t nixos_rebuild_opts < <(compose_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
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

    # Run dry-build (doesn't actually build, just evaluates)
    if sudo nixos-rebuild dry-build --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" 2>&1 | tee "$log_path"; then
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
