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

declare -a AI_VSCODE_EXTENSIONS=()

# ============================================================================
# Flatpak Helpers
# ============================================================================

flatpak_remote_exists() {
    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"

    if run_as_primary_user flatpak --user remote-list --columns=name 2>/dev/null | grep -Fxq "$remote_name"; then
        return 0
    fi

    if run_as_primary_user flatpak --system remote-list --columns=name 2>/dev/null | grep -Fxq "$remote_name"; then
        return 0
    fi

    if run_as_primary_user flatpak remote-list --columns=name 2>/dev/null | grep -Fxq "$remote_name"; then
        return 0
    fi

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

ensure_flathub_remote() {
    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; skipping Flathub repository configuration"
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

    local source output
    for source in "${sources[@]}"; do
        output=$(run_as_primary_user flatpak remote-add --user --if-not-exists --from "$remote_name" "$source" 2>&1)
        if [[ $? -eq 0 ]]; then
            if [[ "$source" == "${sources[0]}" ]]; then
                print_success "Flathub repository added"
            else
                print_success "Flathub repository added via fallback source ($source)"
            fi
            return 0
        fi

        print_flatpak_details "$output"

        output=$(run_as_primary_user flatpak remote-add --user --if-not-exists "$remote_name" "$source" 2>&1)
        if [[ $? -eq 0 ]]; then
            if [[ "$source" == "${sources[0]}" ]]; then
                print_success "Flathub repository added"
            else
                print_success "Flathub repository added via fallback source ($source)"
            fi
            return 0
        fi

        print_flatpak_details "$output"
    done

    print_warning "Unable to configure Flathub repository automatically"
    return 1
}

flatpak_query_application_support() {
    local app_id="$1"

    LAST_FLATPAK_QUERY_MESSAGE=""

    local remote_name="${FLATHUB_REMOTE_NAME:-flathub}"
    local user_output system_output user_status system_status

    user_output=$(run_as_primary_user flatpak --user remote-info "$remote_name" "$app_id" 2>&1 || true)
    user_status=$?
    if [[ $user_status -eq 0 ]]; then
        return 0
    fi

    system_output=$(run_as_primary_user flatpak remote-info "$remote_name" "$app_id" 2>&1 || true)
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

    for app_id in "$@"; do
        if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            print_info "  • $app_id already present"
            continue
        fi

        flatpak_query_application_support "$app_id"
        local support_status=$?

        if [[ $support_status -ne 0 ]]; then
            if [[ $support_status -eq 3 ]]; then
                print_warning "  ⚠ $app_id is not available on $remote_name for this architecture; skipping"
            else
                print_warning "  ⚠ Unable to query metadata for $app_id prior to installation"
            fi
            print_flatpak_details "$LAST_FLATPAK_QUERY_MESSAGE"
            [[ $support_status -eq 3 ]] && continue
            failure=1
            continue
        fi

        print_info "  Installing $app_id from $remote_name..."
        local attempt
        local installed=0
        for attempt in 1 2 3; do
            local install_output
            install_output=$(run_as_primary_user flatpak --noninteractive --assumeyes install --user "$remote_name" "$app_id" 2>&1)
            if [[ $? -eq 0 ]]; then
                print_success "  ✓ Installed $app_id"
                installed=1
                break
            fi

            if printf '%s\n' "$install_output" | grep -Eiq 'No remote refs found similar|No entry for|Nothing matches'; then
                print_warning "  ⚠ $app_id is not available on $remote_name for this architecture; skipping"
                print_flatpak_details "$install_output"
                installed=1
                break
            fi

            print_warning "  ⚠ Attempt $attempt failed for $app_id"
            print_flatpak_details "$install_output"
            sleep $(( attempt * 2 ))
        done

        if [[ $installed -ne 1 ]]; then
            print_warning "  ⚠ Failed to install $app_id after retries"
            failure=1
        fi
    done

    return $failure
}

ensure_default_flatpak_apps_installed() {
    if [[ ${#DEFAULT_FLATPAK_APPS[@]} -eq 0 ]]; then
        print_info "No default Flatpak applications defined"
        return 0
    fi

    local -a missing=()
    local app_id

    for app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
        if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            print_info "  • $app_id already present"
        else
            missing+=("$app_id")
        fi
    done

    if (( ${#missing[@]} == 0 )); then
        print_success "All default Flatpak applications are already installed"
        return 0
    fi

    if flatpak_install_app_list "${missing[@]}"; then
        print_success "Default Flatpak applications are now installed and ready"
        run_as_primary_user flatpak --user update --noninteractive --appstream >/dev/null 2>&1 || true
        run_as_primary_user flatpak --user update --noninteractive >/dev/null 2>&1 || true
        return 0
    fi

    print_warning "Some Flatpak applications could not be installed automatically"
    print_info "You can retry manually with: flatpak install --user ${FLATHUB_REMOTE_NAME:-flathub} <app-id>"
    return 1
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

    if ! command -v flatpak >/dev/null 2>&1; then
        print_warning "Flatpak CLI not found in PATH"
        print_info "Install Flatpak or re-run home-manager switch to enable declarative apps"
        return 1
    fi

    if ! ensure_flathub_remote; then
        print_warning "Flatpak applications will need to be installed manually once Flathub is available"
        return 1
    fi

    if ensure_default_flatpak_apps_installed; then
        return 0
    fi

    return 1
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
fi

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

install_single_ai_cli() {
    local descriptor="$1"
    local package display bin_command wrapper_name extension_id debug_env

    IFS='|' read -r package display bin_command wrapper_name extension_id debug_env <<<"$descriptor"

    if [ -z "$package" ] || [ -z "$display" ] || [ -z "$bin_command" ] || [ -z "$wrapper_name" ]; then
        print_warning "Invalid manifest entry: $descriptor"
        return 1
    fi

    local default_prefix
    default_prefix="${PRIMARY_HOME:-$HOME}/.npm-global"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$default_prefix}"
    local npm_modules="$npm_prefix/lib/node_modules"
    local package_dir="$npm_modules/$package"
    local wrapper_path="$npm_prefix/bin/$wrapper_name"
    local install_needed=false
    local current_version=""
    local latest_version=""

    if [ -f "$package_dir/package.json" ]; then
        current_version=$(node -e "const pkg=require(process.argv[1]); if(pkg && pkg.version){console.log(pkg.version);}" "$package_dir/package.json" 2>/dev/null || echo "")
    fi

    latest_version=$(run_as_primary_user npm view "$package" version 2>/dev/null || echo "")

    if [ "$FORCE_UPDATE" = true ]; then
        install_needed=true
    elif [ -z "$current_version" ]; then
        install_needed=true
    elif [ -n "$latest_version" ] && [ "$current_version" != "$latest_version" ]; then
        print_info "$display update available: $current_version → $latest_version"
        install_needed=true
    fi

    if [ "$install_needed" = true ]; then
        local log_file="/tmp/${wrapper_name}-npm-install.log"
        local attempt=1
        local max_attempts=$RETRY_MAX_ATTEMPTS
        local timeout=2
        local install_exit=0
        print_info "Installing $display via npm..."

        while (( attempt <= max_attempts )); do
            run_as_primary_user env NPM_CONFIG_PREFIX="$npm_prefix" npm install -g "$package" \
                2>&1 | tee "$log_file"
            install_exit=${PIPESTATUS[0]}

            if (( install_exit == 0 )); then
                print_success "$display npm package installed"
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
            local not_found=0
            if grep -qiE 'E404|Not Found' "$log_file" 2>/dev/null; then
                not_found=1
                print_warning "$display is not available from the npm registry (HTTP 404) – skipping"
                print_detail "Package $package was not found upstream"
            else
                print_warning "$display installation failed after $max_attempts attempts (exit code $install_exit)"
            fi
            print_detail "See $log_file for details"
            print_detail "Manual install: npm install -g $package"
            if (( not_found == 1 )); then
                cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
echo "[$display] npm package $package is not currently available." >&2
echo "Install it manually once published: npm install -g $package" >&2
exit 127
EOF
                chmod +x "$wrapper_path"
                return 0
            fi
            return 1
        fi
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

install_claude_code() {
    print_section "Installing AI Coding CLIs"

    if ! command -v npm >/dev/null 2>&1; then
        print_warning "npm not available – skipping AI CLI installation"
        return 1
    fi

    if ! command -v node >/dev/null 2>&1; then
        print_warning "Node.js not available – skipping AI CLI installation"
        return 1
    fi

    ensure_npm_global_prefix

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ ! -f "$manifest" ]; then
        print_warning "AI CLI manifest not found at $manifest"
        return 1
    fi

    # shellcheck disable=SC1090
    source "$manifest"

    if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -eq 0 ]; then
        print_info "No AI CLI packages defined in manifest"
        return 0
    fi

    AI_VSCODE_EXTENSIONS=()

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

    if [ ! -f "$settings_file" ]; then
        echo "{}" >"$settings_file"
    fi

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ ! -f "$manifest" ]; then
        print_warning "AI CLI manifest not found, skipping VSCodium settings update"
        return 0
    fi

    # shellcheck disable=SC1090
    source "$manifest"

    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local wrapper_dir="$npm_prefix/bin"
    local npm_modules="$npm_prefix/lib/node_modules"

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

    local entry package display bin_command wrapper_name extension_id debug_env
    local overall_status=0
    for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
        IFS='|' read -r package display bin_command wrapper_name extension_id debug_env <<<"$entry"
        local wrapper_path="$wrapper_dir/$wrapper_name"
        local keys=()
        local extra=()
        case "$package" in
            "@anthropic-ai/claude-code")
                keys=("claude-code" "claudeCode")
                extra=("claude-code.claudeProcessWrapper" "claudeCode.claudeProcessWrapper")
                ;;
            "@openai/gpt-codex")
                keys=("gpt-codex" "gptCodex")
                ;;
            "@openai/codex")
                keys=("codex" "codexIDE" "codexIde")
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
            if ! apply_jq '.[ $base ] = (.[ $base ] // {}) | .[ $base ].executablePath = $wrapper | .[ $base ].environmentVariables = $env | .[ $base ].autoStart = false' \
                --arg base "$key" \
                --arg wrapper "$wrapper_path" \
                --argjson env "$env_json"; then
                overall_status=1
            fi
        done

        local extra_key
        for extra_key in "${extra[@]}"; do
            IFS='.' read -r extra_base extra_prop <<<"$extra_key"
            if [ -z "$extra_base" ] || [ -z "$extra_prop" ]; then
                continue
            fi
            if ! apply_jq '.[ $base ] = (.[ $base ] // {}) | .[ $base ][ $prop ] = $wrapper' \
                --arg base "$extra_base" \
                --arg prop "$extra_prop" \
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

    local manifest
    manifest=$(ai_cli_manifest_path)

    if [ -f "$manifest" ]; then
        # shellcheck disable=SC1090
        source "$manifest"
    else
        NPM_AI_PACKAGE_MANIFEST=()
    fi

    local extensions=(
        "Anthropic.claude-code|Claude Code"
        "OpenAI.gpt-codex|GPT CodeX"
        "OpenAI.codex-ide|Codex IDE"
        "GooseAI.gooseai-vscode|GooseAI"
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
        local entry package display bin_command wrapper_name extension_id debug_env
        for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
            IFS='|' read -r package display bin_command wrapper_name extension_id debug_env <<<"$entry"
            if [ -n "$extension_id" ]; then
                extensions+=("$extension_id|$display")
            fi
        done
    fi

    local install_ext
    install_ext() {
        local ext_id="$1"
        local name="$2"
        local attempt

        print_info "Installing: $name ($ext_id)"
        for attempt in 1 2 3; do
            if codium --install-extension "$ext_id" >/dev/null 2>&1; then
                print_success "$name extension installed"
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
        if [ -n "${seen[$ext_id]:-}" ]; then
            continue
        fi
        seen[$ext_id]=1
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

    print_info "OpenSkills tooling installation is project-specific"
    print_info "This is a placeholder for custom project tools"

    # Check if there's a custom install script
    local openskills_install_script="$HOME/.config/openskills/install.sh"
    if [[ -f "$openskills_install_script" ]]; then
        print_info "Found OpenSkills install script, executing..."
        if bash "$openskills_install_script"; then
            print_success "OpenSkills tooling installed"
            return 0
        else
            print_warning "OpenSkills install script failed"
            return 1
        fi
    fi

    print_info "No custom OpenSkills tooling configured"
    print_info "Create $openskills_install_script to add custom tools"

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

    # Check if our flake configuration is valid
    if [[ -f "$HM_CONFIG_DIR/flake.nix" ]]; then
        print_info "Validating flake configuration..."
        if nix flake check "$HM_CONFIG_DIR" 2>&1 | tee /tmp/flake-check.log; then
            print_success "Flake configuration is valid"
        else
            print_warning "Flake validation had issues (see /tmp/flake-check.log)"
            print_info "Configuration may still work, issues are often non-critical"
        fi
    fi

    print_success "Flake environment setup complete"
    return 0
}
