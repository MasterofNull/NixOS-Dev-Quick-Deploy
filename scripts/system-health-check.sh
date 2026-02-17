#!/usr/bin/env bash
# =============================================================================
# NixOS Dev Quick Deploy - System Health Check
# =============================================================================
# Validates that critical tooling is installed post-deployment. The script is
# intentionally verbose so operators can capture logs and triage regressions.
# =============================================================================

# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
#   ./system-health-check.sh [--detailed] [--fix]
#     --detailed  Show extended notes for every check
#     --fix       Attempt basic remediation where possible
# -----------------------------------------------------------------------------

# NOTE: -e intentionally omitted — health checks must report ALL failures, not
# stop at the first one.
set -uo pipefail

NONINTERACTIVE=false
if [[ ! -t 0 ]]; then
    NONINTERACTIVE=true
fi

HM_PROFILE_BIN="${HOME}/.local/state/nix/profiles/home-manager/bin"
if [[ -d "$HM_PROFILE_BIN" ]]; then
    case ":$PATH:" in
        *":$HM_PROFILE_BIN:"*) ;;
        *) PATH="$HM_PROFILE_BIN:$PATH" ;;
    esac
fi

# -----------------------------------------------------------------------------
# ANSI color palette for consistent messaging
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Simple confirm prompt (local to this script)
# -----------------------------------------------------------------------------
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response=""

    if [[ "$NONINTERACTIVE" == true ]]; then
        [[ "$default" =~ ^[Yy]$ ]]
        return $?
    fi

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e ${BLUE}?${NC} $prompt)" response
    response=${response:-$default}
    [[ "$response" =~ ^[Yy]$ ]]
}

# -----------------------------------------------------------------------------
# Check counters
# -----------------------------------------------------------------------------
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0
FIX_FAILURES=0
FIX_SUCCESSES=0

# -----------------------------------------------------------------------------
# CLI flags
# -----------------------------------------------------------------------------
DETAILED=false
FIX_ISSUES=false
TMP_ROOT="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"

# -----------------------------------------------------------------------------
# Fix tracking helpers
# -----------------------------------------------------------------------------
record_fix_success() {
    local label="$1"
    FIX_SUCCESSES=$((FIX_SUCCESSES + 1))
    print_success "Fix succeeded: $label"
}

record_fix_failure() {
    local label="$1"
    FIX_FAILURES=$((FIX_FAILURES + 1))
    print_fail "Fix failed: $label"
}

# -----------------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------------
for arg in "$@"; do
    case $arg in
        --detailed)
            DETAILED=true
            shift
            ;;
        --fix)
            FIX_ISSUES=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--detailed] [--fix]"
            echo ""
            echo "Options:"
            echo "  --detailed    Show detailed output for all checks"
            echo "  --fix         Attempt to fix common issues automatically"
            exit 0
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Repository metadata and sourced helpers
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NPM_MANIFEST_FILE="$REPO_ROOT/config/npm-packages.sh"
AI_STACK_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"

: "${LOG_DIR:=$REPO_ROOT/logs}"

if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi

KUBECTL_BIN="$(command -v kubectl 2>/dev/null || true)"
if [[ -z "$KUBECTL_BIN" && -x /run/current-system/sw/bin/kubectl ]]; then
    KUBECTL_BIN="/run/current-system/sw/bin/kubectl"
fi

if ! declare -F log >/dev/null 2>&1; then
    log() {
        return 0
    }
fi

if [ -z "${PRIMARY_USER:-}" ]; then
    if [ -n "${USER:-}" ]; then
        PRIMARY_USER="$USER"
    else
        PRIMARY_USER="$(id -un 2>/dev/null || true)"
    fi
fi

if [ -z "$PRIMARY_USER" ]; then
    PRIMARY_USER="root"
fi

COMMON_LIB="$REPO_ROOT/lib/common.sh"
if [ -f "$COMMON_LIB" ]; then
    # shellcheck disable=SC1091
    source "$COMMON_LIB"
fi

# -----------------------------------------------------------------------------
# Package manifests
# -----------------------------------------------------------------------------
declare -a NPM_AI_PACKAGE_MANIFEST=()

declare -a PYTHON_PACKAGE_CHECKS=(
    "pandas|Pandas (DataFrames)|required"
    "numpy|NumPy (numerical computing)|required"
    "sklearn|Scikit-learn (machine learning)|required"
    "torch|PyTorch|required"
    "tensorflow|TensorFlow|optional"
    "openai|OpenAI client|required"
    "anthropic|Anthropic client|required"
    "langchain|LangChain|required"
    "llama_index|LlamaIndex|optional"
    "chromadb|ChromaDB|optional"
    "qdrant_client|Qdrant client|required"
    "sentence_transformers|Sentence Transformers|required"
    "faiss|FAISS|optional"
    "polars|Polars (fast DataFrames)|required"
    "dask|Dask (parallel computing)|optional"
    "black|Black (formatter)|required"
    "ruff|Ruff (linter)|required"
    "mypy|Mypy (type checker)|required"
    "jupyterlab|Jupyter Lab|required"
    "notebook|Jupyter Notebook|optional"
    "transformers|Transformers (Hugging Face)|required"
    "accelerate|Accelerate|required"
    "datasets|Datasets (Hugging Face)|required"
    "gradio|Gradio|optional"
)

PYTHON_INTERPRETER=""
PYTHON_INTERPRETER_VERSION=""
PYTHON_INTERPRETER_NOTE_EMITTED=false

# -----------------------------------------------------------------------------
# Logging helpers
# -----------------------------------------------------------------------------
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

print_check() {
    echo -n "  Checking $1... "
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
    ((TOTAL_CHECKS++))
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED_CHECKS++))
    ((TOTAL_CHECKS++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNING_CHECKS++))
    ((TOTAL_CHECKS++))
}

print_info() {
    echo -e "  ${BLUE}•${NC} $1"
}

print_detail() {
    if [ "$DETAILED" = true ]; then
        echo -e "    ${BLUE}→${NC} $1"
    fi
}

# Fix functions
fix_shell_environment() {
    print_section "Attempting to fix shell environment..."

    # Source home-manager session vars
    if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
        print_detail "Sourcing home-manager session variables"
        source "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
        print_success "Sourced home-manager session variables"
    fi

    # Avoid sourcing ~/.zshrc from bash (can exit or fail on zsh-specific syntax).
    if [ -f "$HOME/.zshrc" ]; then
        print_detail "Skipping ~/.zshrc reload in non-interactive bash"
        print_detail "Run: exec zsh"
    fi
}

fix_home_manager() {
    print_section "Attempting to fix home-manager..."

    if [ -d "$HOME/.dotfiles/home-manager" ]; then
        print_detail "Found home-manager configuration at ~/.dotfiles/home-manager"
        cd "$HOME/.dotfiles/home-manager"

        local hm_target_user="${PRIMARY_USER:-${USER:-$(id -un 2>/dev/null || true)}}"
        local hm_flake=".#${hm_target_user}"

        local hm_cmd=()
        local hm_env=()
        local effective_max_jobs
        effective_max_jobs=$(nix show-config 2>/dev/null | awk -F' = ' '/^max-jobs/ {print $2; exit}')
        if [ "$effective_max_jobs" = "0" ]; then
            print_detail "max-jobs=0 detected; forcing max-jobs=1 for home-manager switch"
            hm_env=(env NIX_CONFIG="max-jobs = 1")
        fi
        if command -v home-manager >/dev/null 2>&1; then
            hm_cmd=(home-manager)
        else
            hm_cmd=(nix run github:nix-community/home-manager --)
        fi

        local backup_suffix="backup-$(date +%Y%m%d_%H%M%S)"
        print_detail "Running: ${hm_cmd[*]} switch --flake $hm_flake -b $backup_suffix"
        local hm_fix_log="${TMP_ROOT}/hm-fix.log"
        if "${hm_env[@]}" "${hm_cmd[@]}" switch --flake "$hm_flake" -b "$backup_suffix" \
            > >(tee "$hm_fix_log") 2>&1; then
            print_success "Successfully applied home-manager configuration"
            fix_shell_environment
        else
            print_fail "Failed to apply home-manager configuration"
            echo "  See ${hm_fix_log} for details"
        fi
    else
        print_fail "home-manager configuration not found at ~/.dotfiles/home-manager"
    fi
}

load_npm_manifest() {
    NPM_AI_PACKAGE_MANIFEST=()
    if [ -f "$NPM_MANIFEST_FILE" ]; then
        local manifest_path=""
        local repo_root=""
        manifest_path=$(readlink -f "$NPM_MANIFEST_FILE" 2>/dev/null || true)
        repo_root=$(readlink -f "$REPO_ROOT" 2>/dev/null || true)
        if [[ -z "$manifest_path" || -z "$repo_root" || "$manifest_path" != "$repo_root"* ]]; then
            print_fail "Refusing to source npm manifest outside repo: $NPM_MANIFEST_FILE"
            return 1
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
        ' "$NPM_MANIFEST_FILE")
    fi
}

ensure_npm_environment() {
    export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    mkdir -p "$NPM_CONFIG_PREFIX/bin" "$NPM_CONFIG_PREFIX/lib" "$NPM_CONFIG_PREFIX/lib/node_modules"

    local npmrc="$HOME/.npmrc"
    if [[ ! -f "$npmrc" ]]; then
        print_detail "Creating ~/.npmrc with correct prefix"
        printf 'prefix=%s\n' "$NPM_CONFIG_PREFIX" > "$npmrc"
        print_success "Created ~/.npmrc"
    elif ! grep -q '^[[:space:]]*prefix=' "$npmrc" 2>/dev/null; then
        print_detail "Appending prefix to existing ~/.npmrc"
        printf '\n# Added by system-health-check\nprefix=%s\n' "$NPM_CONFIG_PREFIX" >> "$npmrc"
        print_success "Updated ~/.npmrc with prefix"
    fi
}

resolve_manifest_cli_path() {
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

write_ai_wrapper() {
    local wrapper_path="$1"
    local cli_path="$2"
    local display_name="$3"
    local debug_env_var="${4:-}"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local npm_modules="$npm_prefix/lib/node_modules"

    cat > "$wrapper_path" <<EOF
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
}

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


fix_npm_packages() {
    print_section "Attempting to fix NPM packages..."

    ensure_npm_environment
    load_npm_manifest

    if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -eq 0 ]; then
        print_info "No AI CLI packages defined in manifest"
        return 0
    fi

    local npm_prefix="$NPM_CONFIG_PREFIX"
    local npm_modules="$npm_prefix/lib/node_modules"
    local entry package version display bin_command wrapper_name extension_id debug_env
    local fix_failed=0

    for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
        IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
        local log_file="${TMP_ROOT}/${wrapper_name}-npm-fix.log"
        local audit_log="${TMP_ROOT}/${wrapper_name}-npm-audit.log"
        local package_spec="${package}@${version}"
        local package_dir="$npm_modules/$package"
        local wrapper_path="$npm_prefix/bin/$wrapper_name"
        local current_version=""

        if [ -f "$package_dir/package.json" ]; then
            current_version=$(node -e "const pkg=require(process.argv[1]); if(pkg && pkg.version){console.log(pkg.version);}" "$package_dir/package.json" 2>/dev/null || echo "")
        fi

        if [ -n "$current_version" ] && [ "$current_version" = "$version" ] && [ ! -f "$wrapper_path" ]; then
            local cli_path
            cli_path=$(resolve_manifest_cli_path "$package_dir" "$bin_command") || cli_path=""
            if [ -n "$cli_path" ] && [ -f "$cli_path" ]; then
                write_ai_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
                print_success "Rebuilt wrapper: $wrapper_path"
                continue
            else
                print_warning "Unable to locate CLI entry for $display (wrapper rebuild failed)"
            fi
        fi

        if [[ -z "$version" || "$version" == "UNPINNED" ]]; then
            print_fail "Skipping $package (unpinned version)"
            fix_failed=1
            continue
        fi
        print_detail "Reinstalling $package"

        if npm install -g --ignore-scripts "$package_spec" > >(tee "$log_file") 2>&1; then
            print_success "$display npm package installed"

            local cli_path
            cli_path=$(resolve_manifest_cli_path "$package_dir" "$bin_command") || cli_path=""

            if [ -n "$cli_path" ] && [ -f "$cli_path" ]; then
                write_ai_wrapper "$wrapper_path" "$cli_path" "$display" "$debug_env"
                print_success "Updated wrapper: $wrapper_path"
            else
                print_warning "Unable to locate CLI entry for $display"
                print_detail "Check $log_file for npm output"
                fix_failed=1
            fi

            if ! npm audit --global --audit-level=high > >(tee "$audit_log") 2>&1; then
                if grep -qiE "EAUDITGLOBAL|does not support testing globals" "$audit_log" 2>/dev/null; then
                    print_info "$display npm audit skipped (npm does not support --global audits)"
                else
                    print_warning "$display npm audit reported issues (see $audit_log)"
                fi
            fi
        else
            print_fail "Failed to reinstall $display"
            echo "  See $log_file for details"
            fix_failed=1
        fi
    done

    if [[ "$fix_failed" -ne 0 ]]; then
        return 1
    fi
    return 0
}

fix_claude_code_native() {
    print_section "Attempting to fix Claude Code installation..."

    local claude_bin="$HOME/.local/bin/claude"
    local claude_alt="$HOME/.claude/bin/claude"

    # Remove stale npm installation if present
    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local old_npm_dir="$npm_prefix/lib/node_modules/@anthropic-ai/claude-code"
    if [ -d "$old_npm_dir" ]; then
        print_detail "Removing deprecated npm Claude Code installation"
        rm -rf "$old_npm_dir" 2>/dev/null || true
    fi

    mkdir -p "$HOME/.local/bin" 2>/dev/null || true

    local log_file="${TMP_ROOT}/claude-native-fix.log"
    print_detail "Installing Claude Code via native installer..."

    local installer_tmp
    installer_tmp="$(mktemp -p "$TMP_ROOT" claude-install.XXXXXX.sh)"
    local installer_hash=""
    local expected_hash="${CLAUDE_INSTALLER_SHA256:-}"

    if curl --max-time 120 --connect-timeout 10 -fsSL "https://claude.ai/install.sh" -o "$installer_tmp"; then
        if command -v sha256sum >/dev/null 2>&1; then
            installer_hash="$(sha256sum "$installer_tmp" | awk '{print $1}')"
        elif command -v shasum >/dev/null 2>&1; then
            installer_hash="$(shasum -a 256 "$installer_tmp" | awk '{print $1}')"
        fi

        if [[ -n "$installer_hash" ]]; then
            print_detail "Claude installer SHA-256: $installer_hash"
        fi

        if [[ -n "$expected_hash" && -n "$installer_hash" && "$installer_hash" != "$expected_hash" ]]; then
            print_fail "Claude installer hash mismatch (expected $expected_hash)"
            rm -f "$installer_tmp"
            return 1
        fi

        if [[ "$NONINTERACTIVE" == true && "${TRUST_REMOTE_SCRIPTS:-false}" != "true" ]]; then
            print_fail "Noninteractive mode blocks remote script execution without TRUST_REMOTE_SCRIPTS=true"
            rm -f "$installer_tmp"
            return 1
        fi

        if ! confirm "Run Claude installer script from https://claude.ai/install.sh?" "n"; then
            print_fail "Claude installer aborted by user"
            rm -f "$installer_tmp"
            return 1
        fi

        if bash "$installer_tmp" > >(tee "$log_file") 2>&1; then

        if [ -x "$claude_bin" ]; then
            print_success "Claude Code installed at $claude_bin"
        elif [ -x "$claude_alt" ]; then
            ln -sf "$claude_alt" "$claude_bin" 2>/dev/null || true
            print_success "Claude Code installed at $claude_alt (symlinked to $claude_bin)"
        else
            print_fail "Claude Code installer completed but binary not found"
            print_detail "See $log_file for details"
            return 1
        fi

        # Create backward-compatible symlink
        if [ -d "$npm_prefix/bin" ]; then
            ln -sf "$claude_bin" "$npm_prefix/bin/claude-wrapper" 2>/dev/null || true
            print_detail "Created compatibility symlink: $npm_prefix/bin/claude-wrapper"
        fi
        else
        print_fail "Failed to install Claude Code"
        print_detail "See $log_file for details"
        print_detail "Manual install: curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash"
        rm -f "$installer_tmp"
        return 1
        fi
    else
        print_fail "Failed to download Claude installer script"
        rm -f "$installer_tmp"
        return 1
    fi
    rm -f "$installer_tmp"
}

# Check functions
detect_python_interpreter() {
    if [ -n "$PYTHON_INTERPRETER" ] && [ -x "$PYTHON_INTERPRETER" ]; then
        return 0
    fi

    local candidates=()

    if [ -n "${PYTHON_AI_INTERPRETER:-}" ]; then
        candidates+=("$PYTHON_AI_INTERPRETER")
    fi

    candidates+=(
        "$HOME/.nix-profile/bin/python3"
        "$HOME/.nix-profile/bin/python"
        "$HOME/.local/state/nix/profiles/home-manager/bin/python3"
        "$HOME/.local/state/nix/profiles/home-manager/bin/python"
        "/run/current-system/sw/bin/python3"
        "/run/current-system/sw/bin/python"
    )

    if command -v python3 >/dev/null 2>&1; then
        candidates+=("$(command -v python3)")
    fi

    if command -v python >/dev/null 2>&1; then
        candidates+=("$(command -v python)")
    fi

    for candidate in "${candidates[@]}"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            PYTHON_INTERPRETER="$candidate"
            PYTHON_INTERPRETER_VERSION="$($candidate --version 2>&1 | tr -d '\r')"
            return 0
        fi
    done

    PYTHON_INTERPRETER=""
    PYTHON_INTERPRETER_VERSION=""
    return 1
}

python_module_available() {
    local module=$1

    if [ -z "$PYTHON_INTERPRETER" ]; then
        return 1
    fi

    "$PYTHON_INTERPRETER" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$module') else 1)" \
        >/dev/null 2>&1
}

python_module_version() {
    local module=$1

    if [ -z "$PYTHON_INTERPRETER" ]; then
        return 1
    fi

    "$PYTHON_INTERPRETER" -c "import importlib; mod = importlib.import_module('$module'); print(getattr(mod, '__version__', 'installed'))" \
        2>/dev/null
}

get_missing_python_packages() {
    local scope=${1:-required}
    local entry module description requirement include

    for entry in "${PYTHON_PACKAGE_CHECKS[@]}"; do
        IFS='|' read -r module description requirement <<<"$entry"
        include=false

        case "$scope" in
            required)
                if [ "$requirement" = "required" ] || [ "$requirement" = "true" ]; then
                    include=true
                fi
                ;;
            optional)
                if [ "$requirement" != "required" ] && [ "$requirement" != "true" ]; then
                    include=true
                fi
                ;;
            all)
                include=true
                ;;
        esac

        if [ "$include" = false ]; then
            continue
        fi

        if [ -z "$PYTHON_INTERPRETER" ] || ! python_module_available "$module"; then
            printf '%s|%s|%s\n' "$module" "$description" "$requirement"
        fi
    done
}

fix_python_environment() {
    print_section "Attempting to fix Python environment..."

    detect_python_interpreter >/dev/null 2>&1 || true

    mapfile -t missing_required_python < <(get_missing_python_packages "required")

    if [ ${#missing_required_python[@]} -eq 0 ]; then
        print_success "Required Python packages already present"
        if [ -n "$PYTHON_INTERPRETER" ] && [ "$DETAILED" = true ]; then
            print_detail "Interpreter: $PYTHON_INTERPRETER"
        fi
        return
    fi

    if [ "$DETAILED" = true ]; then
        for missing_entry in "${missing_required_python[@]}"; do
            IFS='|' read -r _module missing_desc _requirement <<<"$missing_entry"
            print_detail "Missing: $missing_desc"
        done
    fi

    if [ -d "$HOME/.dotfiles/home-manager" ]; then
        local hm_target_user="${PRIMARY_USER:-${USER:-$(id -un 2>/dev/null || true)}}"
        local hm_python_target="$HOME/.dotfiles/home-manager#$hm_target_user"
        local hm_cmd=()
        local hm_env=()
        local effective_max_jobs
        effective_max_jobs=$(nix show-config 2>/dev/null | awk -F' = ' '/^max-jobs/ {print $2; exit}')
        if [ "$effective_max_jobs" = "0" ]; then
            print_detail "max-jobs=0 detected; forcing max-jobs=1 for home-manager switch"
            hm_env=(env NIX_CONFIG="max-jobs = 1")
        fi
        if command -v home-manager >/dev/null 2>&1; then
            hm_cmd=(home-manager)
        else
            hm_cmd=(nix run github:nix-community/home-manager --)
        fi
        print_detail "Reapplying home-manager configuration to rebuild Python environment"
        local backup_suffix="backup-$(date +%Y%m%d_%H%M%S)"
        print_detail "Running: ${hm_cmd[*]} switch --flake $hm_python_target -b $backup_suffix"
        local hm_python_log="${TMP_ROOT}/hm-python-fix.log"
        if "${hm_env[@]}" "${hm_cmd[@]}" switch --flake "$hm_python_target" -b "$backup_suffix" \
            > >(tee "$hm_python_log") 2>&1; then
            print_success "Reapplied home-manager configuration"
            detect_python_interpreter >/dev/null 2>&1 || true

            mapfile -t missing_required_python < <(get_missing_python_packages "required")
            if [ ${#missing_required_python[@]} -eq 0 ]; then
                print_success "Verified required Python packages after rebuild"
            else
                print_warning "Some Python packages are still missing after rebuild"
            fi
        else
            print_fail "Failed to apply home-manager configuration"
            echo "  See ${hm_python_log} for details"
        fi
    else
        print_warning "Home-manager configuration unavailable; install Python packages manually"
    fi
}

check_command() {
    local cmd=$1
    local package_name=$2
    local required=${3:-true}

    print_check "$package_name"

    if command -v "$cmd" &> /dev/null; then
        local version
        case $cmd in
            go)
                version=$($cmd version 2>&1 | head -n1)
                ;;
            podman|python3|node|cargo|aider|nvim)
                version=$($cmd --version 2>&1 | head -n1)
                ;;
            home-manager)
                version=$($cmd --version 2>&1 | head -n1)
                ;;
            *)
                version="installed"
                ;;
        esac
        print_success "$package_name ($version)"
        print_detail "Location: $(which $cmd)"
        return 0
    else
        if [ "$required" = true ]; then
            print_fail "$package_name not found"
            return 1
        else
            print_warning "$package_name not found (optional)"
            return 2
        fi
    fi
}

check_file_exists() {
    local file=$1
    local description=$2
    local required=${3:-true}

    print_check "$description"

    if [ -f "$file" ]; then
        print_success "$description"
        print_detail "Location: $file"
        return 0
    elif [ -L "$file" ]; then
        if [ -e "$file" ]; then
            print_success "$description (symlink)"
            print_detail "Location: $file -> $(readlink -f $file)"
            return 0
        else
            print_fail "$description (broken symlink)"
            print_detail "Location: $file -> $(readlink $file)"
            return 1
        fi
    else
        if [ "$required" = true ]; then
            print_fail "$description not found"
            return 1
        else
            print_warning "$description not found (optional)"
            return 2
        fi
    fi
}

check_directory_exists() {
    local dir=$1
    local description=$2
    local required=${3:-true}

    print_check "$description"

    if [ -d "$dir" ]; then
        local count=$(ls -A "$dir" 2>/dev/null | wc -l)
        print_success "$description ($count items)"
        print_detail "Location: $dir"
        return 0
    else
        if [ "$required" = true ]; then
            print_fail "$description not found"
            return 1
        else
            print_warning "$description not found (optional)"
            return 2
        fi
    fi
}

normalize_channel_basename() {
    local raw=$1

    raw=${raw##*/}
    raw=${raw%%\?*}
    raw=${raw%.tar.gz}
    raw=${raw%.tar.xz}
    raw=${raw%.tar.bz2}
    raw=${raw%.tar}
    raw=${raw%.tgz}
    raw=${raw%.zip}

    echo "$raw"
}

nix_channel_supports_profile_flag() {
    if [[ -n "${NIX_CHANNEL_PROFILE_SUPPORT:-}" ]]; then
        [[ "$NIX_CHANNEL_PROFILE_SUPPORT" == "yes" ]]
        return
    fi

    local help_output=""
    if ! help_output=$(nix-channel --help 2>&1); then
        NIX_CHANNEL_PROFILE_SUPPORT="yes"
        [[ "$NIX_CHANNEL_PROFILE_SUPPORT" == "yes" ]]
        return
    fi

    if grep -q -- "--profile" <<<"$help_output"; then
        NIX_CHANNEL_PROFILE_SUPPORT="yes"
    else
        NIX_CHANNEL_PROFILE_SUPPORT="no"
    fi

    [[ "$NIX_CHANNEL_PROFILE_SUPPORT" == "yes" ]]
}

check_nix_channel() {
    local profile=$1
    local alias=$2
    local expected=$3
    local description=$4

    print_check "$description"

    local list_output=""
    if [ -n "$profile" ]; then
        if ! nix_channel_supports_profile_flag; then
            print_success "$description (nix-channel lacks --profile flag; skipping system check)"
            print_detail "Current nix-channel build does not expose --profile; run 'sudo nix-channel --list' manually if needed."
            return 0
        fi
        local channel_output=""
        if ! channel_output=$(nix-channel --list --profile "$profile" 2>&1); then
            if echo "$channel_output" | grep -qi "unsupported argument '--profile'\\|unknown option '--profile'"; then
                print_success "$description (nix-channel lacks --profile flag; skipping system check)"
                print_detail "Current nix-channel build does not expose --profile; run 'sudo nix-channel --list' manually if needed."
                return 0
            fi
            if echo "$channel_output" | grep -qi "permission denied"; then
                print_success "$description (requires root access, skipping)"
                print_detail "Run with: sudo nix-channel --list --profile '$profile'"
                return 0
            fi
            print_warning "Unable to query $alias channel"
            print_detail "$channel_output"
            return 1
        fi
        list_output="$channel_output"
    else
        if ! list_output=$(nix-channel --list 2>/dev/null); then
            print_warning "Unable to query $alias channel"
            return 1
        fi
    fi

    local actual_url=""
    actual_url=$(printf '%s\n' "$list_output" | awk -v target="$alias" '$1 == target {print $2}' | tail -n1)

    if [ -z "$actual_url" ]; then
        print_fail "$alias channel not configured"
        return 1
    fi

    local actual_name
    actual_name=$(normalize_channel_basename "$actual_url")

    if [ "$actual_name" = "$expected" ]; then
        print_success "$alias channel set to $actual_name"
        print_detail "Source: $actual_url"
        return 0
    fi

    print_warning "$alias channel points to $actual_name (expected $expected)"
    print_detail "Source: $actual_url"
    return 1
}

check_flatpak_app() {
    local app_id=$1
    local app_name=$2
    local required=${3:-false}

    print_check "$app_name (Flatpak)"

    if ! command -v flatpak &> /dev/null; then
        print_fail "Flatpak command not found"
        return 1
    fi

    local info_output=""
    local install_scope=""
    if info_output=$(flatpak info --user "$app_id" 2>/dev/null); then
        install_scope="user"
    elif info_output=$(flatpak info --system "$app_id" 2>/dev/null); then
        install_scope="system"
    fi

    if [[ -n "$info_output" ]]; then
        local version=""
        version=$(printf '%s\n' "$info_output" | awk -F': +' '/^Version:/ {print $2; exit}')
        if [[ -z "$version" ]]; then
            version="unknown"
        fi
        print_success "$app_name (v$version)"
        print_detail "App ID: $app_id (${install_scope} install)"
        return 0
    fi

    if [ "$required" = true ]; then
        print_fail "$app_name not installed"
        return 1
    fi

    print_warning "$app_name not installed (optional)"
    return 2
}

check_flatpak_remote() {
    local remote_name=$1
    local description=$2
    local required=${3:-true}

    print_check "$description"

    if ! command -v flatpak &> /dev/null; then
        if [ "$required" = true ]; then
            print_fail "Flatpak command not available"
        else
            print_warning "Flatpak command not available"
        fi
        return 1
    fi

    local remote_line=""
    local scope
    for scope in --user --system ""; do
        local remote_output=""
        if [ -n "$scope" ]; then
            remote_output=$(flatpak remotes "$scope" --columns=name,url 2>/dev/null || true)
        else
            remote_output=$(flatpak remotes --columns=name,url 2>/dev/null || true)
        fi

        if [ -n "$remote_output" ]; then
            remote_line=$(printf '%s\n' "$remote_output" | awk -v name="$remote_name" 'NR == 1 {next} $1 == name {print $0}' | head -n1)
        fi

        if [ -n "$remote_line" ]; then
            break
        fi
    done

    if [ -z "$remote_line" ]; then
        if [ "$required" = true ]; then
            print_fail "$remote_name remote not configured"
        else
            print_warning "$remote_name remote not configured"
        fi
        return 1
    fi

    local remote_url
    remote_url=$(printf '%s\n' "$remote_line" | awk '{print $2}')
    print_success "$remote_name remote present"
    if [ -n "$remote_url" ]; then
        print_detail "Source: $remote_url"
    fi

    return 0
}

check_shell_alias() {
    local alias_name=$1
    local description=$2

    print_check "$description"

    # Check if alias exists
    if alias "$alias_name" &> /dev/null 2>&1; then
        local alias_value=$(alias "$alias_name" 2>&1 | sed "s/^$alias_name=//")
        print_success "$description"
        print_detail "Alias: $alias_value"
        return 0
    # Check if it's a function
    elif declare -f "$alias_name" &> /dev/null; then
        print_success "$description (function)"
        return 0
    else
        print_fail "$description not found"
        return 1
    fi
}

check_path_variable() {
    print_check "PATH configuration"

    local required_paths=(
        "$HOME/.nix-profile/bin"
        "$HOME/.local/bin"
        "$HOME/.npm-global/bin"
    )

    local missing_paths=()

    for path in "${required_paths[@]}"; do
        if [[ ":$PATH:" != *":$path:"* ]]; then
            missing_paths+=("$path")
        fi
    done

    if [ ${#missing_paths[@]} -eq 0 ]; then
        print_success "All required paths in PATH"
        if [ "$DETAILED" = true ]; then
            echo -e "    ${BLUE}→${NC} PATH includes:"
            for path in "${required_paths[@]}"; do
                echo -e "      • $path"
            done
        fi
        return 0
    else
        print_warning "Some paths missing from PATH"
        echo -e "    ${YELLOW}Missing:${NC}"
        for path in "${missing_paths[@]}"; do
            echo -e "      • $path"
        done
        return 2
    fi
}

check_python_package() {
    local package=$1
    local description=$2
    local required=${3:-false}
    local required_flag=false

    if [ "$required" = true ] || [ "$required" = "required" ]; then
        required_flag=true
    fi

    print_check "Python: $description"

    if [ -z "$PYTHON_INTERPRETER" ]; then
        if [ "$PYTHON_INTERPRETER_NOTE_EMITTED" = false ] && [ "$DETAILED" = true ]; then
            print_detail "Python interpreter not detected; set PYTHON_AI_INTERPRETER to override"
            PYTHON_INTERPRETER_NOTE_EMITTED=true
        fi

        if [ "$required_flag" = true ]; then
            print_fail "$description cannot be verified (no Python interpreter)"
            return 1
        else
            print_warning "$description check skipped (no Python interpreter)"
            return 2
        fi
    fi

    if python_module_available "$package"; then
        local version
        version=$(python_module_version "$package" || echo "installed")
        if [ -z "$version" ]; then
            version="installed"
        fi
        print_success "$description ($version)"
        if [ "$DETAILED" = true ] && [ "$PYTHON_INTERPRETER_NOTE_EMITTED" = false ]; then
            print_detail "Interpreter: $PYTHON_INTERPRETER"
            if [ -n "$PYTHON_INTERPRETER_VERSION" ]; then
                print_detail "Python version: $PYTHON_INTERPRETER_VERSION"
            fi
            PYTHON_INTERPRETER_NOTE_EMITTED=true
        fi
        return 0
    else
        if [ "$required_flag" = true ]; then
            print_fail "$description not found"
            return 1
        else
            print_warning "$description not found (optional)"
            return 2
        fi
    fi
}

check_systemd_service() {
    local service=$1
    local description=$2
    local check_running=${3:-false}
    local required=${4:-true}

    # Gracefully handle environments without a user systemd instance
    if ! systemctl --user show-environment >/dev/null 2>&1; then
        print_warning "$description (user systemd unavailable, skipping)"
        print_detail "Hint: Run inside a logged-in user session to evaluate $service."
        return 2
    fi

    print_check "$description"

    # Check if service unit exists
    if ! systemctl --user list-unit-files | grep -q "^${service}.service"; then
        if [ "$required" = true ]; then
            print_fail "$description service not configured"
            return 1
        fi
        print_warning "$description service not configured (optional)"
        return 2
    fi

    # Check if service is enabled
    local enabled="disabled"
    if systemctl --user is-enabled "$service" &> /dev/null; then
        enabled="enabled"
    fi

    # Check if service is running
    if systemctl --user is-active "$service" &> /dev/null; then
        print_success "$description (running, $enabled)"
        print_detail "Status: Active"
        return 0
    else
        if [ "$check_running" = true ]; then
            print_warning "$description (not running, $enabled)"
            print_detail "Start with: systemctl --user start $service"
        else
            print_success "$description (configured, $enabled)"
            print_detail "Enable with: systemctl --user enable --now $service"
        fi
        return 2
    fi
}

check_system_service() {
    local service=$1
    local description=$2
    local check_running=${3:-false}
    local required=${4:-true}

    print_check "$description"

    if ! systemctl list-unit-files >/dev/null 2>&1; then
        print_warning "$description (systemd unavailable, skipping)"
        return 2
    fi

    # Check if service unit exists (system-level)
    if ! systemctl list-unit-files | grep -q "^${service}.service"; then
        if [ "$required" = true ]; then
            print_fail "$description service not configured"
            return 1
        fi
        print_warning "$description service not configured (optional)"
        return 2
    fi

    # Check if service is enabled
    local enabled="disabled"
    if systemctl is-enabled "$service" &> /dev/null; then
        enabled="enabled"
    fi

    # Check if service is running
    if systemctl is-active "$service" &> /dev/null; then
        print_success "$description (running, $enabled)"
        print_detail "Status: Active"
        return 0
    fi

    if [ "$check_running" = true ]; then
        if [ "$required" = true ]; then
            print_fail "$description (not running, $enabled)"
            print_detail "Check logs: journalctl -u $service"
            print_detail "Start with: sudo systemctl start $service"
            return 1
        fi
        print_warning "$description (not running, $enabled)"
        print_detail "Check logs: journalctl -u $service"
        print_detail "Start with: sudo systemctl start $service"
        return 2
    fi

    print_success "$description (configured, $enabled)"
    print_detail "Enable with: sudo systemctl enable --now $service"
    return 2
}

check_systemd_service_port() {
    local service=$1
    local port=$2
    local description=$3

    # Only check port if service is running
    if systemctl --user is-active "$service" &> /dev/null; then
        if curl -s --max-time 2 --connect-timeout 1 "http://${SERVICE_HOST:-localhost}:$port" &> /dev/null || nc -z localhost "$port" 2>/dev/null; then
            print_detail "Service accessible on port $port"
            return 0
        else
            print_detail "Service running but port $port not accessible"
            return 1
        fi
    fi
    return 0
}

check_guardrail_monitor() {
    local service="$1"
    local timer="$2"
    local description="$3"

    print_check "$description"

    if ! command -v systemctl >/dev/null 2>&1; then
        print_warning "$description check skipped (systemctl unavailable)"
        return 2
    fi

    if ! systemctl list-unit-files 2>/dev/null | grep -q "^${service}.service"; then
        print_warning "$description not configured"
        return 2
    fi

    local timer_active="unknown"
    local timer_enabled="unknown"
    if systemctl list-unit-files 2>/dev/null | grep -q "^${timer}.timer"; then
        timer_active="$(systemctl is-active "${timer}.timer" 2>/dev/null || echo "unknown")"
        timer_enabled="$(systemctl is-enabled "${timer}.timer" 2>/dev/null || echo "unknown")"
    fi

    local unit_active="unknown"
    local unit_result="unknown"
    unit_active="$(systemctl is-active "${service}.service" 2>/dev/null || echo "unknown")"
    unit_result="$(systemctl show -p Result --value "${service}.service" 2>/dev/null || echo "unknown")"

    if systemctl is-failed --quiet "${service}.service" 2>/dev/null || [[ "$unit_result" == "failed" ]]; then
        print_fail "$description failed (result: $unit_result)"
        if [ "$DETAILED" = true ]; then
            print_detail "Recent logs: journalctl -u ${service}.service -n 30 --no-pager"
        fi
        return 1
    fi

    if [[ "$timer_active" == "active" ]]; then
        print_success "$description healthy (timer: active/$timer_enabled, last result: $unit_result)"
    elif [[ "$timer_active" == "unknown" ]]; then
        print_warning "$description timer status unavailable"
    else
        print_warning "$description timer not active (timer: $timer_active/$timer_enabled, last result: $unit_result)"
    fi

    if [ "$DETAILED" = true ]; then
        print_detail "Service state: ${unit_active}, result: ${unit_result}"
    fi

    return 0
}

# Main checks
run_all_checks() {
    print_header "NixOS Dev Quick Deploy - System Health Check"

    echo ""
    echo "Running comprehensive system health check..."
    echo "Start time: $(date)"
    echo ""

    load_npm_manifest

    # ==========================================================================
    # Core System Tools
    # ==========================================================================
    print_section "Core System Tools"

    local require_podman=true
    if [[ "${REQUIRE_PODMAN:-}" == "true" ]]; then
        require_podman=true
    elif [[ "${REQUIRE_PODMAN:-}" == "false" ]]; then
        require_podman=false
    else
        if command -v systemctl >/dev/null 2>&1 && systemctl is-active k3s >/dev/null 2>&1; then
            require_podman=false
        elif [[ -f "/etc/rancher/k3s/k3s.yaml" ]]; then
            require_podman=false
        fi
    fi

    check_command "podman" "Podman" "$require_podman"

    print_section "Rootless Podman Diagnostics"
    if command -v podman >/dev/null 2>&1 && declare -F run_rootless_podman_diagnostics >/dev/null 2>&1; then
        if run_rootless_podman_diagnostics "$PRIMARY_USER"; then
            print_info "Rootless Podman diagnostics completed."
        else
            print_info "Rootless Podman diagnostics detected issues; review the messages above."
        fi
    else
        print_warning "Podman diagnostics skipped (podman not available or helper missing)."
    fi
    check_command "git" "Git" true
    check_command "curl" "cURL" true
    check_command "wget" "wget" true

    # ==========================================================================
    # Programming Languages & Runtimes
    # ==========================================================================
    print_section "Programming Languages & Runtimes"

    check_command "python3" "Python 3" true
    check_command "node" "Node.js" true
    check_command "npm" "NPM" true
    check_command "go" "Go" true
    check_command "cargo" "Rust (cargo)" true
    check_command "ruby" "Ruby" true

    # ==========================================================================
    # Nix Ecosystem
    # ==========================================================================
    print_section "Nix Ecosystem"

    check_command "nix" "Nix package manager" true
    check_command "nix-env" "nix-env" true

    # Home Manager check with helpful context
    print_check "Home Manager"
    if command -v home-manager &> /dev/null; then
        local version=$(home-manager --version 2>&1 | head -n1)
        print_success "Home Manager ($version)"
        print_detail "Location: $(which home-manager)"
    else
        # Check if it's available via nix run
        if nix run home-manager/master -- --version &> /dev/null 2>&1; then
            print_success "Home Manager (available via 'nix run home-manager')"
            print_detail "Not in PATH but accessible via Nix flakes"
        else
            print_warning "Home Manager not found"
            print_detail "May need to run: home-manager switch --flake ~/.dotfiles/home-manager#$(whoami)"
            ((WARNING_CHECKS++))
            ((TOTAL_CHECKS++))
        fi
    fi

    # Check Nix flakes
    print_check "Nix flakes"
    if nix flake --help &> /dev/null 2>&1; then
        print_success "Nix flakes enabled"
    else
        print_fail "Nix flakes not enabled"
    fi

    # Check home-manager configuration
    check_directory_exists "$HOME/.dotfiles/home-manager" "Home Manager config directory" true
    check_file_exists "$HOME/.dotfiles/home-manager/flake.nix" "Home Manager flake.nix" true
    check_file_exists "$HOME/.dotfiles/home-manager/home.nix" "Home Manager home.nix" true

    # ==========================================================================
    # Channel Alignment
    # ==========================================================================
    print_section "Channel Alignment"

    local expected_nixpkgs="nixos-unstable"
    local expected_home="master"
    local nixos_version_raw=""
    nixos_version_raw=$(nixos-version 2>/dev/null | awk '{print $1}')
    if [[ "$nixos_version_raw" =~ ^([0-9]{2}\.[0-9]{2}) ]]; then
        expected_nixpkgs="nixos-${BASH_REMATCH[1]}"
        expected_home="release-${BASH_REMATCH[1]}"
    fi

    check_nix_channel "/nix/var/nix/profiles/per-user/root/channels" "nixos" "$expected_nixpkgs" "System nixos channel"
    check_nix_channel "" "nixpkgs" "$expected_nixpkgs" "User nixpkgs channel"
    check_nix_channel "" "home-manager" "$expected_home" "Home Manager channel"

    # ==========================================================================
    # AI Development Tools
    # ==========================================================================
    print_section "AI Development Tools"

    # --- Claude Code (native installer) ---
    local claude_native_bin="$HOME/.local/bin/claude"
    local claude_alt_bin="$HOME/.claude/bin/claude"
    local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
    local claude_legacy_wrapper="$npm_prefix/bin/claude-wrapper"

    print_check "Claude Code (native binary)"
    if [ -x "$claude_native_bin" ]; then
        local claude_version
        claude_version=$("$claude_native_bin" --version 2>/dev/null || echo "unknown")
        print_success "Claude Code native binary available (${claude_version})"
        print_detail "Binary: $claude_native_bin"
    elif [ -x "$claude_alt_bin" ]; then
        local claude_version
        claude_version=$("$claude_alt_bin" --version 2>/dev/null || echo "unknown")
        print_success "Claude Code native binary available (${claude_version})"
        print_detail "Binary: $claude_alt_bin"
        print_detail "Consider symlinking to $claude_native_bin for PATH consistency"
    elif command -v claude >/dev/null 2>&1; then
        local claude_location
        claude_location=$(command -v claude)
        local claude_version
        claude_version=$(claude --version 2>/dev/null || echo "unknown")
        print_success "Claude Code available (${claude_version})"
        print_detail "Location: $claude_location"
    elif [ -x "$claude_legacy_wrapper" ]; then
        print_warning "Claude Code found at legacy npm wrapper path only"
        print_detail "Legacy wrapper: $claude_legacy_wrapper"
        print_detail "Upgrade: curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash"
    else
        print_fail "Claude Code not found"
        print_detail "Install: curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash"
        print_detail "Checked: $claude_native_bin, $claude_alt_bin, PATH, $claude_legacy_wrapper"
    fi

    # --- NPM-based AI CLIs (OpenAI, CodeX, Goose, etc.) ---
    if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -eq 0 ]; then
        print_info "No npm-based AI CLIs defined in manifest"
    else
        local npm_modules="$npm_prefix/lib/node_modules"
        local entry package version display bin_command wrapper_name extension_id debug_env
        for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
            IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
            local required_package=true
            case "$package" in
                "@gooseai/cli")
                    required_package=false
                    ;;
            esac
            local wrapper_path="$npm_prefix/bin/$wrapper_name"
            print_check "$display wrapper"
            if [ -f "$wrapper_path" ]; then
                if command -v "$wrapper_name" >/dev/null 2>&1; then
                    print_success "$display wrapper available"
                    print_detail "Wrapper: $wrapper_path"
                    print_detail "In PATH: $(which "$wrapper_name")"
                else
                    print_warning "$display wrapper exists but is not on PATH"
                    print_detail "Wrapper: $wrapper_path"
                    print_detail 'Add to PATH: export PATH="$HOME/.npm-global/bin:$PATH"'
                fi
            else
                if [ "$required_package" = true ]; then
                    print_fail "$display wrapper not found"
                else
                    print_warning "$display wrapper not found (optional)"
                fi
                print_detail "Expected at: $wrapper_path"
                if [ "$package" = "@google/gemini-cli" ]; then
                    print_detail "If Gemini CLI install fails, ensure ripgrep is installed or set RIPGREP_BINARY and rerun --fix."
                fi
                if [[ -n "$version" && "$version" != "UNPINNED" ]]; then
                    print_detail "Install with: npm install -g ${package}@${version}"
                else
                    print_detail "Install with: npm install -g $package (version unpinned)"
                fi
            fi

            print_check "$display npm package"
            local package_dir="$npm_modules/$package"
            if [ -d "$package_dir" ]; then
                local pkg_json="$package_dir/package.json"
                local pkg_version="unknown"
                if [ -f "$pkg_json" ]; then
                    pkg_version=$(node -e "console.log(require(process.argv[1]).version)" "$pkg_json" 2>/dev/null || echo "unknown")
                fi
                print_success "$display npm package (v${pkg_version})"
                print_detail "Location: $package_dir"
            else
                if [ "$required_package" = true ]; then
                    print_fail "$display npm package not found"
                else
                    print_warning "$display npm package not found (optional)"
                fi
                if [[ -n "$version" && "$version" != "UNPINNED" ]]; then
                    print_detail "Install with: npm install -g ${package}@${version}"
                else
                    print_detail "Install with: npm install -g $package (version unpinned)"
                fi
            fi
        done
    fi

    # Other AI tools
    check_command "aider" "Aider" true
    check_command "openskills" "OpenSkills CLI" true

    local llama_cpp_url="${LLAMA_CPP_BASE_URL:-http://${SERVICE_HOST:-localhost}:8080}"
    local normalized_llama_cpp_url="${llama_cpp_url%/}"
    normalized_llama_cpp_url="${normalized_llama_cpp_url%/api/v1}"
    print_check "llama.cpp server health (${normalized_llama_cpp_url}/health)"
    if curl -sf --max-time 3 "${normalized_llama_cpp_url}/health" > /dev/null 2>&1; then
        print_success "llama.cpp server reachable"
    else
        print_warning "llama.cpp server not reachable (optional)"
        print_detail "Start via ./scripts/local-ai-starter.sh option 2 or kubectl --request-timeout=60s apply -k ai-stack/kubernetes"
    fi

    # ==========================================================================
    # Virtualization Stack (NixOS 25.11 Improvements)
    # ==========================================================================
    print_section "Virtualization Stack"

    # Check core virtualization tools
    check_command "virsh" "Virsh (libvirt CLI)" false
    check_command "virt-manager" "Virt-Manager (VM GUI)" false
    check_command "qemu-system-x86_64" "QEMU" false

    # Check KVM module loaded
    print_check "KVM kernel module"
    if lsmod | grep -q '^kvm'; then
        local kvm_type="unknown"
        if lsmod | grep -q 'kvm_intel'; then
            kvm_type="Intel VT-x"
        elif lsmod | grep -q 'kvm_amd'; then
            kvm_type="AMD-V"
        fi
        print_success "KVM module loaded ($kvm_type)"
        print_detail "Virtualization enabled and ready"
    else
        print_warning "KVM module not loaded (optional)"
        print_detail "Enable virtualization in BIOS and load module: modprobe kvm_intel or kvm_amd"
    fi

    # Check CPU virtualization support
    print_check "CPU virtualization support"
    local virt_support=$(egrep -c '(vmx|svm)' /proc/cpuinfo 2>/dev/null || echo "0")
    if [ "$virt_support" -gt 0 ]; then
        print_success "CPU supports virtualization ($virt_support cores)"
        print_detail "VT-x/AMD-V feature flags present"
    else
        print_warning "CPU virtualization support not detected (optional)"
        print_detail "Enable VT-x/AMD-V in BIOS settings"
    fi

    # Check libvirtd service
    check_system_service "libvirtd" "Libvirtd daemon" false false

    # Check if user is in libvirtd group
    print_check "Libvirtd group membership"
    if groups | grep -q libvirtd; then
        print_success "User in libvirtd group"
        print_detail "Can manage VMs without sudo"
    else
        print_warning "User not in libvirtd group (optional)"
        print_detail "Add with: sudo usermod -aG libvirtd $USER"
    fi

    # Check VM helper scripts
    check_command "vm-create-nixos" "vm-create-nixos helper" false
    check_command "vm-list" "vm-list helper" false
    check_command "vm-snapshot" "vm-snapshot helper" false

    # ==========================================================================
    # Testing Infrastructure (pytest)
    # ==========================================================================
    print_section "Testing Infrastructure"
    detect_python_interpreter >/dev/null 2>&1 || true

    # Check pytest and plugins
    check_python_package "pytest" "pytest core" false
    check_python_package "pytest_cov" "pytest-cov (coverage)" false
    check_python_package "pytest_xdist" "pytest-xdist (parallel)" false
    check_python_package "hypothesis" "Hypothesis (property-based)" false

    # Check testing helper scripts
    check_command "pytest-init" "pytest-init helper" false
    check_command "pytest-watch" "pytest-watch helper" false
    check_command "pytest-report" "pytest-report helper" false
    check_command "pytest-quick" "pytest-quick helper" false

    # ==========================================================================
    # Performance Optimizations
    # ==========================================================================
    print_section "Performance Optimizations"

    # Check zswap
    print_check "Zswap (compressed RAM swap)"
    if [ -f "/sys/module/zswap/parameters/enabled" ]; then
        local zswap_enabled=$(cat /sys/module/zswap/parameters/enabled 2>/dev/null || echo "N")
        if [ "$zswap_enabled" = "Y" ]; then
            local zswap_compressor=$(cat /sys/module/zswap/parameters/compressor 2>/dev/null || echo "unknown")
            print_success "Zswap enabled (compressor: $zswap_compressor)"
            print_detail "Memory compression active for better performance"
        else
            print_warning "Zswap available but disabled"
            print_detail "Enable in configuration.nix with boot.kernelParams"
        fi
    else
        print_warning "Zswap not available (optional)"
        print_detail "Kernel may not support zswap module"
    fi

    # Check I/O schedulers
    print_check "I/O scheduler optimization"
    local disk_count=0
    local optimized_count=0
    for disk in /sys/block/*/queue/scheduler; do
        if [ -f "$disk" ]; then
            disk_count=$((disk_count + 1))
            local current_scheduler=$(cat "$disk" | grep -oP '\[\K[^\]]+')
            local disk_name=$(echo "$disk" | cut -d'/' -f4)
            local disk_type="unknown"

            # Detect disk type
            if [[ "$disk_name" == nvme* ]]; then
                disk_type="NVMe"
                if [ "$current_scheduler" = "none" ]; then
                    optimized_count=$((optimized_count + 1))
                fi
            elif [ -f "/sys/block/$disk_name/queue/rotational" ]; then
                local rotational=$(cat "/sys/block/$disk_name/queue/rotational" 2>/dev/null || echo "1")
                if [ "$rotational" = "0" ]; then
                    disk_type="SSD"
                    if [ "$current_scheduler" = "mq-deadline" ] || [ "$current_scheduler" = "none" ]; then
                        optimized_count=$((optimized_count + 1))
                    fi
                else
                    disk_type="HDD"
                    if [ "$current_scheduler" = "bfq" ]; then
                        optimized_count=$((optimized_count + 1))
                    fi
                fi
            fi

            if [ "$DETAILED" = true ]; then
                print_detail "$disk_name: $current_scheduler ($disk_type)"
            fi
        fi
    done

    if [ $disk_count -gt 0 ]; then
        if [ $optimized_count -eq $disk_count ]; then
            print_success "I/O schedulers optimized ($optimized_count/$disk_count disks)"
        elif [ $optimized_count -gt 0 ]; then
            print_warning "I/O schedulers partially optimized ($optimized_count/$disk_count disks)"
            print_detail "Check optimizations.nix for proper scheduler configuration"
        else
            print_warning "I/O schedulers using defaults"
            print_detail "Enable optimization in optimizations.nix"
        fi
    else
        print_warning "No block devices found to check"
    fi

    # Check CPU governor
    print_check "CPU frequency governor"
    if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor" ]; then
        local governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "unknown")
        case "$governor" in
            schedutil)
                print_success "CPU governor: schedutil (balanced)"
                print_detail "Optimal for desktop/development workloads"
                ;;
            performance)
                print_success "CPU governor: performance (max speed)"
                print_detail "Best for performance, higher power usage"
                ;;
            powersave)
                print_warning "CPU governor: powersave (battery saving)"
                print_detail "May impact performance, good for laptops"
                ;;
            *)
                print_warning "CPU governor: $governor"
                print_detail "Consider schedutil for balanced performance"
                ;;
        esac
    else
        print_warning "CPU frequency scaling not available"
    fi

    # Check NixOS-Init (Rust-based initrd)
    print_check "NixOS-Init (Rust-based initrd)"
    if systemctl --version | grep -q "systemd"; then
        if [ -d "/run/systemd" ]; then
            # Check if system is using systemd in initrd
            if grep -q "systemd" /proc/cmdline 2>/dev/null; then
                print_success "Systemd-based initrd active"
                print_detail "NixOS 25.11 fast boot enabled"
            else
                print_warning "Traditional initrd (optional upgrade)"
                print_detail "Enable NixOS-Init in optimizations.nix"
            fi
        else
            print_warning "Systemd initrd status unclear"
        fi
    else
        print_warning "Systemd not detected"
    fi

    # Check tmpfs for /tmp
    print_check "Tmpfs for /tmp"
    if mount 2>/dev/null | grep -q "tmpfs on /tmp"; then
        local tmp_size=$(df -h /tmp 2>/dev/null | awk 'NR==2 {print $2}')
        print_success "Tmpfs enabled for /tmp (size: $tmp_size)"
        print_detail "Fast temporary file operations"
    else
        print_warning "/tmp not using tmpfs (optional)"
        print_detail "Enable in optimizations.nix for better performance"
    fi

    # Python AI/ML Packages
    # ==========================================================================
    print_section "Python AI/ML Packages"

    PYTHON_INTERPRETER_NOTE_EMITTED=false
    detect_python_interpreter >/dev/null 2>&1 || true

    if [ -n "$PYTHON_INTERPRETER" ] && [ "$DETAILED" = true ]; then
        print_detail "Using Python interpreter: $PYTHON_INTERPRETER"
        if [ -n "$PYTHON_INTERPRETER_VERSION" ]; then
            print_detail "Interpreter version: $PYTHON_INTERPRETER_VERSION"
        fi
        PYTHON_INTERPRETER_NOTE_EMITTED=true
    fi

    local python_entry module description requirement required_flag
    for python_entry in "${PYTHON_PACKAGE_CHECKS[@]}"; do
        IFS='|' read -r module description requirement <<<"$python_entry"
        required_flag=false
        if [ "$requirement" = "required" ] || [ "$requirement" = "true" ]; then
            required_flag=true
        fi
        check_python_package "$module" "$description" "$required_flag"
    done

    # ==========================================================================
    # Editors & IDEs
    # ==========================================================================
    print_section "Editors & IDEs"

    check_command "nvim" "Neovim" true
    check_command "codium" "VSCodium" true
    check_command "code-cursor" "Cursor launcher" false

    # VSCodium configuration
    check_directory_exists "$HOME/.config/VSCodium/User" "VSCodium config directory" true
    check_file_exists "$HOME/.config/VSCodium/User/settings.json" "VSCodium settings.json" true

    # ==========================================================================
    # Shell Configuration
    # ==========================================================================
    print_section "Shell Configuration"

    check_file_exists "$HOME/.zshrc" "ZSH configuration" true
    check_command "zsh" "ZSH shell" true

    # Check aliases and functions
    if [ -n "${ZSH_VERSION:-}" ] || [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "$HOME/.nix-profile/bin/zsh" ]; then
        # Source zshrc to get aliases
        source "$HOME/.zshrc" 2>/dev/null || true

        check_shell_alias "aidb-dev" "aidb-dev alias/function"
        check_shell_alias "aidb-shell" "aidb-shell alias"
        check_shell_alias "hms" "hms alias (home-manager switch)"
        check_shell_alias "nrs" "nrs alias (nixos-rebuild switch)"
    else
        print_warning "Not running in ZSH - skipping alias checks"
        ((TOTAL_CHECKS+=4))
        ((WARNING_CHECKS+=4))
    fi

    # Check Powerlevel10k
    check_file_exists "$HOME/.config/p10k/.configured" "Powerlevel10k configured" false

    # ==========================================================================
    # Flatpak Applications
    # ==========================================================================
    print_section "Flatpak Applications"

    # Check if flatpak is installed
    if ! command -v flatpak &> /dev/null; then
        print_fail "Flatpak command not found"
        ((TOTAL_CHECKS++))
        ((FAILED_CHECKS++))
    else
        check_flatpak_remote "flathub" "Flathub remote" true
        check_flatpak_remote "flathub-beta" "Flathub Beta remote" true

        # Core applications
        check_flatpak_app "com.google.Chrome" "Google Chrome" true
        check_flatpak_app "org.mozilla.firefox" "Firefox" true
        check_flatpak_app "md.obsidian.Obsidian" "Obsidian" true
        check_flatpak_app "ai.cursor.Cursor" "Cursor IDE" false
        check_flatpak_app "com.lmstudio.LMStudio" "LM Studio" false
        check_flatpak_app "io.podman_desktop.PodmanDesktop" "Podman Desktop" false

        # Utilities
        check_flatpak_app "com.github.tchx84.Flatseal" "Flatseal" false
        check_flatpak_app "net.nokyan.Resources" "Resources" false
        check_flatpak_app "org.gnome.FileRoller" "File Roller" false

        # Media
        check_flatpak_app "org.videolan.VLC" "VLC" false
        check_flatpak_app "io.mpv.Mpv" "MPV" false

        # Database Tools
        check_flatpak_app "com.dbeaver.DBeaverCommunity" "DBeaver Community" false
        check_flatpak_app "org.sqlitebrowser.sqlitebrowser" "SQLite Browser" false

        # Check for duplicate runtimes
        print_check "Flatpak runtime versions"
        local runtime_count=$(flatpak list --user --runtime 2>/dev/null | grep -c "org.freedesktop.Platform" 2>/dev/null || echo "0")
        runtime_count="${runtime_count//[^0-9]/}"  # Remove non-numeric characters
        runtime_count="${runtime_count:-0}"  # Default to 0 if empty
        if [[ "$runtime_count" -gt 4 ]]; then
            print_warning "Multiple Freedesktop Platform runtimes ($runtime_count found)"
            print_detail "This is normal - apps depend on different runtime versions"
            print_detail "Run 'flatpak uninstall --unused' to remove unused runtimes"
        else
            print_success "Flatpak runtimes (${runtime_count} versions)"
        fi
    fi

    # ==========================================================================
    # Environment Variables & PATH
    # ==========================================================================
    print_section "Environment Variables & PATH"

    check_path_variable

    # Check important environment variables
    print_check "NPM_CONFIG_PREFIX"
    if [ -n "${NPM_CONFIG_PREFIX:-}" ]; then
        print_success "NPM_CONFIG_PREFIX set to $NPM_CONFIG_PREFIX"
    else
        print_warning "NPM_CONFIG_PREFIX not set"
    fi

    print_check "EDITOR"
    if [ -n "${EDITOR:-}" ]; then
        print_success "EDITOR set to $EDITOR"
    else
        print_warning "EDITOR not set"
    fi

    # ==========================================================================
    # AI Stack Overview
    # ==========================================================================
    print_section "AI Stack Status"

    local kubeconfig_path="${KUBECONFIG:-}"
    if [[ -z "$kubeconfig_path" && -f /etc/rancher/k3s/k3s.yaml ]]; then
        kubeconfig_path="/etc/rancher/k3s/k3s.yaml"
    fi
    if [[ -n "$kubeconfig_path" ]]; then
        export KUBECONFIG="$kubeconfig_path"
    fi
    if [[ "$DETAILED" == "true" ]]; then
        print_detail "kubectl: ${KUBECTL_BIN:-not found}"
        print_detail "KUBECONFIG: ${kubeconfig_path:-<unset>}"
    fi

    print_check "K3s cluster connectivity"
    local kube_err=""
    if [[ -n "$KUBECTL_BIN" ]]; then
        kube_err=$("$KUBECTL_BIN" get nodes >/dev/null 2>&1 || true)
        if [[ -z "$kube_err" ]]; then
            print_success "kubectl can reach the cluster"
        else
            print_fail "kubectl unavailable or cluster unreachable"
            if [[ "$DETAILED" == "true" ]]; then
                print_detail "kubectl error: ${kube_err}"
            fi
        fi
    else
        print_fail "kubectl unavailable or cluster unreachable"
    fi

    print_check "AI stack pods (${AI_STACK_NAMESPACE})"
    local pods_output=""
    local pods_err=""
    if [[ -n "$KUBECTL_BIN" ]]; then
        pods_output=$("$KUBECTL_BIN" --request-timeout="${KUBECTL_TIMEOUT:-60}s" get pods -n "$AI_STACK_NAMESPACE" --no-headers 2>/dev/null || true)
        if [[ -z "$pods_output" ]]; then
            pods_err=$("$KUBECTL_BIN" --request-timeout="${KUBECTL_TIMEOUT:-60}s" get pods -n "$AI_STACK_NAMESPACE" --no-headers 2>&1 || true)
        fi
    fi

    if [[ -z "$pods_output" ]]; then
        if [[ -n "$pods_err" ]]; then
            print_warning "Unable to query pods in namespace '${AI_STACK_NAMESPACE}'"
            if [[ "$DETAILED" == "true" ]]; then
                print_detail "kubectl pods error: ${pods_err}"
            fi
        else
            print_warning "No pods reported in namespace '${AI_STACK_NAMESPACE}'"
        fi
    else
        local non_running=0
        local crashloop=0
        local imagepull=0
        local high_restarts=0
        local restart_threshold=5
        local restart_details=()

        while read -r name ready status restarts _rest; do
            [[ -z "$name" ]] && continue
            if [[ "$status" == "Completed" || "$status" == "Succeeded" ]]; then
                continue
            fi
            if [[ "$status" != "Running" ]]; then
                non_running=$((non_running + 1))
            fi
            if [[ "$status" == *CrashLoopBackOff* || "$status" == *Error* ]]; then
                crashloop=$((crashloop + 1))
            fi
            if [[ "$status" == *ImagePullBackOff* || "$status" == *ErrImagePull* ]]; then
                imagepull=$((imagepull + 1))
            fi
            if [[ "$restarts" =~ ^[0-9]+$ ]] && (( restarts > restart_threshold )); then
                high_restarts=$((high_restarts + 1))
                restart_details+=("${name}(${restarts})")
            fi
        done <<< "$pods_output"

        if (( crashloop > 0 )); then
            print_fail "CrashLoopBackOff detected for ${crashloop} pod(s)"
        elif (( imagepull > 0 )); then
            print_fail "Image pull failures detected for ${imagepull} pod(s)"
        elif (( non_running > 0 )); then
            print_warning "${non_running} pod(s) not in Running state"
        else
            print_success "All AI stack pods Running"
        fi

        if (( high_restarts > 0 )); then
            local restart_list="${restart_details[*]}"
            print_warning "${high_restarts} pod(s) restarted more than ${restart_threshold} times: ${restart_list}"
        fi
    fi

    # Jupyter Lab (user service)
    check_systemd_service "jupyter-lab" "Jupyter Lab (notebooks)" false false
    if systemctl --user is-active jupyter-lab &> /dev/null; then
        check_systemd_service_port "jupyter-lab" "8888" "Jupyter Lab"
    fi

    # Gitea development forge (system service)
    check_system_service "gitea" "Gitea (development forge)" true false

    # ==========================================================================
    # Nix Store & Profile Health
    # ==========================================================================
    print_section "Nix Store & Profile Health"

    if [[ "$NONINTERACTIVE" == true ]]; then
        print_warning "Skipping Nix store/profile checks in non-interactive mode (sudo unavailable)."
    else
        # Check nix store
        print_check "Nix store"
        if [ -d "/nix/store" ]; then
            local store_size=$(du -sh /nix/store 2>/dev/null | awk '{print $1}')
            print_success "Nix store ($store_size)"
            print_detail "Location: /nix/store"
        else
            print_fail "Nix store not found"
        fi

        # Check nix profile
        print_check "Nix profile"
        if [ -d "$HOME/.nix-profile" ]; then
            local profile_generation=$(nix-env --list-generations 2>/dev/null | tail -n1 | awk '{print $1}')
            print_success "Nix profile (generation $profile_generation)"
            print_detail "Location: $HOME/.nix-profile"
        else
            print_warning "Nix profile not found"
        fi
    fi

    # Check for broken symlinks in PATH
    print_check "Broken symlinks in PATH"
    local broken_count=0
    for path_dir in $(echo "$PATH" | tr ':' '\n'); do
        if [ -d "$path_dir" ]; then
            while IFS= read -r -d '' symlink; do
                if [ ! -e "$symlink" ]; then
                    ((broken_count++))
                    if [ "$DETAILED" = true ]; then
                        print_detail "Broken: $symlink"
                    fi
                fi
            done < <(find "$path_dir" -maxdepth 1 -type l -print0 2>/dev/null)
        fi
    done
    if [ $broken_count -eq 0 ]; then
        print_success "No broken symlinks in PATH"
    else
        print_warning "Found $broken_count broken symlinks in PATH"
        print_detail "Run 'nix-collect-garbage' to clean up"
    fi

    # ==========================================================================
    # Configuration Files Health
    # ==========================================================================
    print_section "Configuration Files Health"

    # Check npmrc
    print_check "NPM configuration (~/.npmrc)"
    if [ -f "$HOME/.npmrc" ]; then
        if grep -q "prefix=" "$HOME/.npmrc" 2>/dev/null; then
            local npm_prefix=$(grep "prefix=" "$HOME/.npmrc" | cut -d= -f2)
            print_success "NPM config (prefix: $npm_prefix)"
        else
            print_warning "NPM config exists but no prefix set"
        fi
    else
        print_warning "NPM config not found"
        print_detail "Create with: echo 'prefix=\$HOME/.npm-global' > ~/.npmrc"
    fi

    # Check gitconfig
    print_check "Git configuration (~/.gitconfig)"
    if [ -f "$HOME/.gitconfig" ]; then
        local git_user=$(git config --global user.name 2>/dev/null || echo "not set")
        local git_email=$(git config --global user.email 2>/dev/null || echo "not set")
        print_success "Git config (user: $git_user)"
        print_detail "Email: $git_email"
    else
        print_warning "Git config not found"
    fi

    # ==========================================================================
    # Boot + Filesystem Guardrails
    # ==========================================================================
    print_section "Boot + Filesystem Guardrails"

    check_command "fs-integrity-check" "Filesystem integrity checker" false
    check_command "disk-health-check" "Disk health checker" false

    check_guardrail_monitor "fs-integrity-monitor" "fs-integrity-monitor" "Filesystem integrity monitor"
    check_guardrail_monitor "disk-health-monitor" "disk-health-monitor" "Disk health monitor"

    print_check "Guardrail alert backlog"
    local guardrail_alert_dir="/var/lib/nixos-quick-deploy/alerts"
    if [[ -d "$guardrail_alert_dir" ]]; then
        local alert_count=0
        alert_count=$(find "$guardrail_alert_dir" -maxdepth 1 -type f | wc -l)
        if [[ "$alert_count" -eq 0 ]]; then
            print_success "No guardrail alerts queued"
        else
            print_warning "$alert_count guardrail alert file(s) present at $guardrail_alert_dir"
            print_detail "Review with: sudo ls -lt $guardrail_alert_dir"
        fi
    else
        print_success "No guardrail alert directory present"
    fi

    # Check flake lock completeness
    local hm_flake_dir="$HOME/.dotfiles/home-manager"
    local hm_flake_file="$hm_flake_dir/flake.nix"
    local hm_lock_file="$hm_flake_dir/flake.lock"
    print_check "Flake lock completeness"
    if [ -f "$hm_flake_file" ] && [ -f "$hm_lock_file" ] && command -v jq >/dev/null 2>&1; then
        # Extract declared inputs from flake.nix
        local declared_inputs
        declared_inputs=$(awk '
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
        ' "$hm_flake_file" | sort -u)
        # Extract locked inputs from flake.lock
        local locked_inputs
        locked_inputs=$(jq -r '.nodes.root.inputs // {} | keys[]' "$hm_lock_file" 2>/dev/null | sort -u)

        local missing_lock_inputs=""
        local input_name
        while IFS= read -r input_name; do
            [ -z "$input_name" ] && continue
            if ! echo "$locked_inputs" | grep -Fxq "$input_name"; then
                missing_lock_inputs="${missing_lock_inputs:+$missing_lock_inputs, }$input_name"
            fi
        done <<< "$declared_inputs"

        if [ -z "$missing_lock_inputs" ]; then
            local lock_count
            lock_count=$(echo "$locked_inputs" | wc -l)
            print_success "All flake inputs locked ($lock_count inputs)"
        else
            print_fail "Missing flake.lock entries: $missing_lock_inputs"
            print_detail "Fix: cd $hm_flake_dir && nix flake lock"
            print_detail "Or re-run deployment with --update-flake-inputs"
        fi
    elif [ ! -f "$hm_flake_file" ]; then
        print_detail "Flake configuration not found (skipped)"
    elif [ ! -f "$hm_lock_file" ]; then
        print_warning "No flake.lock found — run: cd $hm_flake_dir && nix flake lock"
    else
        print_detail "jq not available; skipping flake lock check"
    fi

    # ==========================================================================
    # Summary
    # ==========================================================================
    echo ""
    print_header "Health Check Summary"

    echo ""
    echo -e "  ${GREEN}Passed:${NC}   $PASSED_CHECKS"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNING_CHECKS"
    echo -e "  ${RED}Failed:${NC}   $FAILED_CHECKS"
    echo -e "  ${BLUE}Total:${NC}    $TOTAL_CHECKS"
    echo ""

    # Overall status
    if [ $FAILED_CHECKS -eq 0 ]; then
        echo -e "${GREEN}✓ System health check PASSED${NC}"
        echo ""
        echo "Your NixOS development environment is properly configured!"

        if [ $WARNING_CHECKS -gt 0 ]; then
            echo ""
            echo "Note: Some optional components have warnings."
            echo "Review the warnings above to see if action is needed."
        fi

        return 0
    else
        echo -e "${RED}✗ System health check FAILED${NC}"
        echo ""
        echo "Some required components are missing or misconfigured."
        echo ""

        if [ "$FIX_ISSUES" = false ]; then
            echo "Suggested fixes (try these in order):"
            echo ""

            # Check for common issues and provide specific guidance
            local suggestion_index=1

            if ! command -v git &> /dev/null; then
                echo -e "  ${YELLOW}${suggestion_index}. Git not available:${NC}"
                echo "     • Immediate fallback (no rebuild needed):"
                echo "       ./scripts/git-safe.sh status"
                echo "     • Declarative fix:"
                echo "       run deploy/switch to apply base system packages that include git"
                echo ""
                suggestion_index=$((suggestion_index + 1))
            fi

            if ! command -v home-manager &> /dev/null; then
                echo -e "  ${YELLOW}${suggestion_index}. Home Manager not in PATH:${NC}"
                echo "     • Source session variables:"
                echo "       source ~/.nix-profile/etc/profile.d/hm-session-vars.sh"
                echo "     • Then reload shell:"
                echo "       exec zsh"
                echo "     • If still missing, re-apply home-manager:"
                echo "       cd ~/.dotfiles/home-manager"
                echo "       nix run home-manager/master -- switch --flake .#$(whoami)"
                echo ""
                suggestion_index=$((suggestion_index + 1))
            fi

            # Check Claude Code (native installer)
            local claude_missing=false
            if [ ! -x "$HOME/.local/bin/claude" ] && [ ! -x "$HOME/.claude/bin/claude" ] && ! command -v claude >/dev/null 2>&1; then
                claude_missing=true
            fi

            if [ "$claude_missing" = true ]; then
                echo -e "  ${YELLOW}${suggestion_index}. Claude Code not installed:${NC}"
                echo "     • Install via native installer:"
                echo "       curl -fsSL --max-time 30 --connect-timeout 5 https://claude.ai/install.sh | bash"
                echo "     • Or use auto-fix:"
                echo "       $0 --fix"
                echo ""
                suggestion_index=$((suggestion_index + 1))
            fi

            # Check npm-based AI CLIs
            load_npm_manifest
            local missing_ai_tools=()
            if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -gt 0 ]; then
                local entry package version display bin_command wrapper_name extension_id debug_env
                for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
                    IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
                    if [ ! -f "$HOME/.npm-global/bin/$wrapper_name" ]; then
                        missing_ai_tools+=("$display|$package|$version")
                    fi
                done
            fi

            if [ ${#missing_ai_tools[@]} -gt 0 ]; then
                echo -e "  ${YELLOW}${suggestion_index}. AI CLI tools missing:${NC}"
                echo "     • Install via NPM:"
                echo "       export NPM_CONFIG_PREFIX=~/.npm-global"
                local tool
                for tool in "${missing_ai_tools[@]}"; do
                    IFS='|' read -r display package version <<<"$tool"
                    if [[ -n "$version" && "$version" != "UNPINNED" ]]; then
                        echo "       npm install -g ${package}@${version}    # $display"
                    else
                        echo "       npm install -g ${package}    # $display (version unpinned)"
                    fi
                done
                echo "     • Or use auto-fix:"
                echo "       $0 --fix"
                echo ""
                suggestion_index=$((suggestion_index + 1))
            fi

            detect_python_interpreter >/dev/null 2>&1 || true
            local -a missing_required_python=()
            mapfile -t missing_required_python < <(get_missing_python_packages "required")
            local -a missing_optional_python=()
            mapfile -t missing_optional_python < <(get_missing_python_packages "optional")

            if [ ${#missing_required_python[@]} -gt 0 ]; then
                echo -e "  ${YELLOW}${suggestion_index}. Python packages missing:${NC}"
                echo "     • These should be installed via home-manager"
                echo "     • If home-manager was just applied, reload your shell:"
                echo "       exec zsh"
                echo "     • If still missing, check if packages built successfully:"
                echo "       nix-store --verify-path ~/.nix-profile"
                echo "     • Re-apply home-manager to rebuild Python environment:"
                echo "       cd ~/.dotfiles/home-manager && home-manager switch --flake .#$(whoami)"
                echo "     • Missing modules detected:"
                for missing_entry in "${missing_required_python[@]}"; do
                    IFS='|' read -r _module missing_desc _requirement <<<"$missing_entry"
                    echo "       - $missing_desc"
                done
                echo ""
            fi

            if [ ${#missing_optional_python[@]} -gt 0 ]; then
                echo -e "  ${YELLOW}${suggestion_index}. Optional Python packages missing:${NC}"
                echo "     • These are not installed by default to avoid nixpkgs conflicts"
                echo "     • Install via the optional agent requirements file:"
                echo "       pip install -r ~/.config/ai-agents/requirements.txt"
                echo "     • Missing modules detected:"
                for missing_entry in "${missing_optional_python[@]}"; do
                    IFS='|' read -r _module missing_desc _requirement <<<"$missing_entry"
                    echo "       - $missing_desc"
                done
                echo ""
            fi
            echo -e "  ${YELLOW}Quick fix (attempts all repairs automatically):${NC}"
            echo "     $0 --fix"
            echo ""

            echo -e "  ${YELLOW}Manual verification after fixes:${NC}"
            echo "     • Reload shell: exec zsh"
            echo "     • Run health check again: $0"
            echo ""
        fi

        return 1
    fi
}

# Main execution
main() {
    if [ "$FIX_ISSUES" = true ]; then
        print_header "NixOS Dev Quick Deploy - System Repair"
        echo ""
        echo "Attempting to fix common issues..."
        echo ""

        if fix_shell_environment; then
            record_fix_success "shell environment"
        else
            record_fix_failure "shell environment"
        fi

        if ! command -v home-manager &> /dev/null; then
            if fix_home_manager; then
                record_fix_success "home-manager"
            else
                record_fix_failure "home-manager"
            fi
        fi

        if fix_python_environment; then
            record_fix_success "python environment"
        else
            record_fix_failure "python environment"
        fi

        # Fix Claude Code (native installer)
        local claude_native_bin="$HOME/.local/bin/claude"
        local claude_alt_bin="$HOME/.claude/bin/claude"
        if [ ! -x "$claude_native_bin" ] && [ ! -x "$claude_alt_bin" ] && ! command -v claude >/dev/null 2>&1; then
            if fix_claude_code_native; then
                record_fix_success "claude code"
            else
                record_fix_failure "claude code"
            fi
        fi

        # Fix npm-based AI CLIs
        load_npm_manifest
        local npm_prefix="${NPM_CONFIG_PREFIX:-$HOME/.npm-global}"
        local ai_fix_needed=false
        if [ ${#NPM_AI_PACKAGE_MANIFEST[@]} -gt 0 ]; then
            local entry package version display bin_command wrapper_name extension_id debug_env
            for entry in "${NPM_AI_PACKAGE_MANIFEST[@]}"; do
                IFS='|' read -r package version display bin_command wrapper_name extension_id debug_env <<<"$entry"
                if [ ! -f "$npm_prefix/bin/$wrapper_name" ]; then
                    ai_fix_needed=true
                    break
                fi
            done
        fi

        if [ "$ai_fix_needed" = true ]; then
            if fix_npm_packages; then
                record_fix_success "npm ai packages"
            else
                record_fix_failure "npm ai packages"
            fi
        fi

        # Fix incomplete flake.lock (missing inputs like sops-nix, nix-vscode-extensions)
        local hm_flake_dir="$HOME/.dotfiles/home-manager"
        if [ -f "$hm_flake_dir/flake.nix" ] && [ -f "$hm_flake_dir/flake.lock" ] && command -v jq >/dev/null 2>&1; then
            local declared_inputs locked_inputs
            declared_inputs=$(awk '
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
            ' "$hm_flake_dir/flake.nix" | sort -u)
            locked_inputs=$(jq -r '.nodes.root.inputs // {} | keys[]' "$hm_flake_dir/flake.lock" 2>/dev/null | sort -u)
            local has_missing=false
            while IFS= read -r input_name; do
                [ -z "$input_name" ] && continue
                if ! echo "$locked_inputs" | grep -Fxq "$input_name"; then
                    has_missing=true
                    break
                fi
            done <<< "$declared_inputs"
            if [ "$has_missing" = true ]; then
                print_section "Resolving missing flake.lock entries..."
                local fix_effective_max_jobs
                fix_effective_max_jobs=$(nix show-config 2>/dev/null | awk -F' = ' '/^max-jobs/ {print $2; exit}')
                local -a fix_lock_cmd=(nix flake lock)
                if [[ "$fix_effective_max_jobs" == "0" ]]; then
                    fix_lock_cmd=(env NIX_CONFIG="max-jobs = 1" nix flake lock)
                fi
                if (cd "$hm_flake_dir" && "${fix_lock_cmd[@]}" 2>&1); then
                    print_success "Resolved missing flake input locks"
                    record_fix_success "flake.lock inputs"
                else
                    print_fail "Could not resolve flake.lock — run manually: cd $hm_flake_dir && nix flake lock"
                    record_fix_failure "flake.lock inputs"
                fi
            fi
        fi

        echo ""
        if [ "$FIX_FAILURES" -gt 0 ]; then
            print_warning "Fix summary: $FIX_SUCCESSES succeeded, $FIX_FAILURES failed"
        else
            print_success "Fix summary: $FIX_SUCCESSES succeeded, 0 failed"
        fi
        print_header "Running Health Check After Fixes"
        echo ""
    fi

    run_all_checks
    exit_code=$?
    if [ "$FIX_FAILURES" -gt 0 ]; then
        exit_code=1
    fi

    echo ""
    echo "End time: $(date)"
    echo ""

    exit $exit_code
}

main
