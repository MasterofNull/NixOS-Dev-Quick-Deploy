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
# NOTE: ensure_package_available() is defined in lib/common.sh (canonical location).
# Duplicate removed in Phase 17.2.2 — common.sh is loaded after packages.sh and provides
# the definitive implementation.

# NOTE: ensure_prerequisite_installed() is defined in lib/common.sh (canonical location).
# Duplicate removed in Phase 17.2.3 — common.sh is loaded after packages.sh and provides
# the definitive implementation.

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

    if ! ensure_prerequisite_installed "hf" "nixpkgs#python3Packages.huggingface-hub" "hf (Hugging Face CLI)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "huggingface-cli" "nixpkgs#python3Packages.huggingface-hub" "huggingface-cli (Hugging Face legacy CLI)"; then
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

# ============================================================================
# Cleanup Preflight Nix-Env Packages (avoid home-manager path collisions)
# ============================================================================
# Purpose: Remove preflight-installed packages from the user profile so
# home-manager can own those paths without file collisions.
# Returns:
#   0 - Success (cleaned up or nothing to remove)
# ============================================================================
cleanup_preflight_profile_packages() {
    if ! command -v nix-env >/dev/null 2>&1; then
        :
    fi

    local -a patterns=(
        '^python3($|[^a-zA-Z0-9])'
        '^python3Full'
        '^python3Minimal'
        '^python3[0-9]'
        '^shellcheck'
        '^slirp4netns'
        '^fuse3'
        'huggingface-hub'
        '^git($|[^a-zA-Z0-9])'
    )

    # --------------------------------------------------------------------
    # 1) Remove from legacy nix-env profile (if present)
    # --------------------------------------------------------------------
    local installed
    installed=$(run_as_primary_user nix-env -q 2>/dev/null || true)
    if [[ -n "$installed" ]]; then
        local removed_any=false
        local pkg
        while IFS= read -r pkg; do
            [[ -z "$pkg" ]] && continue
            local matched=false
            local pattern
            for pattern in "${patterns[@]}"; do
                if [[ "$pkg" =~ $pattern ]]; then
                    matched=true
                    break
                fi
            done
            if [[ "$matched" == true ]]; then
                if run_as_primary_user nix-env -e "$pkg" >/dev/null 2>&1; then
                    print_success "Removed preflight nix-env package: $pkg"
                    removed_any=true
                else
                    print_warning "Failed to remove preflight nix-env package: $pkg"
                fi
            fi
        done <<< "$installed"

        if [[ "$removed_any" == true ]]; then
            print_info "Preflight nix-env packages cleaned to avoid home-manager path conflicts"
        fi
    fi

    # --------------------------------------------------------------------
    # 2) Remove from nix profile (nix profile install ...)
    # --------------------------------------------------------------------
    if command -v nix >/dev/null 2>&1; then
        local profile_json
        profile_json=$(nix profile list --json 2>/dev/null || true)

        if [[ -n "$profile_json" && "$profile_json" != "[]" ]]; then
            local removal_indices=""

            if command -v jq >/dev/null 2>&1; then
                removal_indices=$(printf '%s' "$profile_json" | jq -r '
                  .[]? | select(.name != null) |
                  (.name | tostring) as $n |
                  if ($n|test("^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)"))
                  then .index else empty end' 2>/dev/null || true)
            elif command -v python3 >/dev/null 2>&1; then
                removal_indices=$(PROFILE_JSON="$profile_json" python3 - <<'PY'
import json, os, re, sys
raw = os.environ.get("PROFILE_JSON", "[]")
try:
    entries = json.loads(raw)
except Exception:
    sys.exit(0)
pattern = re.compile(r"^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)")
for entry in entries or []:
    if not isinstance(entry, dict):
        continue
    name = str(entry.get("name") or "")
    if pattern.search(name):
        idx = entry.get("index")
        if idx is not None:
            print(idx)
PY
                )
            fi

            if [[ -n "$removal_indices" ]]; then
                local idx
                while IFS= read -r idx; do
                    [[ -z "$idx" ]] && continue
                    if nix profile remove "$idx" >/dev/null 2>&1; then
                        print_success "Removed nix profile entry at index $idx (preflight package)"
                    else
                        print_warning "Failed to remove nix profile entry at index $idx"
                    fi
                done <<< "$removal_indices"
            fi
        else
            # Fallback: parse human-readable output if JSON unavailable
            local line_indices=""
            line_indices=$(nix profile list 2>/dev/null | awk '
                NF>=2 {
                    idx=$1;
                    name=$2;
                    if (name ~ /^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)/) {
                        print idx
                    }
                }' || true)
            if [[ -n "$line_indices" ]]; then
                local idx
                while IFS= read -r idx; do
                    [[ -z "$idx" ]] && continue
                    if nix profile remove "$idx" >/dev/null 2>&1; then
                        print_success "Removed nix profile entry at index $idx (preflight package)"
                    else
                        print_warning "Failed to remove nix profile entry at index $idx"
                    fi
                done <<< "$line_indices"
            fi
        fi
    fi

    # --------------------------------------------------------------------
    # 3) Remove from home-manager profile (if present)
    # --------------------------------------------------------------------
    if command -v nix >/dev/null 2>&1; then
        local hm_profile="${HOME}/.local/state/nix/profiles/home-manager"
        if [[ -L "$hm_profile" || -d "$hm_profile" ]]; then
            print_info "Checking home-manager profile for conflicting packages..."
            local hm_json=""
            hm_json=$(nix profile list --json --profile "$hm_profile" 2>/dev/null || true)
            if [[ -n "$hm_json" && "$hm_json" != "[]" ]]; then
                local hm_indices=""
                if command -v jq >/dev/null 2>&1; then
                    hm_indices=$(printf '%s' "$hm_json" | jq -r '
                      .[]? | select(.name != null) |
                      (.name | tostring) as $n |
                      if ($n|test("^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)"))
                      then .index else empty end' 2>/dev/null || true)
                elif command -v python3 >/dev/null 2>&1; then
                    hm_indices=$(PROFILE_JSON="$hm_json" python3 - <<'PY'
import json, os, re, sys
raw = os.environ.get("PROFILE_JSON", "[]")
try:
    entries = json.loads(raw)
except Exception:
    sys.exit(0)
pattern = re.compile(r"^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)")
for entry in entries or []:
    if not isinstance(entry, dict):
        continue
    name = str(entry.get("name") or "")
    if pattern.search(name):
        idx = entry.get("index")
        if idx is not None:
            print(idx)
PY
                    )
                fi
                if [[ -n "$hm_indices" ]]; then
                    print_warning "Found conflicting packages in home-manager profile, removing them..."
                    local hm_idx
                    while IFS= read -r hm_idx; do
                        [[ -z "$hm_idx" ]] && continue
                        if nix profile remove "$hm_idx" --profile "$hm_profile" >/dev/null 2>&1; then
                            print_success "Removed home-manager profile entry at index $hm_idx (preflight package)"
                        else
                            print_warning "Failed to remove home-manager profile entry at index $hm_idx"
                        fi
                    done <<< "$hm_indices"
                else
                    print_info "No conflicting packages found in home-manager profile (JSON check)"
                fi
            else
                # Fallback: parse human-readable output if JSON unavailable
                local hm_line_indices=""
                hm_line_indices=$(nix profile list --profile "$hm_profile" 2>/dev/null | awk '
                    NF>=2 {
                        idx=$1;
                        name=$2;
                        if (name ~ /^(python3|python3Full|python3Minimal|python3[0-9]|shellcheck|slirp4netns|fuse3|huggingface-hub|git)([^a-zA-Z0-9]|$)/) {
                            print idx
                        }
                    }' || true)
                if [[ -n "$hm_line_indices" ]]; then
                    print_warning "Found conflicting packages in home-manager profile, removing them..."
                    local hm_idx
                    while IFS= read -r hm_idx; do
                        [[ -z "$hm_idx" ]] && continue
                        if nix profile remove "$hm_idx" --profile "$hm_profile" >/dev/null 2>&1; then
                            print_success "Removed home-manager profile entry at index $hm_idx (preflight package)"
                        else
                            print_warning "Failed to remove home-manager profile entry at index $hm_idx"
                        fi
                    done <<< "$hm_line_indices"
                else
                    print_info "No conflicting packages found in home-manager profile (text check)"
                fi
            fi
        else
            print_info "Home-manager profile not yet initialized"
        fi
    fi

    return 0
}

# ============================================================================
# Aggressively Clean Home Manager Profile
# ============================================================================
# Purpose: Nuclear option to ensure home-manager profile is completely clean
# before home-manager switch to prevent frameobject.h and similar collisions
# Returns:
#   0 - Success (profile is clean)
#   1 - Failed to clean (python3 or other conflicts still present)
# ============================================================================
aggressively_clean_home_manager_profile() {
    local hm_profile="${HOME}/.local/state/nix/profiles/home-manager"

    if ! command -v nix >/dev/null 2>&1; then
        print_warning "nix command not available, cannot clean home-manager profile"
        return 0
    fi

    # If profile doesn't exist yet, nothing to clean
    if [[ ! -e "$hm_profile" ]]; then
        print_info "Home-manager profile not yet initialized (nothing to clean)"
        return 0
    fi

    print_section "Aggressively Cleaning Home-Manager Profile"
    echo ""
    print_info "Ensuring no conflicting packages exist in: $hm_profile"

    # Show current profile contents for debugging
    print_info "Current home-manager profile contents:"
    if nix profile list --profile "$hm_profile" 2>/dev/null | head -20; then
        echo ""
    else
        print_warning "Could not list home-manager profile contents"
        return 0
    fi

    # Multiple cleanup passes to catch any stragglers
    local cleanup_pass=1
    local max_passes=3
    local cleaned_something=false

    while (( cleanup_pass <= max_passes )); do
        print_info "Cleanup pass $cleanup_pass of $max_passes..."

        local profile_output
        profile_output=$(nix profile list --profile "$hm_profile" 2>/dev/null || true)

        if [[ -z "$profile_output" ]]; then
            print_info "Profile is empty or unreadable"
            break
        fi

        # Check for python3 and other conflicting packages
        # Look in both the package name and the store path
        local conflict_lines
        conflict_lines=$(echo "$profile_output" | grep -iE 'python3|huggingface-hub|shellcheck|slirp4netns|fuse3|^[[:space:]]*[0-9]+[[:space:]]+git[[:space:]]' || true)

        if [[ -n "$conflict_lines" ]]; then
            print_warning "Found conflicting packages in pass $cleanup_pass:"
            echo "$conflict_lines" | sed 's/^/  /'
            echo ""

            # Extract indices and remove them
            local indices
            indices=$(echo "$conflict_lines" | awk '{print $1}' | sed 's/://g')

            if [[ -n "$indices" ]]; then
                while IFS= read -r idx; do
                    [[ -z "$idx" ]] && continue
                    print_info "Removing profile entry at index: $idx"
                    if nix profile remove "$idx" --profile "$hm_profile" > >(tee /dev/tty) 2>&1; then
                        print_success "Removed index $idx"
                        cleaned_something=true
                    else
                        print_error "Failed to remove index $idx from home-manager profile"
                        print_info "You may need to manually run: nix profile remove $idx --profile $hm_profile"
                    fi
                done <<< "$indices"
            fi
        else
            print_success "No conflicting packages found in pass $cleanup_pass"
            break
        fi

        cleanup_pass=$((cleanup_pass + 1))
        sleep 1  # Brief pause between passes
    done

    # Final verification
    print_info "Final verification of home-manager profile..."
    local final_check
    final_check=$(nix profile list --profile "$hm_profile" 2>/dev/null | grep -iE 'python3|huggingface' || true)

    if [[ -n "$final_check" ]]; then
        print_error "Home-manager profile still contains conflicting packages after cleanup:"
        echo "$final_check" | sed 's/^/  /'
        echo ""
        print_error "This will cause file collisions (frameobject.h) during home-manager switch"
        print_info "Manual cleanup required:"
        print_info "  nix profile list --profile $hm_profile"
        print_info "  nix profile remove <index> --profile $hm_profile"
        return 1
    fi

    if [[ "$cleaned_something" == true ]]; then
        print_success "Successfully cleaned home-manager profile"
    else
        print_success "Home-manager profile was already clean"
    fi

    echo ""
    return 0
}
