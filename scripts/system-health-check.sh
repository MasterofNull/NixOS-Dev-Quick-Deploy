#!/usr/bin/env bash
# =============================================================================
# NixOS Dev Quick Deploy - System Health Check
# =============================================================================
# This script verifies that all packages and configurations were installed
# correctly and are accessible in your environment.
#
# Usage:
#   ./system-health-check.sh [--detailed] [--fix]
#
# Options:
#   --detailed    Show detailed output for all checks
#   --fix         Attempt to fix common issues automatically
# =============================================================================

set -uo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Options
DETAILED=false
FIX_ISSUES=false

# Parse arguments
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

# Logging functions
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

    # Reload shell config
    if [ -f "$HOME/.zshrc" ]; then
        print_detail "Reloading ZSH configuration"
        source "$HOME/.zshrc" 2>/dev/null || true
        print_success "Reloaded ZSH configuration"
    fi
}

fix_home_manager() {
    print_section "Attempting to fix home-manager..."

    if [ -d "$HOME/.dotfiles/home-manager" ]; then
        print_detail "Found home-manager configuration at ~/.dotfiles/home-manager"
        cd "$HOME/.dotfiles/home-manager"

        print_detail "Running: home-manager switch --flake ."
        if home-manager switch --flake . 2>&1 | tee /tmp/hm-fix.log; then
            print_success "Successfully applied home-manager configuration"
            fix_shell_environment
        else
            print_fail "Failed to apply home-manager configuration"
            echo "  See /tmp/hm-fix.log for details"
        fi
    else
        print_fail "home-manager configuration not found at ~/.dotfiles/home-manager"
    fi
}

fix_npm_packages() {
    print_section "Attempting to fix NPM packages..."

    # Ensure NPM prefix is set
    export NPM_CONFIG_PREFIX="$HOME/.npm-global"

    # Create directories
    mkdir -p "$HOME/.npm-global/bin"
    mkdir -p "$HOME/.npm-global/lib"

    # Check npmrc
    if ! grep -q "prefix=" "$HOME/.npmrc" 2>/dev/null; then
        print_detail "Creating ~/.npmrc with correct prefix"
        echo "prefix=$HOME/.npm-global" > "$HOME/.npmrc"
        print_success "Created ~/.npmrc"
    fi

    # Reinstall Claude Code
    print_detail "Reinstalling @anthropic-ai/claude-code"
    if npm install -g @anthropic-ai/claude-code 2>&1 | tee /tmp/npm-fix.log; then
        print_success "Reinstalled Claude Code npm package"

        # Recreate wrapper if needed
        if [ ! -f "$HOME/.npm-global/bin/claude-wrapper" ] || [ ! -x "$HOME/.npm-global/bin/claude-wrapper" ]; then
            print_detail "Creating claude-wrapper script"
            cat > "$HOME/.npm-global/bin/claude-wrapper" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Smart Claude Code Wrapper - Finds Node.js dynamically
set -euo pipefail

# Try common Nix profile locations
NODE_LOCATIONS=(
    "$HOME/.nix-profile/bin/node"
    "/run/current-system/sw/bin/node"
    "/nix/var/nix/profiles/default/bin/node"
)

NODE_BIN=""
for node_path in "${NODE_LOCATIONS[@]}"; do
    if [ -n "$node_path" ] && [ -x "$node_path" ]; then
        NODE_BIN="$node_path"
        break
    fi
done

# Fallback to system PATH
if [ -z "$NODE_BIN" ] && command -v node &> /dev/null; then
    NODE_BIN=$(command -v node)
fi

if [ -z "$NODE_BIN" ]; then
    echo "ERROR: Node.js not found" >&2
    echo "Install Node.js with: home-manager switch --flake ~/.dotfiles/home-manager" >&2
    exit 127
fi

# Path to Claude Code CLI
CLAUDE_CLI="$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"

if [ ! -f "$CLAUDE_CLI" ]; then
    echo "ERROR: Claude Code CLI not found at $CLAUDE_CLI" >&2
    echo "Install with: npm install -g @anthropic-ai/claude-code" >&2
    exit 127
fi

# Execute with Node.js
exec "$NODE_BIN" "$CLAUDE_CLI" "$@"
WRAPPER_EOF
            chmod +x "$HOME/.npm-global/bin/claude-wrapper"
            print_success "Created claude-wrapper"
        fi
    else
        print_fail "Failed to reinstall Claude Code"
        echo "  See /tmp/npm-fix.log for details"
    fi
}

# Check functions
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
            podman|python3|node|cargo|ollama|aider|nvim)
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

check_nix_channel() {
    local profile=$1
    local alias=$2
    local expected=$3
    local description=$4

    print_check "$description"

    local list_output=""
    if [ -n "$profile" ]; then
        if ! list_output=$(nix-channel --list --profile "$profile" 2>/dev/null); then
            print_warning "Unable to query $alias channel (permission denied or profile missing)"
            return 1
        fi
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

    if flatpak info --user "$app_id" &> /dev/null; then
        local version=$(flatpak info --user "$app_id" | grep "Version:" | awk '{print $2}')
        print_success "$app_name (v$version)"
        print_detail "App ID: $app_id"
        return 0
    else
        if [ "$required" = true ]; then
            print_fail "$app_name not installed"
            return 1
        else
            print_warning "$app_name not installed (optional)"
            return 2
        fi
    fi
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

    local remote_output
    remote_output=$(flatpak remotes --user --columns=name,url 2>/dev/null || true)
    local remote_line
    remote_line=$(printf '%s\n' "$remote_output" | awk -v name="$remote_name" 'NR == 1 {next} $1 == name {print $0}' | head -n1)

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

    print_check "Python: $description"

    if python3 -c "import $package" &> /dev/null; then
        # Try to get version
        local version=$(python3 -c "import $package; print(getattr($package, '__version__', 'installed'))" 2>/dev/null || echo "installed")
        print_success "$description ($version)"
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

check_systemd_service() {
    local service=$1
    local description=$2
    local check_running=${3:-false}

    print_check "$description"

    # Check if service unit exists
    if ! systemctl --user list-unit-files | grep -q "^${service}.service"; then
        print_fail "$description service not configured"
        return 1
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

    print_check "$description"

    # Check if service unit exists (system-level)
    if ! systemctl list-unit-files | grep -q "^${service}.service"; then
        print_fail "$description service not configured"
        return 1
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
    else
        if [ "$check_running" = true ]; then
            print_fail "$description (not running, $enabled)"
            print_detail "Check logs: journalctl -u $service"
            print_detail "Start with: sudo systemctl start $service"
        else
            print_success "$description (configured, $enabled)"
            print_detail "Enable with: sudo systemctl enable --now $service"
        fi
        return 2
    fi
}

check_systemd_service_port() {
    local service=$1
    local port=$2
    local description=$3

    # Only check port if service is running
    if systemctl --user is-active "$service" &> /dev/null; then
        if curl -s "http://localhost:$port" &> /dev/null || nc -z localhost "$port" 2>/dev/null; then
            print_detail "Service accessible on port $port"
            return 0
        else
            print_detail "Service running but port $port not accessible"
            return 1
        fi
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

    # ==========================================================================
    # Core System Tools
    # ==========================================================================
    print_section "Core System Tools"

    check_command "podman" "Podman" true
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
            print_detail "May need to run: home-manager switch --flake ~/.dotfiles/home-manager"
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

    check_nix_channel "/nix/var/nix/profiles/per-user/root/channels" "nixos" "nixos-unstable" "System nixos channel"
    check_nix_channel "" "nixpkgs" "nixos-unstable" "User nixpkgs channel"
    check_nix_channel "" "home-manager" "master" "Home Manager channel"

    # ==========================================================================
    # AI Development Tools
    # ==========================================================================
    print_section "AI Development Tools"

    # Claude Code - comprehensive check
    print_check "Claude Code installation"
    if [ -f "$HOME/.npm-global/bin/claude-wrapper" ]; then
        if command -v claude-wrapper &> /dev/null; then
            print_success "Claude Code (wrapper and PATH configured)"
            print_detail "Wrapper: $HOME/.npm-global/bin/claude-wrapper"
            print_detail "In PATH: $(which claude-wrapper)"
        else
            print_warning "Claude Code wrapper exists but not in PATH"
            print_detail "Wrapper: $HOME/.npm-global/bin/claude-wrapper"
            print_detail "Add to PATH: export PATH=\"\$HOME/.npm-global/bin:\$PATH\""
            ((WARNING_CHECKS++))
        fi
        ((TOTAL_CHECKS++))
    else
        print_fail "Claude Code wrapper not found"
        print_detail "Expected at: $HOME/.npm-global/bin/claude-wrapper"
        print_detail "Install with: npm install -g @anthropic-ai/claude-code"
        ((FAILED_CHECKS++))
        ((TOTAL_CHECKS++))
    fi

    # Check underlying npm package
    print_check "Claude Code npm package"
    if [ -f "$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js" ]; then
        local pkg_version=$(node -e "console.log(require('$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/package.json').version)" 2>/dev/null || echo "unknown")
        print_success "Claude Code npm package (v$pkg_version)"
        print_detail "Location: $HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code"
    else
        print_fail "Claude Code npm package not found"
        print_detail "Install with: npm install -g @anthropic-ai/claude-code"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Other AI tools
    check_command "ollama" "Ollama" true
    check_command "aider" "Aider" true

    # ==========================================================================
    # Python AI/ML Packages
    # ==========================================================================
    print_section "Python AI/ML Packages"

    # Core Data Science
    check_python_package "pandas" "Pandas (DataFrames)" true
    check_python_package "numpy" "NumPy (numerical computing)" true
    check_python_package "sklearn" "Scikit-learn (machine learning)" true

    # Deep Learning Frameworks
    check_python_package "torch" "PyTorch" true
    check_python_package "tensorflow" "TensorFlow" false

    # LLM & AI Frameworks
    check_python_package "openai" "OpenAI client" true
    check_python_package "anthropic" "Anthropic client" true
    check_python_package "langchain" "LangChain" true
    check_python_package "llama_index" "LlamaIndex" true
    check_python_package "openskills" "OpenSkills automation toolkit" true

    # Vector Databases & Embeddings
    check_python_package "chromadb" "ChromaDB" true
    check_python_package "qdrant_client" "Qdrant client" true
    check_python_package "sentence_transformers" "Sentence Transformers" true
    check_python_package "faiss" "FAISS" false

    # Modern Data Processing
    check_python_package "polars" "Polars (fast DataFrames)" true
    check_python_package "dask" "Dask (parallel computing)" false

    # Code Quality Tools
    check_python_package "black" "Black (formatter)" true
    check_python_package "ruff" "Ruff (linter)" true
    check_python_package "mypy" "Mypy (type checker)" true

    # Jupyter
    check_python_package "jupyterlab" "Jupyter Lab" true
    check_python_package "notebook" "Jupyter Notebook" false

    # Additional AI/ML packages
    check_python_package "transformers" "Transformers (Hugging Face)" true
    check_python_package "accelerate" "Accelerate" true
    check_python_package "datasets" "Datasets (Hugging Face)" true
    check_python_package "gradio" "Gradio" true

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
        local runtime_count=$(flatpak list --user --runtime 2>/dev/null | grep -c "org.freedesktop.Platform" || echo "0")
        if [ "$runtime_count" -gt 4 ]; then
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
    # AI Systemd Services
    # ==========================================================================
    print_section "AI Systemd Services"

    # Qdrant vector database (system service)
    # These services are disabled by default to prevent startup issues during deployment
    check_system_service "qdrant" "Qdrant (vector database)" false
    if systemctl is-active qdrant &> /dev/null; then
        if curl -s "http://localhost:6333" &> /dev/null || nc -z localhost 6333 2>/dev/null; then
            print_detail "Qdrant API accessible on port 6333"
        fi
    fi

    # Hugging Face TGI (system service)
    check_system_service "huggingface-tgi" "Hugging Face TGI (LLM inference)" false
    if systemctl is-active huggingface-tgi &> /dev/null; then
        if curl -s "http://localhost:8080" &> /dev/null || nc -z localhost 8080 2>/dev/null; then
            print_detail "TGI API accessible on port 8080"
        fi
    fi

    # Jupyter Lab (user service)
    check_systemd_service "jupyter-lab" "Jupyter Lab (notebooks)" false
    if systemctl --user is-active jupyter-lab &> /dev/null; then
        check_systemd_service_port "jupyter-lab" "8888" "Jupyter Lab"
    fi

    # Gitea development forge (system service)
    check_system_service "gitea" "Gitea (development forge)" true

    # ==========================================================================
    # Network Services
    # ==========================================================================
    print_section "Network Services (Optional)"

    # Check if Ollama is running
    print_check "Ollama service"
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_success "Ollama service running"
        print_detail "URL: http://localhost:11434"
    else
        print_warning "Ollama service not running"
        print_detail "Start with: systemctl --user start ollama"
    fi

    # ==========================================================================
    # Nix Store & Profile Health
    # ==========================================================================
    print_section "Nix Store & Profile Health"

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
            if ! command -v home-manager &> /dev/null; then
                echo "  ${YELLOW}1. Home Manager not in PATH:${NC}"
                echo "     • Source session variables:"
                echo "       source ~/.nix-profile/etc/profile.d/hm-session-vars.sh"
                echo "     • Then reload shell:"
                echo "       exec zsh"
                echo "     • If still missing, re-apply home-manager:"
                echo "       cd ~/.dotfiles/home-manager"
                echo "       nix run home-manager/master -- switch --flake ."
                echo ""
            fi

            if [ ! -f "$HOME/.npm-global/bin/claude-wrapper" ]; then
                echo "  ${YELLOW}2. Claude Code not installed:${NC}"
                echo "     • Install via NPM:"
                echo "       export NPM_CONFIG_PREFIX=~/.npm-global"
                echo "       npm install -g @anthropic-ai/claude-code"
                echo "     • Or use auto-fix:"
                echo "       $0 --fix"
                echo ""
            fi

            if ! python3 -c "import torch" &> /dev/null || \
               ! python3 -c "import pandas" &> /dev/null || \
               ! python3 -c "import anthropic" &> /dev/null; then
                echo "  ${YELLOW}3. Python packages missing:${NC}"
                echo "     • These should be installed via home-manager"
                echo "     • If home-manager was just applied, reload your shell:"
                echo "       exec zsh"
                echo "     • If still missing, check if packages built successfully:"
                echo "       nix-store --verify-path ~/.nix-profile"
                echo "     • Re-apply home-manager to rebuild Python environment:"
                echo "       cd ~/.dotfiles/home-manager && home-manager switch --flake ."
                echo ""
            fi

            echo "  ${YELLOW}Quick fix (attempts all repairs automatically):${NC}"
            echo "     $0 --fix"
            echo ""

            echo "  ${YELLOW}Manual verification after fixes:${NC}"
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

        fix_shell_environment

        if ! command -v home-manager &> /dev/null; then
            fix_home_manager
        fi

        if [ ! -f "$HOME/.npm-global/bin/claude-wrapper" ]; then
            fix_npm_packages
        fi

        echo ""
        print_header "Running Health Check After Fixes"
        echo ""
    fi

    run_all_checks
    exit_code=$?

    echo ""
    echo "End time: $(date)"
    echo ""

    exit $exit_code
}

main
