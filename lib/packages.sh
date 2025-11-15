#!/usr/bin/env bash
#
# Package Management Functions
# Purpose: Package installation and validation
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/common.sh → run_as_primary_user() function
#   - lib/python.sh → ensure_python_runtime() function
#
# Required Variables:
#   - DRY_RUN → Dry run mode flag
#   - LOG_DIR → Log directory path
#   - PYTHON_BIN → Python interpreter array
#
# Note: This module mirrors helpers from lib/common.sh but keeps them isolated
# for package-specific workflows (preflight installs, profile cleanup). Keep
# logic changes in sync if you adjust the shared functions.
#
# ============================================================================

# ============================================================================
# Ensure Package Available
# ============================================================================
# Purpose: Check if package is available, install if missing
# Parameters:
#   $1 - Command to check
#   $2 - Package name (defaults to $1)
#   $3 - Priority (CRITICAL/IMPORTANT/OPTIONAL)
#   $4 - Description
# Returns:
#   0 - Package available or successfully installed
#   1 - Package unavailable and installation failed
# ============================================================================
# See lib/common.sh for parameter descriptions. This copy exists so phase logic
# can source packages.sh without pulling the entire common.sh surface area.
ensure_package_available() {
    local cmd="$1"
    local pkg="${2:-$1}"
    local priority="${3:-CRITICAL}"
    local description="${4:-$cmd}"
    local pkg_ref=""

    # Check if already available
    if command -v "$cmd" &>/dev/null; then
        local existing_path
        existing_path=$(command -v "$cmd" 2>/dev/null)
        print_success "$description available: $existing_path"
        log DEBUG "$cmd available: $existing_path"
        return 0
    fi

    # Determine log level based on priority
    if [[ "${IMPERATIVE_INSTALLS_ALLOWED:-false}" != "true" ]]; then
        case "$priority" in
            CRITICAL)
                print_error "$description not found and imperative installs are disabled. Declare it in configuration.nix or home.nix and rerun."
                ;;
            IMPORTANT)
                print_warning "$description not found and imperative installs are disabled. Add it to configuration.nix or home.nix."
                ;;
            OPTIONAL)
                print_info "$description not found and imperative installs are disabled. Add it declaratively if desired."
                ;;
        esac
        log INFO "Skipping imperative installation for $cmd because IMPERATIVE_INSTALLS_ALLOWED is not true"
        return 1
    fi

    local log_level="INFO"

    case "$priority" in
        CRITICAL)
            print_warning "$description not found - installing from nixpkgs"
            log_level="WARNING"
            ;;
        IMPORTANT)
            print_info "$description not found - installing automatically (recommended)"
            log_level="INFO"
            ;;
        OPTIONAL)
            print_info "$description not found - installing automatically (optional, improves functionality)"
            log_level="INFO"
            ;;
    esac

    log "$log_level" "$cmd missing, attempting installation via $pkg"

    # Validate package reference
    if [[ -z "$pkg" ]]; then
        log ERROR "No package mapping provided for $cmd"
        return 1
    fi

    # Build package reference
    if [[ "$pkg" == *"#"* ]]; then
        pkg_ref="$pkg"
    else
        pkg_ref="nixpkgs#$pkg"
    fi

    # Attempt installation
    if ! ensure_prerequisite_installed "$cmd" "$pkg_ref" "$description"; then
        case "$priority" in
            CRITICAL)
                print_error "Failed to install $description"
                ;;
            IMPORTANT)
                print_warning "Failed to install $description"
                ;;
            OPTIONAL)
                print_info "$description could not be installed automatically"
                ;;
        esac
        return 1
    fi

    # Verify installation
    if command -v "$cmd" &>/dev/null; then
        local installed_path
        installed_path=$(command -v "$cmd" 2>/dev/null)
        log INFO "$cmd installed and available at $installed_path"
        return 0
    fi

    log ERROR "$cmd installation reported success but command remains unavailable"
    return 1
}

# ============================================================================
# Ensure Prerequisite Installed
# ============================================================================
# Purpose: Install prerequisite package via nix-env
# Parameters:
#   $1 - Command to install
#   $2 - Package reference (e.g., "nixpkgs#git")
#   $3 - Description
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
# nix-env installer variant used during the preflight phase. Shares behaviour
# with the version in lib/common.sh; keep changes mirrored.
ensure_prerequisite_installed() {
    local cmd="$1"
    local pkg_ref="$2"
    local description="$3"
    local install_log="$LOG_DIR/preflight-${cmd}-install.log"
    local attr_path=""

    # Check if already available
    if command -v "$cmd" >/dev/null 2>&1; then
        local existing_path
        existing_path=$(command -v "$cmd" 2>/dev/null)
        print_success "$description already available: $existing_path"
        log INFO "Prerequisite $cmd present at $existing_path"
        return 0
    fi

    # Extract attribute path from reference
    if [[ "$pkg_ref" =~ ^[^#]+#(.+)$ ]]; then
        attr_path="${BASH_REMATCH[1]}"
    fi

    if [[ "${IMPERATIVE_INSTALLS_ALLOWED:-false}" != "true" ]]; then
        print_error "$description cannot be installed automatically because imperative installs are disabled. Declare it in configuration.nix or home.nix."
        log INFO "Skipping nix-env install for $cmd because IMPERATIVE_INSTALLS_ALLOWED is not true"
        return 1
    fi

    # Handle dry-run
    if [[ "$DRY_RUN" == true ]]; then
        print_warning "$description not found – would install via 'nix-env' (dry-run)"
        log INFO "Dry-run: would install prerequisite $cmd from $pkg_ref"
        return 0
    fi

    # Validate attribute path
    if [[ -z "$attr_path" ]]; then
        log ERROR "Unable to derive attribute path from $pkg_ref for $cmd"
        print_error "Failed to install $description – invalid package reference"
        return 1
    fi

    # Prepare installation
    rm -f "$install_log"
    local install_succeeded=false
    local install_method=""
    local exit_code=0

    # Try nix-env with nixos channel first (primary method)
    if command -v nix-env >/dev/null 2>&1; then
        print_warning "$description not found – installing via nix-env -iA nixos.$attr_path"
        log INFO "Attempting nix-env installation for $cmd using nixos channel"

        if run_as_primary_user nix-env -iA "nixos.$attr_path" >"$install_log" 2>&1; then
            install_succeeded=true
            install_method="nix-env (nixos channel)"
        else
            exit_code=$?
            log WARNING "nix-env -iA nixos.$attr_path for $cmd failed with exit code $exit_code, trying nixpkgs fallback"

            # Fallback to nixpkgs if nixos channel fails
            print_warning "$description installation retry via nix-env -f '<nixpkgs>' -iA $attr_path"
            log INFO "Attempting nix-env installation for $cmd using nixpkgs"

            if run_as_primary_user nix-env -f '<nixpkgs>' -iA "$attr_path" >>"$install_log" 2>&1; then
                install_succeeded=true
                install_method="nix-env (nixpkgs)"
            else
                exit_code=$?
                log ERROR "nix-env -f '<nixpkgs>' -iA $attr_path for $cmd failed with exit code $exit_code"
            fi
        fi
    else
        log ERROR "nix-env command not available"
        print_error "Failed to install $description – nix-env not found"
        return 1
    fi

    # Check installation result
    if [[ "$install_succeeded" == true ]]; then
        hash -r 2>/dev/null || true

        # Ensure PATH includes nix profile directories
        export PATH="$HOME/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH"

        local new_path
        new_path=$(command -v "$cmd" 2>/dev/null || run_as_primary_user bash -lc "command -v $cmd" 2>/dev/null || true)

        if [[ -n "$new_path" ]]; then
            print_success "$description installed via $install_method: $new_path"
            log INFO "Prerequisite $cmd installed successfully via $install_method at $new_path"
        else
            print_warning "$description installation completed but command not yet on current PATH"
            print_info "Refreshing shell environment..."
            log WARNING "Prerequisite $cmd installed but not immediately visible on PATH"

            # Try reloading the environment
            if [[ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]]; then
                # shellcheck disable=SC1091
                source "$HOME/.nix-profile/etc/profile.d/nix.sh" 2>/dev/null || true
            fi

            # Check again after reloading
            new_path=$(command -v "$cmd" 2>/dev/null || true)
            if [[ -n "$new_path" ]]; then
                print_success "$description now available: $new_path"
                log INFO "Prerequisite $cmd available after environment refresh at $new_path"
            fi
        fi

        print_info "Installation log: $install_log"
        return 0
    else
        print_error "Failed to install $description via nix-env"
        log ERROR "Failed to install prerequisite $cmd via nix-env (exit code: $exit_code)"
        print_info "Review the log for details: $install_log"
        return 1
    fi
}

# ============================================================================
# Ensure Preflight Core Packages
# ============================================================================
# Purpose: Install essential packages needed for deployment
# Returns:
#   0 - All packages installed
#   1 - Failed to install required packages
# ============================================================================
ensure_preflight_core_packages() {
    print_info "Ensuring core prerequisite packages are installed..."

    if ! ensure_prerequisite_installed "git" "nixpkgs#git" "git (version control)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "python3" "nixpkgs#python3" "python3 (Python interpreter)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "shellcheck" "nixpkgs#shellcheck" "shellcheck (shell script linter)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "fusermount3" "nixpkgs#fuse3" "fusermount3 (FUSE user mount helper)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "slirp4netns" "nixpkgs#slirp4netns" "slirp4netns (rootless networking helper)"; then
        return 1
    fi

    return 0
}

# ============================================================================
# Cleanup Conflicting Home Manager Profile
# ============================================================================
# Purpose: Remove existing home-manager profile entries to prevent conflicts
# Returns:
#   0 - Success (cleaned up or nothing to clean)
# ============================================================================
cleanup_conflicting_home_manager_profile() {
    if ! command -v nix >/dev/null 2>&1; then
        return 0
    fi

    # Try removing default home-manager profile entry
    if nix profile remove home-manager >/dev/null 2>&1; then
        print_success "Preemptively removed default 'home-manager' profile entry"
    fi

    local removal_indices=""
    local conflict_detected=false

    # Get profile JSON
    local profile_json
    profile_json=$(nix profile list --json 2>/dev/null || true)

    # Parse JSON to find home-manager entries
    if [[ -n "$profile_json" && "$profile_json" != "[]" ]]; then
        if ensure_python_runtime; then
            local parsed_indices
            parsed_indices=$(PROFILE_JSON="$profile_json" "${PYTHON_BIN[@]}" - <<'PY'
import json
import sys
import os

try:
    profile_json_str = os.environ.get('PROFILE_JSON', '[]')
    entries = json.loads(profile_json_str)
except Exception:
    sys.exit(1)

seen = set()
for entry in entries or []:
    if isinstance(entry, str):
        try:
            entry = json.loads(entry)
        except Exception:
            continue
    if not isinstance(entry, dict):
        continue
    text_parts = []
    for key in ("name", "attrPath", "description", "originalRef"):
        value = entry.get(key)
        if isinstance(value, str):
            text_parts.append(value)
    store_paths = entry.get("storePaths") or []
    for path in store_paths:
        if isinstance(path, str):
            text_parts.append(path)
    combined = " ".join(text_parts)
    if "home-manager" not in combined:
        continue
    idx = entry.get("index")
    if isinstance(idx, int):
        seen.add(str(idx))
    elif isinstance(idx, str) and idx:
        seen.add(idx)

if seen:
    print("\n".join(sorted(seen, key=lambda value: int(value) if value.isdigit() else value)))
PY
            )

            if [[ -n "$parsed_indices" ]]; then
                removal_indices+="$parsed_indices"$'\n'
                conflict_detected=true
            fi
        else
            print_warning "Python runtime unavailable; skipping JSON profile cleanup"
        fi
    fi

    # Fallback: text-based parsing
    if [[ "$conflict_detected" == false ]]; then
        local profile_output
        profile_output=$(nix profile list 2>/dev/null || true)
        if [[ -n "$profile_output" ]]; then
            local profile_lines
            profile_lines=$(echo "$profile_output" | tail -n +2 2>/dev/null || true)
            if [[ -n "$profile_lines" ]]; then
                local conflict_lines
                conflict_lines=$(echo "$profile_lines" | grep -E 'home-manager' || true)
                if [[ -n "$conflict_lines" ]]; then
                    conflict_detected=true
                    while IFS= read -r line; do
                        [[ -z "$line" ]] && continue
                        local idx
                        idx=$(echo "$line" | awk '{print $1}')
                        idx="${idx%:}"
                        [[ -z "$idx" ]] && continue
                        removal_indices+="$idx"$'\n'
                    done <<< "$conflict_lines"
                fi
            fi
        fi
    fi

    if [[ "$conflict_detected" == false ]]; then
        return 0
    fi

    print_warning "Existing home-manager profile entries detected (avoiding package conflict)"

    # Deduplicate indices
    if [[ -n "$removal_indices" ]]; then
        removal_indices=$(printf '%s' "$removal_indices" | awk 'NF { if (!seen[$0]++) print $0 }' 2>/dev/null || printf '')
    fi

    local removed_any=false

    # Remove by index
    if [[ -n "$removal_indices" ]]; then
        while IFS= read -r idx; do
            [[ -z "$idx" ]] && continue
            if nix profile remove "$idx" >/dev/null 2>&1; then
                print_success "Removed home-manager profile entry at index $idx"
                removed_any=true
            else
                print_warning "Failed to remove home-manager profile entry at index $idx"
            fi
        done <<< "$removal_indices"
    fi

    # Fallback: remove by name
    if [[ "$removed_any" == false ]]; then
        for name in home-manager home-manager-path; do
            local attempt=0
            while nix profile list 2>/dev/null | tail -n +2 | grep -q "$name"; do
                if nix profile remove "$name" >/dev/null 2>&1; then
                    print_success "Removed existing '$name' profile entry"
                    removed_any=true
                else
                    break
                fi
                attempt=$((attempt + 1))
                if (( attempt >= 5 )); then
                    break
                fi
            done
        done
    fi

    return 0
}
