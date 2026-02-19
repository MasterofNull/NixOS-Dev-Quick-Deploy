#!/usr/bin/env bash
#
# Additional Tools Installation
# Purpose: Install non-declarative tools like Claude Code, Flatpak apps, etc.
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#
# Exports:
#   - install_flatpak_stage() → Install Flatpak applications
#   - install_claude_code() → Install Claude Code CLI
#   - configure_vscodium_for_claude() → Configure VSCodium for Claude
#   - install_vscodium_extensions() → Install VSCodium extensions
#   - install_openskills_tooling() → Install OpenSkills tools
#   - setup_flake_environment() → Setup Nix flakes dev environment

# Resolved list of AI extensions to install via install_vscodium_extensions().
declare -a AI_VSCODE_EXTENSIONS=()

LAST_OPEN_VSX_URL=""
LAST_OPEN_VSX_STATUS=""

# -----------------------------------------------------------------------------
# Helper lookups/registries
# -----------------------------------------------------------------------------
ai_cli_manual_url() {
    local package="$1"

    if declare -p NPM_AI_PACKAGE_MANUAL_URLS >/dev/null 2>&1; then
        printf '%s' "${NPM_AI_PACKAGE_MANUAL_URLS["$package"]:-}"
        return 0
    fi

    printf '%s' ""
}

ai_vscode_cache_var() {
    local raw="$1"
    local sanitized="${raw//[^A-Za-z0-9]/_}"
    if [[ -z "$sanitized" ]]; then
        sanitized="EXT"
    fi
    printf 'AI_VSCODE_EXTENSION_CACHE_%s' "$sanitized"
}

ai_vscode_cache_get() {
    local var
    var=$(ai_vscode_cache_var "$1")
    printf '%s' "${!var:-}"
}

ai_vscode_cache_set() {
    local var
    var=$(ai_vscode_cache_var "$1")
    if ! ai_validate_var_name "$var"; then
        print_warning "Invalid cache key name; skipping cache write"
        return 1
    fi
    printf -v "$var" '%s' "$2"
}

vscode_extension_manual_url() {
    local extension_id="$1"

    if declare -p VSCODE_AI_EXTENSION_FALLBACK_URLS >/dev/null 2>&1; then
        printf '%s' "${VSCODE_AI_EXTENSION_FALLBACK_URLS["$extension_id"]:-}"
        return 0
    fi

    printf '%s' ""
}

open_vsx_extension_available() {
    local extension_id="$1"

    LAST_OPEN_VSX_URL=""
    LAST_OPEN_VSX_STATUS=""

    if [[ -z "$extension_id" ]]; then
        return 0
    fi

    # Extension identifiers must contain a namespace and a name separated by a dot
    if [[ "$extension_id" != *.* ]]; then
        return 0
    fi

    local cached
    cached=$(ai_vscode_cache_get "$extension_id")
    if [[ -n "$cached" ]]; then
        LAST_OPEN_VSX_STATUS="${cached%%|*}"
        LAST_OPEN_VSX_URL="${cached#*|}"
        [[ "$LAST_OPEN_VSX_STATUS" == "200" ]] && return 0
        return 1
    fi

    local namespace="${extension_id%%.*}"
    local name="${extension_id#*.}"
    local url="https://open-vsx.org/api/$namespace/$name"

    LAST_OPEN_VSX_URL="$url"

    local status
    status=$(curl_safe -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo "000")
    LAST_OPEN_VSX_STATUS="$status"

    if [[ "$status" == "000" ]]; then
        return 0
    fi

    ai_vscode_cache_set "$extension_id" "${status}|$url"

    if [[ "$status" == "200" ]]; then
        return 0
    fi

    return 1
}

resolve_marketplace_vsix_url() {
    local extension_id="$1"

    if ! command -v jq >/dev/null 2>&1; then
        return 1
    fi

    if [[ "$extension_id" != *.* ]]; then
        return 1
    fi

    local publisher="${extension_id%%.*}"
    local name="${extension_id#*.}"

    local payload
    payload=$(cat <<EOF
{
  "filters": [
    {
      "criteria": [
        { "filterType": 7, "value": "${publisher}.${name}" }
      ],
      "pageNumber": 1,
      "pageSize": 1,
      "sortBy": 0,
      "sortOrder": 0
    }
  ],
  "assetTypes": [
    "Microsoft.VisualStudio.Services.VSIXPackage"
  ],
  "flags": 914
}
EOF
)

    local response
    response=$(curl_safe -fsSL \
        -H "Content-Type: application/json" \
        -H "Accept: application/json;api-version=7.1-preview.1" \
        -X POST \
        --data "$payload" \
        "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery" 2>/dev/null) || return 1

    local vsix_url version
    version=$(printf '%s' "$response" | jq -r '.results[0].extensions[0].versions[0].version // empty')
    vsix_url=$(printf '%s' "$response" | jq -r '.results[0].extensions[0].versions[0].files[] | select(.assetType == "Microsoft.VisualStudio.Services.VSIXPackage") | .source' | head -n1)

    if [[ -z "$version" || -z "$vsix_url" || "$version" == "null" || "$vsix_url" == "null" ]]; then
        return 1
    fi

    printf '%s' "$vsix_url"
    return 0
}

VSCODIUM_EXTENSION_INDEX=""
VSCODIUM_EXTENSION_CACHE_LOADED="false"

load_vscodium_extension_cache() {
    if [[ "$VSCODIUM_EXTENSION_CACHE_LOADED" == "true" ]]; then
        return 0
    fi

    if ! command -v codium >/dev/null 2>&1; then
        return 1
    fi

    local list_output
    list_output=$(codium --list-extensions 2>/dev/null || true)
    VSCODIUM_EXTENSION_INDEX=""
    if [[ -n "$list_output" ]]; then
        while IFS= read -r ext; do
            ext=${ext//$'\r'/}
            [[ -z "$ext" ]] && continue
            ext=${ext%@*}
            if [[ -z "$VSCODIUM_EXTENSION_INDEX" ]]; then
                VSCODIUM_EXTENSION_INDEX="$ext"
            else
                VSCODIUM_EXTENSION_INDEX+=$'\n'"$ext"
            fi
        done <<< "$list_output"
    fi

    VSCODIUM_EXTENSION_CACHE_LOADED="true"
    return 0
}

vscodium_extension_installed() {
    local ext_id="$1"
    if [[ -z "$ext_id" ]]; then
        return 1
    fi

    if ! load_vscodium_extension_cache; then
        return 1
    fi

    if [[ -z "$VSCODIUM_EXTENSION_INDEX" ]]; then
        return 1
    fi

    if printf '%s\n' "$VSCODIUM_EXTENSION_INDEX" | grep -Fxq "$ext_id"; then
        return 0
    fi

    return 1
}

mark_vscodium_extension_installed() {
    local ext_id="$1"
    if [[ -z "$ext_id" ]]; then
        return 0
    fi
    if vscodium_extension_installed "$ext_id"; then
        return 0
    fi

    if [[ -z "$VSCODIUM_EXTENSION_INDEX" ]]; then
        VSCODIUM_EXTENSION_INDEX="$ext_id"
    else
        VSCODIUM_EXTENSION_INDEX+=$'\n'"$ext_id"
    fi

    VSCODIUM_EXTENSION_CACHE_LOADED="true"
}

install_extension_from_marketplace() {
    local extension_id="$1"
    local name="$2"

    if ! command -v codium >/dev/null 2>&1; then
        return 1
    fi

    local vsix_url
    if ! vsix_url=$(resolve_marketplace_vsix_url "$extension_id"); then
        return 1
    fi

    local tmp_vsix
    tmp_vsix=$(mktemp --suffix ".vsix") || return 1

    print_info "Downloading VS Marketplace package for $name"
    if ! curl_safe -fsSL "$vsix_url" -o "$tmp_vsix"; then
        rm -f "$tmp_vsix"
        return 1
    fi

    if codium --install-extension "$tmp_vsix" >/dev/null 2>&1; then
        rm -f "$tmp_vsix"
        print_success "$name extension installed via VS Marketplace fallback"
        mark_vscodium_extension_installed "$extension_id"
        return 0
    fi

    rm -f "$tmp_vsix"
    return 1
}

# ============================================================================
# Flatpak Helpers
# ============================================================================

flatpak_remote_exists() {
    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"

    local -a scopes=("--user" "--system" "")
    local scope
    for scope in "${scopes[@]}"; do
        local -a cmd=(flatpak remotes)
        if [[ -n "$scope" ]]; then
            cmd+=("$scope")
        fi
        cmd+=("--columns=name")

        local remote_output=""
        remote_output=$(run_as_primary_user "${cmd[@]}" 2>/dev/null || true)
        if printf '%s\n' "$remote_output" | sed '1d' | grep -Fxq "$remote_name"; then
            return 0
        fi
    done

    return 1
}

print_flatpak_details() {
    local message="$1"

    if [[ -z "$message" ]]; then
        return 0
    fi

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        print_detail "$line"
    done <<<"$message"
}

flatpak_user_repo_path() {
    printf '%s\n' "$HOME/.local/share/flatpak/repo"
}

flatpak_user_repo_initialized() {
    local repo_path
    repo_path=$(flatpak_user_repo_path)

    if [[ -d "$repo_path" ]]; then
        if find "$repo_path" -mindepth 1 -print -quit >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

flatpak_user_app_count() {
    if ! flatpak_cli_available; then
        echo ""
        return 1
    fi

    local list_output
    list_output=$(run_as_primary_user flatpak list --user --app --columns=application 2>/dev/null || true)
    if [[ -z "$list_output" ]]; then
        echo "0"
        return 0
    fi

    local count
    count=$(printf '%s\n' "$list_output" | awk 'NR==1 && ($0=="Application" || $0=="Application ID") {next} NF {c++} END {print c+0}')
    echo "$count"
    return 0
}

report_flatpak_user_state() {
    local repo_path repo_relative
    repo_path=$(flatpak_user_repo_path)
    repo_relative=${repo_path#"$HOME/"}
    if [[ "$repo_relative" == "$repo_path" ]]; then
        repo_relative="$repo_path"
    else
        repo_relative="$HOME/$repo_relative"
    fi

    if flatpak_user_repo_initialized; then
        print_info "Existing Flatpak repository detected (${repo_relative}); preserving contents"
    elif [[ -d "$repo_path" ]]; then
        print_info "Flatpak repository directory exists (${repo_relative}) but is empty"
    else
        print_info "No user-level Flatpak repository detected; initializing ${repo_relative}"
    fi

    if flatpak_cli_available; then
        local app_count
        app_count=$(flatpak_user_app_count)
        if [[ -n "$app_count" ]]; then
            print_info "User Flatpak applications currently installed: $app_count"
        fi
    fi

    if [[ -n "${FLATPAK_INSTALL_ARCH:-}" ]]; then
        print_info "Flatpak target architecture: $FLATPAK_INSTALL_ARCH"
    fi
}

ensure_flatpak_repo_integrity() {
    local repo_dir="$HOME/.local/share/flatpak/repo"

    if [[ ! -e "$repo_dir" ]]; then
        return 0
    fi

    local repo_relative=${repo_dir#"$HOME/"}
    if [[ "$repo_relative" == "$repo_dir" ]]; then
        repo_relative="$repo_dir"
    else
        repo_relative="$HOME/$repo_relative"
    fi

    if [[ -f "$repo_dir/config" && -d "$repo_dir/objects" ]]; then
        safe_chown_user_dir "$repo_dir" || true
        return 0
    fi

    if find "$repo_dir" -mindepth 1 -print -quit >/dev/null 2>&1; then
        print_warning "Flatpak repository at ${repo_relative} exists but is missing required files"
        print_info "Manual fix: rm -rf ${repo_relative} && rerun deployer"
        return 1
    fi

    if rm -rf "$repo_dir" 2>/dev/null; then
        print_warning "Removed empty Flatpak repository stub at ${repo_relative}; it will be recreated"
    else
        print_warning "Unable to remove invalid Flatpak repository at ${repo_relative}"
        return 1
    fi

    return 0
}

ensure_flatpak_user_dirs() {
    local base_dir="$HOME/.local/share/flatpak"
    local config_dir="$HOME/.config/flatpak"

    local -a required_dirs=("$base_dir" "$config_dir")
    local -a created_dirs=()
    local dir
    for dir in "${required_dirs[@]}"; do
        local existed_before=true

        # Handle broken symlinks
        if [[ -L "$dir" && ! -e "$dir" ]]; then
            print_warning "Removing broken symlink: $dir"
            rm -f "$dir" || {
                print_error "Unable to remove broken symlink: $dir"
                return 1
            }
            existed_before=false
        elif [[ ! -d "$dir" ]]; then
            existed_before=false
        fi

        if ! safe_mkdir "$dir"; then
            print_error "Unable to prepare Flatpak directory: $dir"
            return 1
        fi

        if [[ "$existed_before" == false ]]; then
            created_dirs+=("$dir")
        fi
    done

    chmod 700 "$base_dir" "$config_dir" 2>/dev/null || true
    local -a ownership_dirs=("$base_dir" "$config_dir")
    for dir in "${ownership_dirs[@]}"; do
        safe_chown_user_dir "$dir" || true
    done

    if ! ensure_flatpak_repo_integrity; then
        return 1
    fi

    if (( ${#created_dirs[@]} > 0 )); then
        local -a relative_created=()
        local created
        for dir in "${created_dirs[@]}"; do
            local rel
            rel=${dir#"$HOME/"}
            if [[ "$rel" == "$dir" ]]; then
                relative_created+=("$dir")
            else
                relative_created+=("$HOME/$rel")
            fi
        done
        created=$(printf '%s, ' "${relative_created[@]}")
        created=${created%, }
        print_success "Initialized Flatpak directories: ${created}"
    else
        print_info "Flatpak directories already exist; preserving current state"
    fi

    return 0
}

ensure_flathub_remote() {
    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; skipping Flathub repository configuration"
        return 1
    fi

    if ! ensure_flatpak_user_dirs; then
        print_warning "Flatpak directories missing or inaccessible; skipping Flathub configuration"
        return 1
    fi

    if flatpak_remote_exists; then
        print_success "Flathub repository already configured"
        return 0
    fi

    print_info "Adding Flathub Flatpak remote..."

    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"
    local -a sources=("${FLATHUB_REMOTE_URL:-https://dl.flathub.org/repo/flathub.flatpakrepo}")

    if [[ -n "${FLATHUB_REMOTE_FALLBACK_URL:-}" && "${FLATHUB_REMOTE_FALLBACK_URL}" != "${sources[0]}" ]]; then
        sources+=("$FLATHUB_REMOTE_FALLBACK_URL")
    fi

    local source scope output status
    local -a scopes=("--user" "")

    for source in "${sources[@]}"; do
        for scope in "${scopes[@]}"; do
            local -a cmd=(flatpak remote-add)
            if [[ -n "$scope" ]]; then
                cmd+=("$scope")
            fi
            cmd+=("--if-not-exists" "$remote_name" "$source")

            output=$(run_as_primary_user "${cmd[@]}" 2>&1)
            status=$?

            if [[ $status -eq 0 ]]; then
                if flatpak_remote_exists; then
                    if [[ "$source" == "${sources[0]}" ]]; then
                        print_success "Flathub repository added"
                    else
                        print_success "Flathub repository added via fallback source ($source)"
                    fi
                    return 0
                fi
            else
                print_flatpak_details "$output"
            fi
        done
    done

    if flatpak_remote_exists; then
        print_success "Flathub repository already configured"
        return 0
    fi

    print_warning "Unable to configure Flathub repository automatically"
    return 1
}

flatpak_append_arch_flag() {
    local -n target_ref="$1"
    if [[ -n "${FLATPAK_INSTALL_ARCH:-}" ]]; then
        target_ref+=("--arch" "$FLATPAK_INSTALL_ARCH")
    fi
}

flatpak_should_retry_without_deltas() {
    local output="$1"

    if [[ -z "$output" ]]; then
        return 1
    fi

    if printf '%s\n' "$output" | grep -Eiq 'repo/deltas|static delta|delta.+failed'; then
        return 0
    fi

    return 1
}

flatpak_run_install_command() {
    local output_var="$1"
    shift
    local -a cmd=("$@")
    local deltas_disabled=0

    while :; do
        local install_output
        install_output=$(run_as_primary_user "${cmd[@]}" 2>&1)
        local status=$?
        printf -v "$output_var" '%s' "$install_output"

        if [[ $status -eq 0 ]]; then
            return 0
        fi

        if [[ $deltas_disabled -eq 0 ]] && flatpak_should_retry_without_deltas "$install_output"; then
            deltas_disabled=1
            cmd+=("--no-static-deltas")
            print_info "  Static delta fetch failed; retrying without deltas..."
            continue
        fi

        return $status
    done
}

flatpak_profile_apps() {
    local profile="${1:-${SELECTED_FLATPAK_PROFILE:-$DEFAULT_FLATPAK_PROFILE}}"
    local array_name="${FLATPAK_PROFILE_APPSETS["$profile"]:-}"

    if [[ -z "$array_name" ]]; then
        return 1
    fi

    local -n profile_ref="$array_name"
    printf '%s\n' "${profile_ref[@]}"
}

flatpak_profile_digest() {
    if (( $# == 0 )); then
        echo ""
        return 0
    fi

    local sorted
    sorted=$(printf '%s\n' "$@" | LC_ALL=C sort -u)
    printf '%s' "$sorted" | sha256sum | awk '{print $1}'
}

flatpak_profile_state_valid() {
    local digest="$1"
    local profile="${SELECTED_FLATPAK_PROFILE:-$DEFAULT_FLATPAK_PROFILE}"

    if [[ -z "$digest" || -z "$profile" ]]; then
        return 1
    fi

    if [[ -z "$FLATPAK_PROFILE_STATE_FILE" || ! -f "$FLATPAK_PROFILE_STATE_FILE" ]]; then
        return 1
    fi

    local saved_profile=""
    local saved_digest=""

    while IFS='=' read -r key value; do
        value=$(printf '%s' "$value" | tr -d '\r')
        case "$key" in
            PROFILE) saved_profile="$value" ;;
            DIGEST) saved_digest="$value" ;;
        esac
    done <"$FLATPAK_PROFILE_STATE_FILE"

    [[ "$saved_profile" == "$profile" && "$saved_digest" == "$digest" ]]
}

update_flatpak_profile_state() {
    local digest="$1"
    local profile="${SELECTED_FLATPAK_PROFILE:-$DEFAULT_FLATPAK_PROFILE}"

    if [[ -z "$digest" || -z "$profile" || -z "$FLATPAK_PROFILE_STATE_FILE" ]]; then
        return 0
    fi

    local pref_dir
    pref_dir=$(dirname "$FLATPAK_PROFILE_STATE_FILE")
    if ! safe_mkdir "$pref_dir"; then
        return 0
    fi

    if cat >"$FLATPAK_PROFILE_STATE_FILE" <<EOF
PROFILE=$profile
DIGEST=$digest
COUNT=${#DEFAULT_FLATPAK_APPS[@]}
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
    then
        chmod 600 "$FLATPAK_PROFILE_STATE_FILE" 2>/dev/null || true
        safe_chown_user_dir "$FLATPAK_PROFILE_STATE_FILE" || true
    fi
}

select_flatpak_profile() {
    local mode="${1:---interactive}"
    local interactive="true"

    # Ensure Flatpak architecture and profiles are normalized before selection
    if declare -F prune_arch_incompatible_flatpaks >/dev/null 2>&1; then
        prune_arch_incompatible_flatpaks
    elif [[ -z "${FLATPAK_INSTALL_ARCH:-}" ]] && declare -F detect_flatpak_install_arch >/dev/null 2>&1; then
        detect_flatpak_install_arch
    fi

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

    local profile="${SELECTED_FLATPAK_PROFILE:-}"

    if [[ -z "$profile" && -f "$FLATPAK_PROFILE_PREFERENCE_FILE" ]]; then
        profile=$(awk -F'=' '/^SELECTED_FLATPAK_PROFILE=/{print $2}' "$FLATPAK_PROFILE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    fi

    local persist_choice="true"

    if [[ "$interactive" == "true" ]]; then
        local -a profile_order=("core" "ai_workstation" "gaming" "minimal")
        local -a profile_keys=()
        local index=1
        print_info "Available Flatpak provisioning profiles:"
        local key
        for key in "${profile_order[@]}"; do
            local label="${FLATPAK_PROFILE_LABELS["$key"]:-$key}"
            local array_name="${FLATPAK_PROFILE_APPSETS["$key"]:-}"
            local count=0
            if [[ -n "$array_name" ]]; then
                local -n ref="$array_name"
                count=${#ref[@]}
            fi
            echo "  ${index}) ${label} (${count} apps)"
            profile_keys+=("$key")
            ((index++))
        done

        local desired_default="${profile:-${DEFAULT_FLATPAK_PROFILE:-core}}"
        local default_index=1
        local i
        for i in "${!profile_keys[@]}"; do
            if [[ "${profile_keys[$i]}" == "$desired_default" ]]; then
                default_index=$((i + 1))
                break
            fi
        done

        local selection
        selection=$(prompt_user "Select Flatpak profile (1-${#profile_keys[@]})" "$default_index")

        if [[ "$selection" =~ ^[0-9]+$ ]] && (( selection >= 1 && selection <= ${#profile_keys[@]} )); then
            profile="${profile_keys[$((selection - 1))]}"
        else
            print_warning "Invalid selection; using default profile '${DEFAULT_FLATPAK_PROFILE}'"
            profile="${DEFAULT_FLATPAK_PROFILE:-core}"
        fi
    else
        if [[ -z "$profile" ]]; then
            profile="${DEFAULT_FLATPAK_PROFILE:-core}"
            persist_choice="false"
            print_info "Flatpak profile not set; defaulting to '$profile'. Run Phase 1 to choose a different profile."
        else
            print_info "Using cached Flatpak profile '$profile'"
        fi
    fi

    if [[ -z "${FLATPAK_PROFILE_APPSETS["$profile"]:-}" ]]; then
        print_warning "Unknown Flatpak profile '$profile', falling back to 'core'"
        profile="core"
    fi

    SELECTED_FLATPAK_PROFILE="$profile"

    local array_name="${FLATPAK_PROFILE_APPSETS["$profile"]}"
    local -n chosen="$array_name"
    declare -A _flatpak_profile_seen=()
    DEFAULT_FLATPAK_APPS=()

    local candidate
    for candidate in "${FLATPAK_PROFILE_CORE_APPS[@]}"; do
        if [[ -z "$candidate" || -n "${_flatpak_profile_seen["$candidate"]:-}" ]]; then
            continue
        fi
        _flatpak_profile_seen["$candidate"]=1
        DEFAULT_FLATPAK_APPS+=("$candidate")
    done

    for candidate in "${chosen[@]}"; do
        if [[ -z "$candidate" || -n "${_flatpak_profile_seen["$candidate"]:-}" ]]; then
            continue
        fi
        _flatpak_profile_seen["$candidate"]=1
        DEFAULT_FLATPAK_APPS+=("$candidate")
    done

    print_info "Selected Flatpak profile '$profile' (${#DEFAULT_FLATPAK_APPS[@]} apps)"

    if [[ "$persist_choice" == "true" && -n "$FLATPAK_PROFILE_PREFERENCE_FILE" ]]; then
        local pref_dir
        pref_dir=$(dirname "$FLATPAK_PROFILE_PREFERENCE_FILE")
        if safe_mkdir "$pref_dir"; then
            if cat >"$FLATPAK_PROFILE_PREFERENCE_FILE" <<EOF
SELECTED_FLATPAK_PROFILE=$profile
EOF
            then
                chmod 600 "$FLATPAK_PROFILE_PREFERENCE_FILE" 2>/dev/null || true
                safe_chown_user_dir "$FLATPAK_PROFILE_PREFERENCE_FILE" || true
            fi
        fi
    fi

    return 0
}

flatpak_query_application_support() {
    local app_id="$1"

    LAST_FLATPAK_QUERY_MESSAGE=""

    if [[ -z "${FLATPAK_INSTALL_ARCH:-}" ]] && declare -F detect_flatpak_install_arch >/dev/null 2>&1; then
        detect_flatpak_install_arch
    fi

    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"
    local -a arch_args=()
    if [[ -n "${FLATPAK_INSTALL_ARCH:-}" ]]; then
        arch_args=("--arch" "$FLATPAK_INSTALL_ARCH")
    fi
    local user_output system_output user_status system_status

    user_output=$(run_as_primary_user flatpak --user remote-info "${arch_args[@]}" "$remote_name" "$app_id" 2>&1 || true)
    user_status=$?
    if [[ $user_status -eq 0 ]]; then
        return 0
    fi

    system_output=$(run_as_primary_user flatpak remote-info "${arch_args[@]}" "$remote_name" "$app_id" 2>&1 || true)
    system_status=$?
    if [[ $system_status -eq 0 ]]; then
        return 0
    fi

    LAST_FLATPAK_QUERY_MESSAGE="$user_output"
    if [[ -n "$LAST_FLATPAK_QUERY_MESSAGE" && -n "$system_output" ]]; then
        LAST_FLATPAK_QUERY_MESSAGE+=$'\n'
    fi
    LAST_FLATPAK_QUERY_MESSAGE+="$system_output"

    if printf '%s\n' "$LAST_FLATPAK_QUERY_MESSAGE" | grep -Eiq 'No remote refs found similar|No entry for|Nothing matches'; then
        return 3
    fi

    return 1
}

flatpak_bulk_install_apps() {
    local remote_name="${1:-}"
    shift
    local -a apps=("$@")
    
    # Validate inputs
    if ! validate_non_empty "remote_name" "$remote_name" 2>/dev/null; then
        log ERROR "flatpak_bulk_install_apps: remote_name required"
        return 1
    fi

    if [[ ${#apps[@]} -eq 0 ]]; then
        return 0
    fi

    print_info "  Installing ${#apps[@]} Flatpak application(s) in batch..."
    local -a install_cmd=(flatpak --noninteractive --assumeyes --no-static-deltas install --user)
    flatpak_append_arch_flag install_cmd
    install_cmd+=("$remote_name" "${apps[@]}")
    local install_output=""
    if flatpak_run_install_command install_output "${install_cmd[@]}"; then
        print_success "  ✓ Batch installed ${#apps[@]} Flatpak application(s)"
        if [[ -n "$install_output" ]]; then
            print_flatpak_details "$install_output"
        fi
        return 0
    fi

    local install_status=$?
    print_warning "  ⚠ Batch install for ${#apps[@]} Flatpak application(s) failed (exit $install_status)"
    if [[ -n "$install_output" ]]; then
        print_flatpak_details "$install_output"
    fi
    return $install_status
}

flatpak_install_single_app() {
    local remote_name="$1"
    local app_id="$2"

    local -a install_cmd=(flatpak --noninteractive --assumeyes --no-static-deltas install --user)
    flatpak_append_arch_flag install_cmd
    install_cmd+=("$remote_name" "$app_id")
    local install_output=""
    if flatpak_run_install_command install_output "${install_cmd[@]}"; then
        print_success "  • Installed $app_id"
        if [[ -n "$install_output" ]]; then
            print_flatpak_details "$install_output"
        fi
        return 0
    fi

    local status=$?
    print_warning "  ⚠ Failed to install $app_id (exit $status)"
    if [[ -n "$install_output" ]]; then
        print_flatpak_details "$install_output"
    fi
    return $status
}

flatpak_install_app_list() {
    if [[ $# -eq 0 ]]; then
        return 0
    fi

    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; cannot install applications"
        return 1
    fi

    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"
    local failure=0
    local app_id

    run_as_primary_user flatpak --user repair >/dev/null 2>&1 || true

    declare -A flatpak_support_status=()
    local -a primary_queue=()
    local -a deferred_queue=()

    for app_id in "$@"; do
        flatpak_query_application_support "$app_id"
        local support_status=$?
        flatpak_support_status["$app_id"]=$support_status
        case "$support_status" in
            0)
                primary_queue+=("$app_id")
                ;;
            3)
                print_warning "  ⚠ $app_id is not available on $remote_name for this architecture; skipping"
                print_flatpak_details "$LAST_FLATPAK_QUERY_MESSAGE"
                flatpak_support_status["$app_id"]="skip"
                ;;
            *)
                print_warning "  ⚠ Unable to query metadata for $app_id; deferring install until remaining apps finish"
                print_flatpak_details "$LAST_FLATPAK_QUERY_MESSAGE"
                deferred_queue+=("$app_id")
                ;;
        esac
    done

    local process_label queue_app_id
    for process_label in primary deferred; do
        local -a queue=()
        if [[ "$process_label" == "primary" ]]; then
            queue=("${primary_queue[@]}")
        else
            queue=("${deferred_queue[@]}")
            if [[ ${#queue[@]} -gt 0 ]]; then
                print_info "  Retrying deferred Flatpak installs (metadata queries previously failed)..."
            fi
        fi

        local batch_size=5
        local start=0
        local total=${#queue[@]}
        while [[ $start -lt $total ]]; do
            local end=$(( start + batch_size ))
            if [[ $end -gt $total ]]; then end=$total; fi
            local -a batch=("${queue[@]:start:end-start}")

            if [[ "$process_label" == "primary" && ${#batch[@]} -gt 1 ]]; then
                if flatpak_bulk_install_apps "$remote_name" "${batch[@]}"; then
                    local -a still_missing=()
                    for queue_app_id in "${batch[@]}"; do
                        if ! flatpak_app_installed "$queue_app_id"; then
                            still_missing+=("$queue_app_id")
                        fi
                    done
                    batch=("${still_missing[@]}")
                fi
            fi

            if [[ ${#batch[@]} -eq 0 ]]; then
                :
            else
                for queue_app_id in "${batch[@]}"; do
                    if flatpak_install_single_app "$remote_name" "$queue_app_id"; then
                        :
                    else
                        failure=1
                    fi
                done
            fi

            start=$end
        done

        for queue_app_id in "${queue[@]}"; do
            if [[ "${flatpak_support_status["$queue_app_id"]:-}" == "skip" ]]; then
                continue
            fi

            if flatpak_app_installed "$queue_app_id"; then
                print_info "  • $queue_app_id already present (skipping)"
                continue
            fi

            print_info "  Installing $queue_app_id from $remote_name..."
            local attempt
            local installed=0
            for attempt in 1 2 3; do
                local -a install_cmd=(flatpak --noninteractive --assumeyes --no-static-deltas install --user)
                flatpak_append_arch_flag install_cmd
                install_cmd+=("$remote_name" "$queue_app_id")
                local install_output
                if flatpak_run_install_command install_output "${install_cmd[@]}"; then
                    print_success "  ✓ Installed $queue_app_id"
                    installed=1
                    break
                fi

                if printf '%s\n' "$install_output" | grep -Eiq 'No remote refs found similar|No entry for|Nothing matches'; then
                    print_warning "  ⚠ $queue_app_id is not available on $remote_name for this architecture; skipping"
                    print_flatpak_details "$install_output"
                    installed=1
                    break
                fi

                print_warning "  ⚠ Attempt $attempt failed for $queue_app_id"
                print_flatpak_details "$install_output"
                sleep $(( attempt * 2 ))
            done

            if [[ $installed -ne 1 ]]; then
                print_warning "  ⚠ Failed to install $queue_app_id after retries"
                failure=1
            fi
        done
    done

    return $failure
}

purge_vscodium_flatpak_conflicts() {
    if ! flatpak_cli_available; then
        return 0
    fi

    if ! declare -p FLATPAK_VSCODIUM_CONFLICT_IDS >/dev/null 2>&1; then
        return 0
    fi

    local -a user_removed=()
    local -a system_installed=()
    local app_id
    local removal_failed=0

    for app_id in "${FLATPAK_VSCODIUM_CONFLICT_IDS[@]}"; do
        if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            print_info "Removing conflicting Flatpak $app_id (user scope)..."
            local uninstall_output=""
            if uninstall_output=$(run_as_primary_user flatpak --noninteractive --assumeyes --user uninstall "$app_id" 2>&1); then
                print_success "  • Removed $app_id (user scope)"
                user_removed+=("$app_id")
            else
                print_warning "  ⚠ Failed to remove $app_id (user scope)"
                print_flatpak_details "$uninstall_output"
                removal_failed=1
            fi
        fi

        if run_as_primary_user flatpak info --system "$app_id" >/dev/null 2>&1; then
            system_installed+=("$app_id")
        fi
    done

    if [[ ${#user_removed[@]} -gt 0 ]]; then
        local removed_list
        removed_list=$(printf '%s, ' "${user_removed[@]}")
        removed_list=${removed_list%, }
        print_info "User-level Visual Studio Code Flatpaks removed: ${removed_list}"
    fi

    if [[ ${#system_installed[@]} -gt 0 ]]; then
        local system_list
        system_list=$(printf '%s, ' "${system_installed[@]}")
        system_list=${system_list%, }
        print_warning "System-wide Flatpak installs still include Visual Studio Code variants: ${system_list}"
        print_info "Remove them manually with: sudo flatpak uninstall --system <app-id>"
    fi

    return $removal_failed
}

filter_vscodium_conflicting_flatpaks() {
    if [[ ${#DEFAULT_FLATPAK_APPS[@]} -eq 0 ]]; then
        return 0
    fi

    if ! declare -p FLATPAK_VSCODIUM_CONFLICT_IDS >/dev/null 2>&1; then
        return 0
    fi

    local -a filtered=()
    local -a removed=()
    local app conflict

    for app in "${DEFAULT_FLATPAK_APPS[@]}"; do
        local skip=false
        for conflict in "${FLATPAK_VSCODIUM_CONFLICT_IDS[@]}"; do
            if [[ "$app" == "$conflict" ]]; then
                skip=true
                removed+=("$app")
                break
            fi
        done

        if [[ "$skip" == false ]]; then
            filtered+=("$app")
        fi
    done

    if [[ ${#removed[@]} -gt 0 ]]; then
        DEFAULT_FLATPAK_APPS=("${filtered[@]}")
        local removed_list
        removed_list=$(printf '%s, ' "${removed[@]}")
        removed_list=${removed_list%, }
        print_warning "Removed conflicting Flatpak apps from selected profile: ${removed_list}"
        print_info "Visual Studio Code and VSCodium should remain managed declaratively via programs.vscode."
    fi

    return 0
}

ensure_default_flatpak_apps_installed() {
    if declare -F select_flatpak_profile >/dev/null 2>&1 && [[ -z "${SELECTED_FLATPAK_PROFILE:-}" ]]; then
        select_flatpak_profile --noninteractive || true
    fi

    if [[ ${#DEFAULT_FLATPAK_APPS[@]} -eq 0 ]]; then
        print_info "No default Flatpak applications defined"
        return 0
    fi

    if ! purge_vscodium_flatpak_conflicts; then
        print_warning "Some conflicting Visual Studio Code Flatpaks could not be removed automatically"
    fi

    filter_vscodium_conflicting_flatpaks

    local profile_name="${SELECTED_FLATPAK_PROFILE:-$DEFAULT_FLATPAK_PROFILE}"
    local profile_digest
    profile_digest=$(flatpak_profile_digest "${DEFAULT_FLATPAK_APPS[@]}")
    local profile_current=false
    if flatpak_profile_state_valid "$profile_digest"; then
        profile_current=true
    fi

    local -a missing=()
    local app_id
    local -A installed_flatpak_index=()

    if flatpak_cli_available; then
        local scope
        for scope in user system; do
            local list_flags=("--app" "--columns=application")
            if [[ "$scope" == "user" ]]; then
                list_flags=("--user" "${list_flags[@]}")
            else
                list_flags=("--system" "${list_flags[@]}")
            fi

            local installed_listing=""
            installed_listing=$(run_as_primary_user flatpak list "${list_flags[@]}" 2>/dev/null || true)
            if [[ -z "$installed_listing" ]]; then
                continue
            fi

            while IFS= read -r line; do
                line=${line//$'\r'/}
                line=${line//$'\v'/}
                line=${line//$'\f'/}
                [[ -z "$line" ]] && continue

                case "$line" in
                    "Application"|$'Application ID'|$'Application\tID')
                        continue
                        ;;
                esac

                local app_id
                IFS=$' \t' read -r app_id _ <<<"$line"
                if [[ -z "$app_id" ]]; then
                    continue
                fi

                local current="${installed_flatpak_index["$app_id"]:-}"
                if [[ "$scope" == "user" ]]; then
                    if [[ "$current" == "system" ]]; then
                        installed_flatpak_index["$app_id"]="both"
                    elif [[ -z "$current" ]]; then
                        installed_flatpak_index["$app_id"]="user"
                    else
                        installed_flatpak_index["$app_id"]="$current"
                    fi
                else
                    if [[ "$current" == "user" ]]; then
                        installed_flatpak_index["$app_id"]="both"
                    elif [[ -z "$current" ]]; then
                        installed_flatpak_index["$app_id"]="system"
                    else
                        installed_flatpak_index["$app_id"]="$current"
                    fi
                fi
            done <<< "$installed_listing"
        done
    fi

    local detection_mode="list"
    if [[ ${#installed_flatpak_index[@]} -eq 0 ]]; then
        detection_mode="info"
    fi

    for app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
        if [[ "$detection_mode" == "list" ]]; then
            local scope="${installed_flatpak_index["$app_id"]:-}"
            if [[ -n "$scope" ]]; then
                local scope_note=""
                case "$scope" in
                    user) scope_note=" (user scope)" ;;
                    system) scope_note=" (system scope)" ;;
                    both) scope_note=" (user + system scopes)" ;;
                esac
                print_info "  • $app_id already present${scope_note}"
                continue
            fi
        else
            if flatpak_app_installed "$app_id"; then
                print_info "  • $app_id already present"
                continue
            fi
        fi
        missing+=("$app_id")
    done

    if (( ${#missing[@]} == 0 )); then
        if $profile_current; then
            print_success "Flatpak profile '${profile_name}' already satisfied (${#DEFAULT_FLATPAK_APPS[@]} apps)"
        else
            print_info "All Flatpak applications for profile '${profile_name}' are present"
            update_flatpak_profile_state "$profile_digest"
            run_as_primary_user flatpak --user update --noninteractive --appstream >/dev/null 2>&1 || true
            run_as_primary_user flatpak --user update --noninteractive >/dev/null 2>&1 || true
        fi
        return 0
    fi

    if flatpak_install_app_list "${missing[@]}"; then
        print_success "Default Flatpak applications are now installed and ready"
        run_as_primary_user flatpak --user update --noninteractive --appstream >/dev/null 2>&1 || true
        run_as_primary_user flatpak --user update --noninteractive >/dev/null 2>&1 || true
        update_flatpak_profile_state "$profile_digest"
        return 0
    fi

    print_warning "Some Flatpak applications could not be installed automatically"
    print_info "You can retry manually with: flatpak install --user ${FLATHUB_REMOTE_NAME:-flathub} <app-id>"
    return 1
}

configure_podman_desktop_flatpak() {
    local app_id="io.podman_desktop.PodmanDesktop"

    if ! flatpak_cli_available; then
        return 0
    fi

    if ! flatpak_app_installed "$app_id"; then
        return 0
    fi

    print_info "Configuring Podman Desktop Flatpak permissions"
    if ! run_as_primary_user flatpak override --user --filesystem=xdg-run/podman "$app_id" >/dev/null 2>&1; then
        print_warning "Unable to grant Podman socket access to Podman Desktop"
    fi

    if ! command -v podman >/dev/null 2>&1; then
        return 0
    fi

    run_as_primary_user systemctl --user enable --now podman.socket >/dev/null 2>&1 || true

    local user_uid socket_path
    user_uid=$(run_as_primary_user id -u 2>/dev/null || echo "")
    if [[ -z "$user_uid" ]]; then
        return 0
    fi

    socket_path="/run/user/${user_uid}/podman/podman.sock"
    if [[ ! -S "$socket_path" ]]; then
        print_warning "Podman socket not found at ${socket_path}"
        return 0
    fi

    local connection_list
    connection_list=$(run_as_primary_user podman system connection list --format "{{.Name}}" 2>/dev/null | sed '/^$/d' || true)
    if [[ -z "$connection_list" ]]; then
        run_as_primary_user podman system connection add local "unix://${socket_path}" --default >/dev/null 2>&1 || \
            print_warning "Unable to register the default Podman connection for Podman Desktop"
    fi
}

# ============================================================================
# Install Flatpak Applications
# ============================================================================
# Purpose: Install Flatpak applications from home.nix configuration
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_flatpak_stage() {
    print_section "Installing Flatpak Applications"

    # Validate flatpak command availability using validation helper
    if ! validate_command_available "flatpak" 2>/dev/null; then
        if ! command -v flatpak >/dev/null 2>&1; then
            print_warning "Flatpak CLI not found in PATH"
            print_info "Install Flatpak or re-run home-manager switch to enable declarative apps"
            return 1
        fi
    fi

    # Always use direct flatpak remote installation instead of systemd service.
    # This avoids timeout issues with large batch installations and provides
    # better error handling and progress reporting.
    print_info "Using direct Flathub remote for installation (bypassing systemd service)"

    report_flatpak_user_state

    if ! ensure_flathub_remote; then
        print_warning "Flatpak applications will need to be installed manually once Flathub is available"
        return 1
    fi

    if [[ -n "${FLATPAK_ARCH_PRUNED_APPS[*]:-}" ]]; then
        local pruned_list
        pruned_list=$(printf '%s, ' "${FLATPAK_ARCH_PRUNED_APPS[@]}")
        pruned_list=${pruned_list%, }
        print_info "Skipping architecture-restricted Flatpak applications: ${pruned_list}"
    fi

    if declare -F select_flatpak_profile >/dev/null 2>&1; then
        select_flatpak_profile --noninteractive || true
    fi

    local install_status=1
    if ensure_default_flatpak_apps_installed; then
        install_status=0
    fi

    configure_podman_desktop_flatpak
    return "$install_status"
}

# ============================================================================
# Install AI Coding CLIs (Claude, GPT CodeX, OpenAI, GooseAI)
# ============================================================================
# Purpose: Install fast-moving AI CLI packages from npm and wire wrappers
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
ensure_npm_global_prefix() {
    local default_prefix
    default_prefix="${PRIMARY_HOME:-$HOME}/.npm-global"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$default_prefix}"

    export NPM_CONFIG_PREFIX="$npm_prefix"

    if ! run_as_primary_user install -d -m 755 "$npm_prefix" "$npm_prefix/bin" \
        "$npm_prefix/lib" "$npm_prefix/lib/node_modules" >/dev/null 2>&1; then
        install -d -m 755 "$npm_prefix" "$npm_prefix/bin" "$npm_prefix/lib" \
            "$npm_prefix/lib/node_modules" >/dev/null 2>&1 || true
        safe_chown_user_dir "$npm_prefix" >/dev/null 2>&1 || true
    fi

    run_as_primary_user env NPM_PREFIX="$npm_prefix" bash <<'EOS' >/dev/null 2>&1 || true
set -euo pipefail
npmrc="$HOME/.npmrc"
tmp_file="${npmrc}.tmp"

if [ ! -f "$npmrc" ]; then
    printf 'prefix=%s\n' "$NPM_PREFIX" >"$npmrc"
    exit 0
fi

if grep -q '^prefix=' "$npmrc" 2>/dev/null; then
    awk -v prefix="$NPM_PREFIX" '
        BEGIN { updated = 0 }
        /^prefix=/ { print "prefix=" prefix; updated = 1; next }
        { print }
        END { if (!updated) print "prefix=" prefix }
    ' "$npmrc" >"$tmp_file"
    mv "$tmp_file" "$npmrc"
    exit 0
fi

printf '\n# Added by NixOS Quick Deploy\nprefix=%s\n' "$NPM_PREFIX" >>"$npmrc"
EOS

    case ":$PATH:" in
        *":$npm_prefix/bin:"*) ;;
        *) export PATH="$npm_prefix/bin:$PATH" ;;
    esac
}

ai_cli_manifest_path() {
    local lib_dir
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root
    repo_root="$(cd "$lib_dir/.." && pwd)"
    local manifest_dir="${CONFIG_DIR:-$repo_root/config}"
    echo "$manifest_dir/npm-packages.sh"
}

ai_validate_var_name() {
    local candidate="$1"
    [[ "$candidate" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

load_npm_manifest() {
    local manifest="$1"
    NPM_AI_PACKAGE_MANIFEST=()

    if [[ -z "$manifest" || ! -f "$manifest" ]]; then
        return 0
    fi

    local line entry
    while IFS= read -r line; do
        if [[ "$line" =~ \"([^\"]+)\" ]]; then
            entry="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ \'([^\']+)\' ]]; then
            entry="${BASH_REMATCH[1]}"
        else
            entry=""
        fi
        if [[ -n "$entry" ]]; then
            NPM_AI_PACKAGE_MANIFEST+=("$entry")
        fi
        done < <(awk '
            BEGIN { in_list=0 }
            /^[[:space:]]*NPM_AI_PACKAGE_MANIFEST[[:space:]]*=[[:space:]]*[(][[:space:]]*$/ { in_list=1; next }
            in_list {
                if ($0 ~ /^[[:space:]]*[)][[:space:]]*$/) { in_list=0; next }
                print
            }
        ' "$manifest")
}

resolve_ai_cli_path() {
    local package_dir="$1"
    local bin_command="$2"

    node - "$package_dir" "$bin_command" <<'NODE'
const fs = require('fs');
const path = require('path');

const pkgDir = process.argv[2];
const desired = process.argv[3];
const pkgJson = path.join(pkgDir, 'package.json');

try {
  const pkg = JSON.parse(fs.readFileSync(pkgJson, 'utf8'));
  let bin = pkg.bin;

  if (!bin) {
    process.exit(1);
  }

  let relative;
  if (typeof bin === 'string') {
    relative = bin;
  } else if (bin[desired]) {
    relative = bin[desired];
  } else {
    const keys = Object.keys(bin);
    if (keys.length === 0) {
      process.exit(2);
    }
    relative = bin[keys[0]];
  }

  const absolute = path.resolve(pkgDir, relative);
  process.stdout.write(absolute);
} catch (error) {
  process.exit(3);
}
NODE
}

run_npm_audit_global() {
    local display="$1"
    local audit_log="$2"
    local npm_prefix="$3"

    if run_as_primary_user env NPM_CONFIG_PREFIX="$npm_prefix" npm audit --global --audit-level=high \
        > >(tee "$audit_log") 2>&1; then
        return 0
    fi

    if grep -qiE "EAUDITGLOBAL|does not support testing globals" "$audit_log" 2>/dev/null; then
        print_info "$display npm audit skipped (npm does not support --global audits)"
        return 0
    fi

    print_warning "$display npm audit reported issues (see $audit_log)"
    return 1
}

create_ai_cli_wrapper() {
    local wrapper_path="$1"
    local cli_path="$2"
    local display_name="$3"
    local debug_env_var="${4:-}"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local npm_modules="$npm_prefix/lib/node_modules"

    cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

DEBUG_FLAG="\${AI_TOOL_DEBUG:-0}"
DEBUG_ENV_VAR="${debug_env_var}"

if [ -n "\${DEBUG_ENV_VAR}" ]; then
    DEBUG_ENV_VALUE="\${!DEBUG_ENV_VAR:-}"
    if [ -n "\${DEBUG_ENV_VALUE}" ]; then
        DEBUG_FLAG="\${DEBUG_ENV_VALUE}"
    fi
fi

if [ "\${DEBUG_FLAG}" = "1" ]; then
    echo "[DEBUG] Wrapper starting for $display_name" >&2
    echo "[DEBUG] CLI path: $cli_path" >&2
fi

CLI_PATH="$cli_path"

if [ ! -f "\${CLI_PATH}" ]; then
    echo "[$display_name] CLI entry point missing: \${CLI_PATH}" >&2
    echo "Reinstall with: npm install -g" >&2
    exit 127
fi

# Normalize and strip wrapper arguments added by editor integrations before
# invoking the real CLI so they don't leak into the process invocation.
normalize_cli_arg() {
    local candidate="\$1"
    if command -v readlink >/dev/null 2>&1; then
        readlink -f "\$candidate" 2>/dev/null || printf '%s\n' "\$candidate"
    else
        printf '%s\n' "\$candidate"
    fi
}

CANONICAL_CLI_PATH="\${CLI_PATH}"
if command -v readlink >/dev/null 2>&1; then
    CANONICAL_CLI_PATH="\$(readlink -f "\${CLI_PATH}" 2>/dev/null || printf '%s\n' "\${CLI_PATH}")"
fi

if [ "\$#" -ge 2 ] && [ "\$1" = "node" ]; then
    maybe_cli="\$2"
    normalized="\$(normalize_cli_arg "\$maybe_cli")"
    if [ "\$maybe_cli" = "\$CLI_PATH" ] || [ "\$normalized" = "\$CANONICAL_CLI_PATH" ]; then
        shift 2
    fi
fi

if [ "\$#" -ge 1 ]; then
    first_arg="\$1"
    normalized_first="\$(normalize_cli_arg "\$first_arg")"
    if [ "\$first_arg" = "\$CLI_PATH" ] || [ "\$normalized_first" = "\$CANONICAL_CLI_PATH" ]; then
        shift
    fi
fi

NODE_CANDIDATES=(
    "\${HOME}/.nix-profile/bin/node"
    "/run/current-system/sw/bin/node"
    "/nix/var/nix/profiles/default/bin/node"
)

if command -v node >/dev/null 2>&1; then
    NODE_CANDIDATES+=("\$(command -v node)")
fi

NODE_BIN=""
for candidate in "\${NODE_CANDIDATES[@]}"; do
    if [ -n "\${candidate}" ] && [ -x "\${candidate}" ]; then
        NODE_BIN="\${candidate}"
        break
    fi
done

if [ -z "\${NODE_BIN}" ]; then
    echo "[$display_name] Unable to locate Node.js runtime" >&2
    echo "Ensure Node.js 22 is installed via home-manager" >&2
    exit 127
fi

export PATH="$npm_prefix/bin:\${PATH}"
export NODE_PATH="$npm_modules"

if [ "\${DEBUG_FLAG}" = "1" ]; then
    echo "[DEBUG] Using Node runtime: \${NODE_BIN}" >&2
fi

exec "\${NODE_BIN}" "\${CLI_PATH}" "\$@"
EOF

    chmod +x "$wrapper_path"
}

create_goose_cli_wrapper() {
    local wrapper_path="$1"
    local cli_path="$2"
    local display_name="$3"
    local debug_env_var="${4:-}"

    cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

DEBUG_FLAG="\${AI_TOOL_DEBUG:-0}"
DEBUG_ENV_VAR="${debug_env_var}"

if [ -n "\${DEBUG_ENV_VAR}" ]; then
    DEBUG_ENV_VALUE="\${!DEBUG_ENV_VAR:-}"
    if [ -n "\${DEBUG_ENV_VALUE}" ]; then
        DEBUG_FLAG="\${DEBUG_ENV_VALUE}"
    fi
fi

if [ "\${DEBUG_FLAG}" = "1" ]; then
    echo "[DEBUG] Wrapper starting for $display_name" >&2
    echo "[DEBUG] CLI path: $cli_path" >&2
fi

if [ ! -x "$cli_path" ]; then
    echo "[$display_name] CLI binary missing: $cli_path" >&2
    echo "Re-run the deployment to reinstall Goose." >&2
    exit 127
fi

exec "$cli_path" "\$@"
EOF

    chmod +x "$wrapper_path"
}

create_goose_install_stub() {
    local wrapper_path="$1"
    local display_name="$2"
    local manual_url="$3"

    if [ -z "$manual_url" ]; then
        manual_url="https://block.github.io/goose/docs/getting-started/installation/"
    fi

    cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

echo "[$display_name] Goose CLI is not currently installed." >&2
echo "Refer to the official installation guide:" >&2
echo "  $manual_url" >&2
exit 127
EOF

    chmod +x "$wrapper_path"
}

fetch_latest_goose_release() {
    local api_url="https://api.github.com/repos/block/goose/releases/latest"
    local release_json

    release_json=$(curl_safe -fsSL "$api_url" 2>/dev/null) || return 1

    if [ -z "$release_json" ] || [ "$release_json" = "null" ]; then
        return 1
    fi

    printf '%s' "$release_json"
}

install_goose_cli_from_release() {
    local release_json="$1"
    local wrapper_path="$2"
    local display="$3"
    local debug_env="$4"

    local arch asset_name cli_url release_tag version
    arch=$(uname -m)

    case "$arch" in
        x86_64|amd64)
            asset_name="goose-x86_64-unknown-linux-gnu.tar.bz2"
            ;;
        aarch64|arm64)
            asset_name="goose-aarch64-unknown-linux-gnu.tar.bz2"
            ;;
        *)
            print_warning "$display is not published for architecture $arch"
            return 1
            ;;
    esac

    release_tag=$(printf '%s' "$release_json" | jq -r '.tag_name // empty' 2>/dev/null)
    if [ -z "$release_tag" ] || [ "$release_tag" = "null" ]; then
        print_warning "Unable to determine latest Goose release tag"
        return 1
    fi

    version="${release_tag#v}"

    cli_url=$(printf '%s' "$release_json" | jq -r --arg name "$asset_name" '.assets[] | select(.name == $name) | .browser_download_url' 2>/dev/null | head -n1)
    if [ -z "$cli_url" ] || [ "$cli_url" = "null" ]; then
        print_warning "Unable to locate $display download for $arch"
        return 1
    fi

    local user_home install_root cli_path version_file
    user_home="${PRIMARY_HOME:-$HOME}"
    install_root="$user_home/.local/share/goose-cli"
    cli_path="$install_root/goose"
    version_file="$install_root/.release_tag"

    local current_tag
    current_tag=$(run_as_primary_user bash -lc "cat '$version_file'" 2>/dev/null || true)

    if run_as_primary_user test -x "$cli_path" && [ "$current_tag" = "$release_tag" ]; then
        print_success "$display already up-to-date ($release_tag)"
        create_goose_cli_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
        run_as_primary_user install -d -m 755 "$user_home/.local/bin" >/dev/null 2>&1 || true
        run_as_primary_user ln -sf "$cli_path" "$user_home/.local/bin/goose" >/dev/null 2>&1 || true
        # shellcheck disable=SC2034
        GOOSE_CLI_BIN_PATH="$cli_path"
        return 0
    fi

    print_info "Downloading Goose CLI $release_tag for $arch"

    local tmp_dir archive_path
    tmp_dir=$(mktemp -d) || {
        print_warning "Unable to allocate temporary directory for $display download"
        return 1
    }
    archive_path="$tmp_dir/$asset_name"

    if ! curl_safe -fsSL "$cli_url" -o "$archive_path"; then
        rm -rf "$tmp_dir"
        print_warning "Failed to download $display from $cli_url"
        return 1
    fi

    if ! tar -xjf "$archive_path" -C "$tmp_dir"; then
        rm -rf "$tmp_dir"
        print_warning "Failed to extract Goose CLI archive"
        return 1
    fi

    if [ ! -f "$tmp_dir/goose" ]; then
        rm -rf "$tmp_dir"
        print_warning "Goose CLI archive did not contain expected binary"
        return 1
    fi

    run_as_primary_user install -d -m 755 "$install_root" >/dev/null 2>&1 || true
    if ! tar -C "$tmp_dir" -cf - goose | run_as_primary_user tar -C "$install_root" -xf - >/dev/null 2>&1; then
        rm -rf "$tmp_dir"
        print_warning "Failed to install Goose CLI binary"
        return 1
    fi

    run_as_primary_user install -d -m 755 "$user_home/.local/bin" >/dev/null 2>&1 || true
    run_as_primary_user ln -sf "$cli_path" "$user_home/.local/bin/goose" >/dev/null 2>&1 || true
    run_as_primary_user bash -c "printf '%s\n' '$release_tag' >'$version_file'" >/dev/null 2>&1 || true

    create_goose_cli_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
    rm -rf "$tmp_dir"

    print_success "$display installed ($release_tag)"
    # shellcheck disable=SC2034
    GOOSE_CLI_BIN_PATH="$cli_path"
    return 0
}

extract_deb_package_contents() {
    local deb_path="$1"
    local dest_dir="$2"

    if command -v dpkg-deb >/dev/null 2>&1; then
        dpkg-deb -x "$deb_path" "$dest_dir" >/dev/null 2>&1
        return $?
    fi

    if ! command -v ar >/dev/null 2>&1; then
        print_warning "Unable to extract $deb_path: missing dpkg-deb and ar utilities"
        return 1
    fi

    if ! mkdir -p "$dest_dir"; then
        print_warning "Unable to create extraction directory: $dest_dir"
        return 1
    fi

    local data_member
    data_member=$(ar t "$deb_path" 2>/dev/null | awk '/^data\.tar/ {print; exit}')
    if [ -z "$data_member" ]; then
        print_warning "Data archive not found inside $deb_path"
        return 1
    fi

    if ! ar p "$deb_path" "$data_member" | tar -C "$dest_dir" -xf -; then
        print_warning "Failed to unpack $deb_path using ar/tar fallback"
        return 1
    fi

    return 0
}

install_goose_desktop_from_release() {
    local release_json="$1"
    local release_tag="$2"

    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64|amd64)
            ;;
        *)
            print_warning "Goose Desktop packages are currently published for x86_64 only (detected $arch)"
            return 1
            ;;
    esac

    local desktop_url desktop_name
    desktop_url=$(printf '%s' "$release_json" | jq -r '.assets[] | select(.name | test("goose_.*_amd64\\.deb$")) | .browser_download_url' 2>/dev/null | head -n1)
    desktop_name=$(printf '%s' "$release_json" | jq -r '.assets[] | select(.name | test("goose_.*_amd64\\.deb$")) | .name' 2>/dev/null | head -n1)

    if [ -z "$desktop_url" ] || [ "$desktop_url" = "null" ]; then
        print_warning "Unable to locate Goose Desktop Debian package in latest release"
        return 1
    fi

    local user_home app_dir version_file
    user_home="${PRIMARY_HOME:-$HOME}"
    app_dir="$user_home/.local/share/goose-desktop"
    version_file="$app_dir/.release_tag"

    local current_tag
    current_tag=$(run_as_primary_user bash -lc "cat '$version_file'" 2>/dev/null || true)
    if [ -d "$app_dir" ] && [ "$current_tag" = "$release_tag" ]; then
        ensure_goose_desktop_shortcuts "$app_dir"
        print_success "Goose Desktop already up-to-date ($release_tag)"
        return 0
    fi

    print_info "Downloading Goose Desktop $release_tag (Debian package)"

    local tmp_dir deb_path extract_dir
    tmp_dir=$(mktemp -d) || {
        print_warning "Unable to allocate temporary directory for Goose Desktop"
        return 1
    }

    deb_path="$tmp_dir/${desktop_name:-goose-desktop.deb}"
    extract_dir="$tmp_dir/extracted"

    if ! curl_safe -fsSL "$desktop_url" -o "$deb_path"; then
        rm -rf "$tmp_dir"
        print_warning "Failed to download Goose Desktop from $desktop_url"
        return 1
    fi

    if ! extract_deb_package_contents "$deb_path" "$extract_dir"; then
        rm -rf "$tmp_dir"
        print_warning "Failed to extract Goose Desktop package"
        return 1
    fi

    local source_dir="$extract_dir/usr/lib/goose"
    if [ ! -d "$source_dir" ]; then
        rm -rf "$tmp_dir"
        print_warning "Goose Desktop package did not contain expected files"
        return 1
    fi

    run_as_primary_user rm -rf "$app_dir" >/dev/null 2>&1 || true
    run_as_primary_user install -d -m 755 "$app_dir" >/dev/null 2>&1 || true
    if ! tar -C "$source_dir" -cf - . | run_as_primary_user tar -C "$app_dir" -xf - >/dev/null 2>&1; then
        rm -rf "$tmp_dir"
        print_warning "Failed to install Goose Desktop resources"
        return 1
    fi

    ensure_goose_desktop_shortcuts "$app_dir" "$extract_dir/usr"

    run_as_primary_user bash -c "printf '%s\n' '$release_tag' >'$version_file'" >/dev/null 2>&1 || true

    rm -rf "$tmp_dir"
    print_success "Goose Desktop installed ($release_tag)"
    return 0
}

ensure_goose_desktop_shortcuts() {
    local app_dir="$1"
    local package_root="${2:-}"
    local user_home="${PRIMARY_HOME:-$HOME}"
    local bin_dir="$user_home/.local/bin"
    local wrapper_path="$bin_dir/goose-desktop"
    local icon_dest="$user_home/.local/share/icons/goose.png"
    local desktop_dir="$user_home/.local/share/applications"
    local desktop_path="$desktop_dir/goose.desktop"
    local desktop_source=""

    if [ -n "$package_root" ] && [ -f "$package_root/share/applications/goose.desktop" ]; then
        desktop_source="$package_root/share/applications/goose.desktop"
    elif [ -f "$app_dir/goose.desktop" ]; then
        desktop_source="$app_dir/goose.desktop"
    fi

    run_as_primary_user install -d -m 755 "$bin_dir" "$desktop_dir" "$user_home/.local/share/icons" >/dev/null 2>&1 || true

    run_as_primary_user bash -c "cat >'$wrapper_path' <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec '$app_dir/Goose' "\$@"
EOF" >/dev/null 2>&1
    run_as_primary_user chmod +x "$wrapper_path" >/dev/null 2>&1 || true

    if [ -n "$package_root" ] && [ -f "$package_root/share/pixmaps/goose.png" ]; then
        tar -C "$package_root/share/pixmaps" -cf - goose.png | run_as_primary_user tar -C "$user_home/.local/share/icons" -xf - >/dev/null 2>&1 || true
    elif [ -f "$app_dir/resources/app.asar.unpacked/static/icon.png" ]; then
        tar -C "$app_dir/resources/app.asar.unpacked/static" -cf - icon.png | run_as_primary_user tar -C "$user_home/.local/share/icons" -xf - >/dev/null 2>&1 || true
    fi

    if [ ! -f "$icon_dest" ] && [ -f "$app_dir/resources/app/static/icon.png" ]; then
        icon_dest="$app_dir/resources/app/static/icon.png"
    fi

    if [ -f "$desktop_source" ]; then
        run_as_primary_user python - "$desktop_source" "$desktop_path" "$wrapper_path" "$icon_dest" <<'PY'
import sys
src, dest, exec_path, icon_path = sys.argv[1:5]

lines = []
exec_written = False
icon_written = False

with open(src, 'r', encoding='utf-8') as handle:
    for raw in handle:
        line = raw.rstrip('\n')
        if line.startswith('Exec='):
            lines.append(f'Exec={exec_path}')
            exec_written = True
        elif line.startswith('Icon='):
            lines.append(f'Icon={icon_path}')
            icon_written = True
        else:
            lines.append(line)

if not exec_written:
    lines.append(f'Exec={exec_path}')
if not icon_written:
    lines.append(f'Icon={icon_path}')

with open(dest, 'w', encoding='utf-8') as handle:
    handle.write('\n'.join(lines) + '\n')
PY
        run_as_primary_user chmod 644 "$desktop_path" >/dev/null 2>&1 || true
    fi
}

install_goose_toolchain() {
    local wrapper_path="$1"
    local display="$2"
    local extension_id="$3"
    local debug_env="$4"

    local goose_bin=""
    goose_bin=$(PATH="$(build_primary_user_path)" command -v goose 2>/dev/null || true)
    if [[ -n "$goose_bin" && -x "$goose_bin" ]]; then
        print_success "Goose CLI provided via nixpkgs: $goose_bin"
        create_goose_cli_wrapper "$wrapper_path" "$goose_bin" "$display" "$debug_env"
        # shellcheck disable=SC2034
        GOOSE_CLI_BIN_PATH="$goose_bin"
        if [ -n "$extension_id" ]; then
            AI_VSCODE_EXTENSIONS+=("$extension_id")
        fi
        return 0
    fi

    print_info "Declarative Goose CLI not detected; falling back to upstream release"

    local release_json
    release_json=$(fetch_latest_goose_release)
    if [ -z "$release_json" ]; then
        print_warning "Unable to retrieve latest Goose release information"
        local manual_url
        manual_url=$(ai_cli_manual_url "@gooseai/cli")
        if [ -n "$manual_url" ]; then
            create_goose_install_stub "$wrapper_path" "$display" "$manual_url"
        fi
        return 1
    fi

    local release_tag
    release_tag=$(printf '%s' "$release_json" | jq -r '.tag_name // empty' 2>/dev/null)
    if [ -z "$release_tag" ] || [ "$release_tag" = "null" ]; then
        print_warning "Goose release data missing tag information"
        local manual_url
        manual_url=$(ai_cli_manual_url "@gooseai/cli")
        if [ -n "$manual_url" ]; then
            create_goose_install_stub "$wrapper_path" "$display" "$manual_url"
        fi
        return 1
    fi

    local cli_status=0
    if ! install_goose_cli_from_release "$release_json" "$wrapper_path" "$display" "$debug_env"; then
        cli_status=1
        local manual_url
        manual_url=$(ai_cli_manual_url "@gooseai/cli")
        if [ -n "$manual_url" ]; then
            create_goose_install_stub "$wrapper_path" "$display" "$manual_url"
        fi
    fi

    if ! install_goose_desktop_from_release "$release_json" "$release_tag"; then
        print_warning "Goose Desktop installation skipped (see above for details)"
    fi

    if [ $cli_status -eq 0 ] && [ -n "$extension_id" ]; then
        AI_VSCODE_EXTENSIONS+=("$extension_id")
    fi

    return $cli_status
}

install_single_ai_cli() {
    local descriptor="$1"
    local package version display bin_command wrapper_name extension_id debug_env

    IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$descriptor"

    if [ -z "$package" ] || [ -z "$version" ] || [ -z "$display" ] || [ -z "$bin_command" ] || [ -z "$wrapper_name" ]; then
        print_warning "Invalid manifest entry: $descriptor"
        return 1
    fi

    if [[ "$version" == "UNPINNED" ]]; then
        print_warning "$display is unpinned in npm manifest; skipping install for supply chain safety"
        return 1
    fi

    local default_prefix
    default_prefix="${PRIMARY_HOME:-$HOME}/.npm-global"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$default_prefix}"
    local npm_modules="$npm_prefix/lib/node_modules"
    local package_dir="$npm_modules/$package"
    local wrapper_path="$npm_prefix/bin/$wrapper_name"

    if [ "$package" = "@gooseai/cli" ]; then
        if install_goose_toolchain "$wrapper_path" "$display" "$extension_id" "$debug_env"; then
            return 0
        fi
        return 1
    fi

    local install_needed=false
    local current_version=""

    if [ -f "$package_dir/package.json" ]; then
        current_version=$(node -e "const pkg=require(process.argv[1]); if(pkg && pkg.version){console.log(pkg.version);}" "$package_dir/package.json" 2>/dev/null || echo "")
    fi

    if [ "$FORCE_UPDATE" = true ]; then
        install_needed=true
    elif [ -z "$current_version" ]; then
        install_needed=true
    elif [ "$current_version" != "$version" ]; then
        print_info "$display update available: $current_version → $version"
        install_needed=true
    fi

    if [ "$install_needed" = true ]; then
        local package_spec="${package}@${version}"
        local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
        local log_file="${tmp_root}/${wrapper_name}-npm-install.log"
        local audit_log="${tmp_root}/${wrapper_name}-npm-audit.log"
        local attempt=1
        local max_attempts=$RETRY_MAX_ATTEMPTS
        local timeout=2
        local install_exit=0
        local not_found=0
        print_info "Installing $display via npm..."

        while (( attempt <= max_attempts )); do
            if run_as_primary_user env NPM_CONFIG_PREFIX="$npm_prefix" npm install -g --ignore-scripts "$package_spec" \
                > >(tee "$log_file") 2>&1; then
                install_exit=0
            else
                install_exit=$?
            fi

            if (( install_exit == 0 )); then
                print_success "$display npm package installed"
                break
            fi

            if grep -qiE 'E404|Not Found' "$log_file" 2>/dev/null; then
                not_found=1
                break
            fi

            if (( attempt < max_attempts )); then
                print_warning "$display install attempt $attempt/$max_attempts failed; retrying in ${timeout}s"
                sleep "$timeout"
                timeout=$(( timeout * RETRY_BACKOFF_MULTIPLIER ))
            fi

            attempt=$(( attempt + 1 ))
        done

        if (( install_exit != 0 )); then
            local manual_url
            manual_url=$(ai_cli_manual_url "$package")

            if (( not_found == 1 )); then
                print_warning "$display is not available from the npm registry (HTTP 404) – skipping"
                print_detail "Package $package was not found upstream"
            else
                print_warning "$display installation failed after $max_attempts attempts (exit code $install_exit)"
            fi
            print_detail "See $log_file for details"
            print_detail "Manual install: npm install -g $package_spec"
            if [[ -n "$manual_url" ]]; then
                print_detail "Reference: $manual_url"
            fi
            if [[ "$package" == "@google/gemini-cli" ]]; then
                if grep -qiE "ripgrep|rg" "$log_file" 2>/dev/null; then
                    print_detail "Gemini CLI may fail if ripgrep download blocks; install ripgrep manually or set RIPGREP_BINARY, then retry."
                fi
            fi
            if (( not_found == 1 )); then
                {
                    echo "#!/usr/bin/env bash"
                    echo "echo \"[$display] npm package $package is not currently available.\" >&2"
                    echo "echo \"Install it manually once published: npm install -g $package_spec\" >&2"
                    if [[ -n "$manual_url" ]]; then
                        echo "echo \"See $manual_url for the latest guidance.\" >&2"
                    fi
                    echo "exit 127"
                } >"$wrapper_path"
                chmod +x "$wrapper_path"
                return 0
            fi
            return 1
        fi

        run_npm_audit_global "$display" "$audit_log" "$npm_prefix" >/dev/null || true
    else
        print_success "$display already up-to-date (v${current_version:-unknown})"
    fi

    local cli_path
    cli_path=$(resolve_ai_cli_path "$package_dir" "$bin_command") || {
        print_warning "Unable to locate CLI entry for $display"
        print_detail "Check package.json in $package_dir"
        return 1
    }

    if [ ! -f "$cli_path" ]; then
        print_warning "Resolved CLI path missing for $display: $cli_path"
        return 1
    fi

    create_ai_cli_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
    print_success "Created wrapper: $wrapper_path"

    if [ -n "$extension_id" ]; then
        AI_VSCODE_EXTENSIONS+=("$extension_id")
    fi

    return 0
}

# ============================================================================
# Install Claude Code via Native Installer
# ============================================================================
# Anthropic deprecated the npm method (@anthropic-ai/claude-code) in favor
# of a native installer that does not depend on npm or Node.js.
#
# The native installer:
#   - Downloads the correct binary for the current OS/arch
#   - Installs to ~/.local/bin/claude (symlink)
#   - Supports auto-updates (unlike the npm method)
#   - Uses the Bun runtime internally (faster startup)
#
# Reference: https://code.claude.com/docs/en/troubleshooting
# ============================================================================
install_claude_code_native() {
    local claude_bin="${PRIMARY_HOME:-$HOME}/.local/bin/claude"
    local claude_alt="${PRIMARY_HOME:-$HOME}/.claude/bin/claude"

    # Check if already installed and up-to-date
    if [ -x "$claude_bin" ] && [ "$FORCE_UPDATE" != true ]; then
        local current_version
        current_version=$("$claude_bin" --version 2>/dev/null || echo "unknown")
        print_success "Claude Code already installed (${current_version})"
        return 0
    fi

    # Clean up stale npm installation if present
    local npm_prefix="${NPM_CONFIG_PREFIX:-${PRIMARY_HOME:-$HOME}/.npm-global}"
    local old_npm_dir="$npm_prefix/lib/node_modules/@anthropic-ai/claude-code"
    if [ -d "$old_npm_dir" ]; then
        print_info "Removing deprecated npm Claude Code installation..."
        rm -rf "$old_npm_dir" 2>/dev/null || true
        # Remove old npm wrapper (will be replaced with symlink below)
        rm -f "$npm_prefix/bin/claude-wrapper" 2>/dev/null || true
        rm -f "$npm_prefix/bin/claude" 2>/dev/null || true
    fi

    # Ensure ~/.local/bin exists
    run_as_primary_user install -d -m 755 "${PRIMARY_HOME:-$HOME}/.local/bin" >/dev/null 2>&1 || \
        install -d -m 755 "${PRIMARY_HOME:-$HOME}/.local/bin" >/dev/null 2>&1 || true

    # Install via native installer with retry logic
    local attempt=1
    local max_attempts=${RETRY_MAX_ATTEMPTS:-4}
    local timeout=2
    local install_exit=0
    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    local log_file="${tmp_root}/claude-native-install.log"

    print_info "Installing Claude Code via native installer..."

    while (( attempt <= max_attempts )); do
        local installer_tmp
        installer_tmp="$(mktemp -p "$tmp_root" claude-install.XXXXXX.sh)"
        local installer_hash=""
        local expected_hash="${CLAUDE_INSTALLER_SHA256:-}"

        if command -v curl_safe >/dev/null 2>&1; then
            if ! curl_safe -fsSL "https://claude.ai/install.sh" -o "$installer_tmp"; then
                print_warning "Failed to download Claude installer"
                rm -f "$installer_tmp"
                install_exit=1
                break
            fi
        else
            if ! curl --max-time 120 --connect-timeout 10 -fsSL "https://claude.ai/install.sh" -o "$installer_tmp"; then
                print_warning "Failed to download Claude installer"
                rm -f "$installer_tmp"
                install_exit=1
                break
            fi
        fi

        if command -v sha256sum >/dev/null 2>&1; then
            installer_hash="$(sha256sum "$installer_tmp" | awk '{print $1}')"
        elif command -v shasum >/dev/null 2>&1; then
            installer_hash="$(shasum -a 256 "$installer_tmp" | awk '{print $1}')"
        fi

        if [[ -n "$installer_hash" ]]; then
            print_info "Claude installer SHA-256: $installer_hash"
        fi

        if [[ -n "$expected_hash" && -n "$installer_hash" && "$installer_hash" != "$expected_hash" ]]; then
            print_error "Claude installer hash mismatch (expected $expected_hash)"
            rm -f "$installer_tmp"
            install_exit=1
            break
        fi

        if [[ "${NONINTERACTIVE:-false}" == "true" && "${TRUST_REMOTE_SCRIPTS:-false}" != "true" ]]; then
            print_warning "Noninteractive mode blocks remote script execution without TRUST_REMOTE_SCRIPTS=true"
            rm -f "$installer_tmp"
            install_exit=1
            break
        fi

        if declare -F confirm >/dev/null 2>&1; then
            if ! confirm "Run Claude installer script from https://claude.ai/install.sh?" "n"; then
                print_warning "Claude installer aborted by user"
                rm -f "$installer_tmp"
                install_exit=1
                break
            fi
        fi

        # Download installer to temp file first to verify integrity before execution
        local installer_url="https://claude.ai/install.sh"
        local download_tmp="${TMPDIR:-/tmp}/claude-installer-$$.sh"
        
        # Download with timeout and verify download succeeded
        if ! curl --max-time 30 --connect-timeout 10 -fsSL "$installer_url" -o "$download_tmp"; then
            print_error "Failed to download Claude installer from $installer_url"
            install_exit=1
            rm -f "$download_tmp" 2>/dev/null || true
            break
        fi
        
        # Verify the downloaded file has content before executing
        if [[ ! -s "$download_tmp" ]]; then
            print_error "Downloaded installer is empty"
            install_exit=1
            rm -f "$download_tmp" 2>/dev/null || true
            break
        fi
        
        # Execute the downloaded script and capture exit code
        if run_as_primary_user bash "$download_tmp" > >(tee "$log_file") 2>&1; then
            install_exit=0
        else
            install_exit=$?
        fi
        
        # Clean up temp files
        rm -f "$download_tmp" 2>/dev/null || true

        if (( install_exit == 0 )); then
            break
        fi

        if (( attempt < max_attempts )); then
            print_warning "Claude Code install attempt $attempt/$max_attempts failed; retrying in ${timeout}s"
            sleep "$timeout"
            timeout=$(( timeout * ${RETRY_BACKOFF_MULTIPLIER:-2} ))
        fi

        attempt=$(( attempt + 1 ))
    done

    if (( install_exit != 0 )); then
        print_warning "Claude Code native installation failed after $max_attempts attempts (exit code $install_exit)"
        print_detail "See $log_file for details"
        print_detail "Manual install: curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash"
        return 1
    fi

    # Verify installation — check primary path then fallback
    local actual_bin=""
    if [ -x "$claude_bin" ]; then
        actual_bin="$claude_bin"
    elif [ -x "$claude_alt" ]; then
        actual_bin="$claude_alt"
        # Create symlink at expected path
        ln -sf "$claude_alt" "$claude_bin" 2>/dev/null || true
    fi

    if [ -z "$actual_bin" ]; then
        print_warning "Claude Code installer completed but binary not found at expected paths"
        print_detail "Checked: $claude_bin, $claude_alt"
        print_detail "Try: which claude"
        return 1
    fi

    local installed_version
    installed_version=$("$actual_bin" --version 2>/dev/null || echo "unknown")
    print_success "Claude Code installed (${installed_version}) at $actual_bin"

    # Create backward-compatible claude-wrapper symlink for existing VSCodium configs
    if [ -d "$npm_prefix/bin" ]; then
        ln -sf "$actual_bin" "$npm_prefix/bin/claude-wrapper" 2>/dev/null || true
        print_detail "Created compatibility symlink: $npm_prefix/bin/claude-wrapper → $actual_bin"
    fi

    return 0
}

install_claude_code() {
    print_section "Installing AI Coding CLIs"

    AI_VSCODE_EXTENSIONS=()

    # -----------------------------------------------------------------------
    # Step 1: Install Claude Code via native installer (no npm/Node required)
    # -----------------------------------------------------------------------
    if ! install_claude_code_native; then
        print_warning "Claude Code native installation had issues"
    fi
    # Always register the VSCodium extension for installation
    AI_VSCODE_EXTENSIONS+=("Anthropic.claude-code")

    # -----------------------------------------------------------------------
    # Step 2: Install remaining AI CLIs via npm (OpenAI, CodeX, Goose, etc.)
    # -----------------------------------------------------------------------
    if ! validate_command_available "npm" 2>/dev/null; then
        if ! command -v npm >/dev/null 2>&1; then
            print_warning "npm not available – skipping npm-based AI CLI installation"
            return 0
        fi
    fi

    if ! validate_command_available "node" 2>/dev/null; then
        if ! command -v node >/dev/null 2>&1; then
            print_warning "Node.js not available – skipping npm-based AI CLI installation"
            return 0
        fi
    fi

    ensure_npm_global_prefix

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ ! -f "$manifest" ]; then
        print_warning "AI CLI manifest not found at $manifest"
        return 0
    fi

    load_npm_manifest "$manifest"

    if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -eq 0 ]; then
        print_info "No additional npm AI CLI packages defined in manifest"
        return 0
    fi

    local overall_status=0
    local entry
    for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
        if ! install_single_ai_cli "$entry"; then
            overall_status=1
        fi
    done

    return $overall_status
}

# ============================================================================
# Configure VSCodium for Claude and other AI CLIs
# ============================================================================
# Purpose: Ensure VSCodium extensions know where wrappers live
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
configure_vscodium_for_claude() {
    print_section "Configuring VSCodium for AI assistants"

    detect_flatpak_vscodium_conflicts() {
        if ! flatpak_cli_available; then
            return 0
        fi

        local -a conflict_ids=()
        if declare -p FLATPAK_VSCODIUM_CONFLICT_IDS >/dev/null 2>&1; then
            conflict_ids=("${FLATPAK_VSCODIUM_CONFLICT_IDS[@]}")
        else
            conflict_ids=(
                "com.visualstudio.code"
                "com.visualstudio.code.insiders"
                "com.vscodium.codium"
                "com.vscodium.codium.insiders"
            )
        fi

        purge_vscodium_flatpak_conflicts || true

        local -a installed=()
        local app_id
        for app_id in "${conflict_ids[@]}"; do
            if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
                installed+=("$app_id (user)")
            fi

            if run_as_primary_user flatpak info --system "$app_id" >/dev/null 2>&1; then
                installed+=("$app_id (system)")
            fi
        done

        if [[ ${#installed[@]} -gt 0 ]]; then
            local joined
            joined=$(printf '%s, ' "${installed[@]}")
            joined=${joined%, }
            print_error "Detected Flatpak Visual Studio Code variants that override declarative VSCodium: ${joined}"
            print_info "Remove them with 'flatpak uninstall --user <app-id>' (or omit --user for system installs)."
            print_info "Keeping only the declarative programs.vscode package prevents settings and wrappers from being replaced."
            return 1
        fi

        return 0
    }

    if ! detect_flatpak_vscodium_conflicts; then
        return 1
    fi

    if ! command -v codium >/dev/null 2>&1; then
        print_info "VSCodium not found in PATH"
        print_info "Configuration will be applied after VSCodium is installed"
        return 0
    fi

    if ! command -v jq >/dev/null 2>&1; then
        print_warning "jq unavailable – skipping automatic VSCodium settings merge"
        return 0
    fi

    local settings_dir="$HOME/.config/VSCodium/User"
    local settings_file="$settings_dir/settings.json"
    mkdir -p "$settings_dir"

    if [ ! -e "$settings_file" ]; then
        echo "{}" >"$settings_file"
    fi

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ ! -f "$manifest" ]; then
        print_warning "AI CLI manifest not found, skipping VSCodium settings update"
        return 0
    fi

    load_npm_manifest "$manifest"

    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local wrapper_dir="$npm_prefix/bin"
    local npm_modules="$npm_prefix/lib/node_modules"

    verify_declarative_vscodium_settings() {
        if [ ! -f "$settings_file" ]; then
            print_warning "Declarative VSCodium settings not found – rerun home-manager to generate settings.json"
            return
        fi

        declare -A missing_keys=()

        __vscodium_check_flat_key() {
            local candidate="$1"
            if [ -z "$candidate" ]; then
                return
            fi
            if ! jq -e --arg key "$candidate" 'has($key) and .[$key] != null' "$settings_file" >/dev/null 2>&1; then
                missing_keys["$candidate"]=1
            fi
        }

        local entry package version display bin_command wrapper_name extension_id debug_env
        for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
            IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
            local keys=()
            local extra=()
            case "$package" in
                "@anthropic-ai/claude-code")
                    keys=("claude-code" "claudeCode")
                    extra=("claude-code.claudeProcessWrapper" "claudeCode.claudeProcessWrapper")
                    ;;
                "@openai/codex")
                    if [[ "$wrapper_name" == "gpt-codex-wrapper" ]]; then
                        keys=("gpt-codex" "gptCodex")
                    else
                        keys=("codex" "codexIDE" "codexIde")
                    fi
                    ;;
                "openai")
                    keys=("openai")
                    ;;
                "@gooseai/cli")
                    keys=("gooseai")
                    ;;
                *)
                    keys=()
                    ;;
            esac

            local key
            for key in "${keys[@]}"; do
                __vscodium_check_flat_key "${key}.executablePath"
                __vscodium_check_flat_key "${key}.environmentVariables"
                __vscodium_check_flat_key "${key}.autoStart"
            done

            local extra_key
            for extra_key in "${extra[@]}"; do
                __vscodium_check_flat_key "$extra_key"
            done
        done

        if [ "${#missing_keys[@]}" -eq 0 ]; then
            print_success "Declarative VSCodium settings already contain AI wrapper configuration"
            return
        fi

        local missing_list=("${!missing_keys[@]}")
        local joined_missing
        joined_missing=$(printf '%s, ' "${missing_list[@]}")
        joined_missing=${joined_missing%, }

        print_warning "Declarative VSCodium settings missing keys: ${joined_missing}"
        print_info "Add them to templates/home.nix → programs.vscode.profiles.default.userSettings to keep settings.json writable by Nix"
    }

    local resolved_settings
    resolved_settings=$(readlink -f "$settings_file" 2>/dev/null || true)

    local conversion_result=""
    if [ -L "$settings_file" ] && [[ "$resolved_settings" == /nix/store/* ]]; then
        if [ -f "$resolved_settings" ]; then
            local tmp_settings="${settings_file}.tmp"
            if cp "$resolved_settings" "$tmp_settings" 2>/dev/null; then
                if rm -f "$settings_file" 2>/dev/null && mv "$tmp_settings" "$settings_file" 2>/dev/null; then
                    chmod u+rw "$settings_file" 2>/dev/null || true
                    conversion_result="copied"
                    print_warning "Converted declarative VSCodium settings to a mutable copy (source: $resolved_settings)"
                    print_info "Future home-manager runs may reapply declarative settings; rerun deploy script afterwards if needed."
                else
                    rm -f "$tmp_settings" 2>/dev/null || true
                fi
            else
                rm -f "$tmp_settings" 2>/dev/null || true
            fi
        fi

        if [ "$conversion_result" != "copied" ]; then
            print_info "VSCodium settings.json is managed declaratively (read-only symlink detected)"
            verify_declarative_vscodium_settings
            return 0
        fi
    elif [ -e "$settings_file" ]; then
        local settings_writable=1
        local stat_mode owner_uid owner_gid
        if read -r stat_mode owner_uid owner_gid < <(stat -c '%a %u %g' "$settings_file" 2>/dev/null); then
            local target_user="${PRIMARY_USER:-${SUDO_USER:-${USER:-}}}"
            if [ -z "$target_user" ]; then
                target_user="root"
            fi
            local target_uid=""
            local target_gid=""
            local target_groups=""
            if command -v id >/dev/null 2>&1; then
                target_uid=$(id -u "$target_user" 2>/dev/null || echo '')
                target_gid=$(id -g "$target_user" 2>/dev/null || echo '')
                target_groups=$(id -G "$target_user" 2>/dev/null || echo '')
            fi
            if [ -z "$target_uid" ]; then
                if [ -n "${PRIMARY_UID:-}" ]; then
                    target_uid="$PRIMARY_UID"
                else
                    target_uid="$EUID"
                fi
            fi
            if [ -z "$target_gid" ]; then
                if [ -n "${PRIMARY_GID:-}" ]; then
                    target_gid="$PRIMARY_GID"
                elif command -v id >/dev/null 2>&1; then
                    target_gid=$(id -g 2>/dev/null || echo '')
                fi
            fi

            local mode_value=$((10#$stat_mode))
            local owner_bits=$(( mode_value / 100 ))
            local group_bits=$(( (mode_value / 10) % 10 ))
            local other_bits=$(( mode_value % 10 ))

            settings_writable=0

            if [ -n "$target_uid" ] && [ "$target_uid" = "$owner_uid" ]; then
                if (( owner_bits & 2 )); then
                    settings_writable=1
                fi
            elif [ -n "$target_groups" ] && [ -n "$owner_gid" ]; then
                local gid
                for gid in $target_groups; do
                    if [ "$gid" = "$owner_gid" ] && (( group_bits & 2 )); then
                        settings_writable=1
                        break
                    fi
                done
            fi

            if [ "$settings_writable" -eq 0 ] && (( other_bits & 2 )); then
                settings_writable=1
            fi
        elif [ ! -w "$settings_file" ]; then
            settings_writable=0
        fi

        if [ "$settings_writable" -eq 0 ]; then
            if chmod u+rw "$settings_file" 2>/dev/null && [ -w "$settings_file" ]; then
                conversion_result="chmod"
                print_warning "Adjusted VSCodium settings.json permissions to restore writability"
                print_info "Future declarative runs may reset permissions; rerun deploy script afterwards if needed."
            else
                print_info "VSCodium settings.json is managed declaratively (read-only file detected)"
                verify_declarative_vscodium_settings
                return 0
            fi
        fi
    fi

    if [ "$conversion_result" = "copied" ]; then
        print_success "VSCodium settings.json converted to writable file"
    elif [ "$conversion_result" = "chmod" ]; then
        print_success "VSCodium settings.json permissions updated to allow edits"
    fi

    local path_entries=("$wrapper_dir" "$HOME/.nix-profile/bin")
    if command -v node >/dev/null 2>&1; then
        local node_bin
        node_bin=$(command -v node)
        if [ -n "$node_bin" ]; then
            local node_dir
            node_dir=$(dirname "$node_bin")
            if [ -n "$node_dir" ]; then
                path_entries+=("$node_dir")
            fi
        fi
    fi
    path_entries+=("/run/current-system/sw/bin")

    local path_value
    local IFS=:
    path_value="${path_entries[*]}"
    IFS=$' \t\n'
    path_value="$path_value:\${env:PATH}"

    local env_json
    env_json=$(jq -n \
        --arg path "$path_value" \
        --arg nodePath "$npm_modules" \
        '[
            {"name": "PATH", "value": $path},
            {"name": "NODE_PATH", "value": $nodePath}
        ]'
    )

    apply_jq() {
        local filter="$1"
        shift
        local temp
        temp=$(mktemp)
        if jq "$@" "$filter" "$settings_file" >"$temp"; then
            mv "$temp" "$settings_file"
            return 0
        fi
        rm -f "$temp"
        return 1
    }

    local entry package version display bin_command wrapper_name extension_id debug_env
    local overall_status=0
    for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
        IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
        local wrapper_path="$wrapper_dir/$wrapper_name"
        local keys=()
        local extra=()
        case "$package" in
            "@anthropic-ai/claude-code")
                keys=("claude-code" "claudeCode")
                extra=("claude-code.claudeProcessWrapper" "claudeCode.claudeProcessWrapper")
                ;;
            "@openai/codex")
                if [[ "$wrapper_name" == "gpt-codex-wrapper" ]]; then
                    keys=("gpt-codex" "gptCodex")
                else
                    keys=("codex" "codexIDE" "codexIde")
                fi
                ;;
            "openai")
                keys=("openai")
                ;;
            "@gooseai/cli")
                keys=("gooseai")
                ;;
            *)
                keys=()
                ;;
        esac

        local key
        for key in "${keys[@]}"; do
            local exec_key="${key}.executablePath"
            local env_key="${key}.environmentVariables"
            local auto_key="${key}.autoStart"
            if ! apply_jq '. + { ($exec_key): $wrapper, ($env_key): $env, ($auto_key): false }' \
                --arg exec_key "$exec_key" \
                --arg env_key "$env_key" \
                --arg auto_key "$auto_key" \
                --arg wrapper "$wrapper_path" \
                --argjson env "$env_json"; then
                overall_status=1
            fi
        done

        local extra_key
        for extra_key in "${extra[@]}"; do
            if [ -z "$extra_key" ]; then
                continue
            fi
            if ! apply_jq '. + { ($flat_key): $wrapper }' \
                --arg flat_key "$extra_key" \
                --arg wrapper "$wrapper_path"; then
                overall_status=1
            fi
        done
    done

    if [ "$overall_status" -eq 0 ]; then
        print_success "Updated VSCodium settings for AI wrappers"
    else
        print_warning "Encountered issues while updating VSCodium AI settings"
    fi
    return 0
}

# ============================================================================
# Install VSCodium Extensions
# ============================================================================
# Purpose: Install useful VSCodium extensions for development
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_vscodium_extensions() {
    print_section "Installing VSCodium extensions"

    if ! command -v codium >/dev/null 2>&1; then
        print_info "VSCodium not found, skipping extension installation"
        return 0
    fi

    load_vscodium_extension_cache || true

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ -f "$manifest" ]; then
        load_npm_manifest "$manifest"
    else
        NPM_AI_PACKAGE_MANIFEST=()
    fi

    local extensions=(
        "Anthropic.claude-code|Claude Code"
        "jnoortheen.nix-ide|Nix IDE"
        "eamodio.gitlens|GitLens"
        "editorconfig.editorconfig|EditorConfig"
        "esbenp.prettier-vscode|Prettier"
        "ms-python.python|Python"
        "ms-python.black-formatter|Black Formatter"
        "ms-python.vscode-pylance|Pylance"
        "ms-toolsai.jupyter|Jupyter"
        "ms-toolsai.jupyter-keymap|Jupyter Keymap"
        "ms-toolsai.jupyter-renderers|Jupyter Renderers"
        "continue.continue|Continue"
        "codeium.codeium|Codeium"
        "Kombai.kombai|Kombai"
        "ms-azuretools.vscode-docker|Docker"
        "rust-lang.rust-analyzer|Rust Analyzer"
        "dbaeumer.vscode-eslint|ESLint"
        "golang.go|Go"
        "usernamehw.errorlens|Error Lens"
        "tamasfe.even-better-toml|Even Better TOML"
        "redhat.vscode-yaml|YAML"
        "mechatroner.rainbow-csv|Rainbow CSV"
        "mhutchie.git-graph|Git Graph"
    )

    if [ -n "${AI_VSCODE_EXTENSIONS[*]:-}" ]; then
        local ext
        for ext in "${AI_VSCODE_EXTENSIONS[@]}"; do
            extensions+=("$ext|AI Tool")
        done
    else
        local entry package version display bin_command wrapper_name extension_id debug_env
        for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
            IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
            if [ -n "$extension_id" ]; then
                extensions+=("$extension_id|$display")
            fi
        done
    fi

    install_ext() {
        local ext_id="$1"
        local name="$2"
        local attempt

        print_info "Installing: $name ($ext_id)"
        for attempt in 1 2 3; do
            if codium --install-extension "$ext_id" >/dev/null 2>&1; then
                print_success "$name extension installed"
                mark_vscodium_extension_installed "$ext_id"
                return 0
            fi
            sleep 2
        done

        print_warning "$name extension could not be installed automatically"
        print_detail "Install manually: codium --install-extension $ext_id"
        return 1
    }

    declare -A seen=()
    local descriptor ext_id name
    for descriptor in "${extensions[@]}"; do
        IFS='|' read -r ext_id name <<<"$descriptor"
        if [ -z "$ext_id" ]; then
            continue
        fi
        if [ -n "${seen["$ext_id"]:-}" ]; then
            continue
        fi
        seen["$ext_id"]=1
        if vscodium_extension_installed "$ext_id"; then
            print_info "$name extension already installed; skipping"
            continue
        fi
        if ! open_vsx_extension_available "$ext_id"; then
            local status="${LAST_OPEN_VSX_STATUS:-unknown}"
            print_warning "$name extension not available on Open VSX (HTTP $status)"
            if [ -n "$LAST_OPEN_VSX_URL" ]; then
                print_detail "Checked: $LAST_OPEN_VSX_URL"
            fi
            if install_extension_from_marketplace "$ext_id" "$name"; then
                continue
            fi
            local manual_url
            manual_url=$(vscode_extension_manual_url "$ext_id")
            if [ -n "$manual_url" ]; then
                print_detail "Manual download: $manual_url"
            fi
            continue
        fi
        install_ext "$ext_id" "$name"
    done

    return 0
}

# ============================================================================
# Install OpenSkills Tooling
# ============================================================================
# Purpose: Install project-specific OpenSkills development tools
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_openskills_tooling() {
    print_section "Installing OpenSkills Tooling"

    if [[ "${DRY_RUN:-false}" == true ]]; then
        print_info "Dry-run mode enabled – skipping OpenSkills installation"
        return 0
    fi

    # Validate npm is available
    if ! validate_command_available "npm"; then
        print_warning "npm not available; skipping OpenSkills installation"
        return 0
    fi
    if ! validate_command_available "node"; then
        print_warning "node not available; skipping OpenSkills installation"
        return 0
    fi

    ensure_npm_global_prefix

    local default_prefix
    default_prefix="${PRIMARY_HOME:-$HOME}/.npm-global"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$default_prefix}"
    local npm_modules="$npm_prefix/lib/node_modules"
    local package="openskills"
    local package_dir="$npm_modules/$package"

    local current_version=""
    if [ -f "$package_dir/package.json" ]; then
        current_version=$(node -e "const pkg=require(process.argv[1]); if(pkg && pkg.version){console.log(pkg.version);}" "$package_dir/package.json" 2>/dev/null || echo "")
    fi

    local desired_version="${OPEN_SKILLS_VERSION:-}"
    local latest_version=""
    if [[ -z "$desired_version" ]]; then
        latest_version=$(run_as_primary_user npm view "$package" version 2>/dev/null || echo "")
    fi

    local need_install=false
    if [[ "${FORCE_UPDATE:-false}" == true ]]; then
        need_install=true
    elif [[ -z "$current_version" ]]; then
        need_install=true
    elif [[ -n "$desired_version" && "$current_version" != "$desired_version" ]]; then
        print_info "OpenSkills update available: $current_version → $desired_version"
        need_install=true
    elif [[ -z "$desired_version" && -n "$latest_version" && "$current_version" != "$latest_version" ]]; then
        print_warning "OpenSkills version unpinned; update available: $current_version → $latest_version"
        need_install=true
    fi

    if [[ "$need_install" == true ]]; then
        print_info "Installing OpenSkills via npm..."
        local log_file="${LOG_DIR:-/tmp}/openskills-npm-install.log"
        local audit_log="${LOG_DIR:-/tmp}/openskills-npm-audit.log"
        local package_spec="$package"
        if [[ -n "$desired_version" ]]; then
            package_spec="${package}@${desired_version}"
        fi
        mkdir -p "$(dirname "$log_file")" 2>/dev/null || true
        local npm_status=0
        if run_as_primary_user env NPM_CONFIG_PREFIX="$npm_prefix" npm install -g --ignore-scripts "$package_spec" \
            > >(tee "$log_file") 2>&1; then
            npm_status=0
        else
            npm_status=$?
        fi
        if [[ $npm_status -ne 0 ]]; then
            print_error "OpenSkills npm install failed (exit code $npm_status)"
            print_detail "See $log_file for details"
            return 1
        fi
        run_npm_audit_global "OpenSkills" "$audit_log" "$npm_prefix" >/dev/null || true
        current_version=$(node -e "const pkg=require(process.argv[1]); if(pkg && pkg.version){console.log(pkg.version);}" "$package_dir/package.json" 2>/dev/null || echo "")
        print_success "OpenSkills tooling installed${current_version:+ (v$current_version)}"
    else
        print_success "OpenSkills already up-to-date (v${current_version:-unknown})"
    fi

    local hook_home="${PRIMARY_HOME:-$HOME}"
    local hook_path="$hook_home/.config/openskills/install.sh"
    if [[ -x "$hook_path" ]]; then
        print_info "Running OpenSkills custom hook: $hook_path"
        if ! HOME="$hook_home" bash "$hook_path"; then
            print_warning "OpenSkills custom hook reported errors"
        fi
    fi

    local missing_toolkits
    if ensure_python_runtime; then
        missing_toolkits=$(run_python <<'PY' 2>/dev/null
import importlib.metadata

candidates = [
    ("crewai", "CrewAI (collaborative agents)"),
    ("autogen", "Microsoft AutoGen (multi-agent automation)"),
    ("smolagents", "Hugging Face Smolagents (tool-calling agents)"),
]

lines = []
for package, label in candidates:
    try:
        importlib.metadata.distribution(package)
    except importlib.metadata.PackageNotFoundError:
        lines.append(f"{package}:{label}")

if lines:
    print("\n".join(lines))
PY
        )
    else
        missing_toolkits=""
    fi

    if [[ -n "$missing_toolkits" ]]; then
        print_info "Additional agent frameworks available for this environment:"
        while IFS=":" read -r package label; do
            [[ -z "$package" ]] && continue
            print_info "  • $label → run 'python3 -m pip install --user $package'"
        done <<<"$missing_toolkits"
    fi

    return 0
}

# ============================================================================
# Setup Flake Environment
# ============================================================================
# Purpose: Setup Nix flakes development environment
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
setup_flake_environment() {
    print_section "Setting Up Flake Development Environment"

    # Check if flakes are enabled
    if ! nix flake --help &>/dev/null; then
        print_warning "Nix flakes not available"
        print_info "Flakes should be enabled in configuration.nix"
        return 1
    fi

    print_info "Nix flakes are enabled and ready"

    # Check if direnv is available for auto-activation
    if command -v direnv &>/dev/null; then
        print_success "direnv is available for automatic environment activation"
        print_info "In project directories with flake.nix:"
        print_info "  1. Create .envrc with: use flake"
        print_info "  2. Run: direnv allow"
        print_info "  3. Environment activates automatically on cd"
    else
        print_info "Install direnv for automatic flake environment activation"
        print_info "Manual activation: nix develop"
    fi

    # Validate flake lock completeness (catch missing inputs like nix-vscode-extensions)
    if [[ -f "$HM_CONFIG_DIR/flake.nix" ]]; then
        if declare -F validate_flake_lock_inputs >/dev/null 2>&1; then
            validate_flake_lock_inputs "$HM_CONFIG_DIR" || \
                print_warning "Flake lock validation had issues (non-critical)"
        fi

        # Check if our flake configuration is valid
        print_info "Validating flake configuration..."
        local tmp_dir="${TMP_DIR:-/tmp}"
        local flake_check_log="${tmp_dir}/flake-check.log"
        if nix flake check "$HM_CONFIG_DIR" > >(tee "$flake_check_log") 2>&1; then
            print_success "Flake configuration is valid"
        else
            print_warning "Flake validation had issues (see $flake_check_log)"
            print_info "Configuration may still work, issues are often non-critical"
        fi
    fi

    print_success "Flake environment setup complete"
    return 0
}

prefetch_podman_ai_stack_images() {
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        return 0
    fi

    if ! command -v podman >/dev/null 2>&1; then
        print_warning "Podman is not available; skipping AI stack image prefetch."
        return 0
    fi

    local -a images=(
        "ghcr.io/ggml-org/llama.cpp:server"
        "ghcr.io/open-webui/open-webui:latest"
        "docker.io/qdrant/qdrant:latest"
        "docker.io/mindsdb/mindsdb:latest"
    )

    print_section "Prefetching Podman AI stack images"
    local image=""
    for image in "${images[@]}"; do
        if podman image exists "$image" >/dev/null 2>&1; then
            print_info "Image already present: $image"
            continue
        fi

        print_info "Pulling $image ..."
        if podman pull "$image"; then
            print_success "Pulled $image"
        else
            print_warning "Failed to pull $image (continuing)"
        fi
    done
    echo ""
}

download_llama_cpp_models_if_needed() {
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        return 0
    fi
    if [[ "${LLM_BACKEND:-llama_cpp}" != "llama_cpp" ]]; then
        return 0
    fi
    if [[ "${AUTO_DOWNLOAD_LLAMA_CPP_MODELS:-false}" != "true" ]]; then
        print_info "Skipping automatic llama.cpp model download (AUTO_DOWNLOAD_LLAMA_CPP_MODELS=false)."
        return 0
    fi

    local download_script="$SCRIPT_DIR/scripts/download-llama-cpp-models.sh"
    if [[ ! -x "$download_script" ]]; then
        print_warning "llama.cpp model download script missing at $download_script"
        return 0
    fi

    if [[ -z "${HUGGINGFACEHUB_API_TOKEN:-}" && -n "${HUGGINGFACE_TOKEN_PREFERENCE_FILE:-}" && -r "$HUGGINGFACE_TOKEN_PREFERENCE_FILE" ]]; then
        local hf_token
        hf_token=$(awk -F'=' '/^HUGGINGFACEHUB_API_TOKEN=/{print $2}' "$HUGGINGFACE_TOKEN_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
        if [[ -n "$hf_token" ]]; then
            export HUGGINGFACEHUB_API_TOKEN="$hf_token"
        fi
    fi

    if [[ -z "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        print_warning "Skipping automatic llama.cpp model download (Hugging Face token not configured)."
        print_warning "Set HUGGINGFACEHUB_API_TOKEN or rerun Phase 1 to cache the token."
        return 0
    fi

    local model_dir="$HOME/.local/share/podman-ai-stack/llama-cpp-models"
    local cache_dir="${HUGGINGFACE_HOME:-$HOME/.cache/huggingface}"

    print_section "Downloading llama.cpp GGUF models"
    MODEL_DIR="$model_dir" HF_HOME="$cache_dir" HUGGINGFACE_TOKEN_FILE="$HUGGINGFACE_TOKEN_PREFERENCE_FILE" \
        "$download_script" --all || print_warning "llama.cpp model download encountered issues"
    echo ""
}

flatpak_app_installed() {
    local app_id="${1:-}"
    
    # Validate input
    if ! validate_non_empty "app_id" "$app_id"; then
        return 1
    fi

    if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
        return 0
    fi

    if run_as_primary_user flatpak info --system "$app_id" >/dev/null 2>&1; then
        return 0
    fi

    return 1
}
