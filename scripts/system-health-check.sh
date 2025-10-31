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
            podman|python3|node|go|cargo|ollama|aider|nvim)
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
    check_command "go" "Go" false
    check_command "cargo" "Rust (cargo)" false
    check_command "ruby" "Ruby" false

    # ==========================================================================
    # Nix Ecosystem
    # ==========================================================================
    print_section "Nix Ecosystem"

    check_command "nix" "Nix package manager" true
    check_command "nix-env" "nix-env" true
    check_command "home-manager" "Home Manager" true

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
    # AI Development Tools
    # ==========================================================================
    print_section "AI Development Tools"

    # Claude Code
    check_file_exists "$HOME/.npm-global/bin/claude-wrapper" "Claude Code wrapper" true
    check_command "claude-wrapper" "Claude Code (in PATH)" true

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
    check_python_package "torch" "PyTorch" false
    check_python_package "tensorflow" "TensorFlow" false

    # LLM & AI Frameworks
    check_python_package "openai" "OpenAI client" false
    check_python_package "anthropic" "Anthropic client" false
    check_python_package "langchain" "LangChain" false
    check_python_package "llama_index" "LlamaIndex" false

    # Vector Databases & Embeddings
    check_python_package "chromadb" "ChromaDB" false
    check_python_package "qdrant_client" "Qdrant client" false
    check_python_package "sentence_transformers" "Sentence Transformers" false
    check_python_package "faiss" "FAISS" false

    # Modern Data Processing
    check_python_package "polars" "Polars (fast DataFrames)" false
    check_python_package "dask" "Dask (parallel computing)" false

    # Code Quality Tools
    check_python_package "black" "Black (formatter)" false
    check_python_package "ruff" "Ruff (linter)" false
    check_python_package "mypy" "Mypy (type checker)" false

    # Jupyter
    check_python_package "jupyterlab" "Jupyter Lab" false
    check_python_package "notebook" "Jupyter Notebook" false

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
    if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "$HOME/.nix-profile/bin/zsh" ]; then
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
    print_section "AI Systemd Services (Optional)"

    # Qdrant vector database
    check_systemd_service "qdrant" "Qdrant (vector database)" false
    if systemctl --user is-active qdrant &> /dev/null; then
        check_systemd_service_port "qdrant" "6333" "Qdrant API"
    fi

    # Hugging Face TGI
    check_systemd_service "huggingface-tgi" "Hugging Face TGI (LLM inference)" false
    if systemctl --user is-active huggingface-tgi &> /dev/null; then
        check_systemd_service_port "huggingface-tgi" "8080" "TGI API"
    fi

    # Jupyter Lab
    check_systemd_service "jupyter-lab" "Jupyter Lab (notebooks)" false
    if systemctl --user is-active jupyter-lab &> /dev/null; then
        check_systemd_service_port "jupyter-lab" "8888" "Jupyter Lab"
    fi

    # Gitea development forge
    check_systemd_service "gitea-dev" "Gitea (development forge)" false

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
            echo "Suggested fixes:"
            echo ""

            if ! command -v home-manager &> /dev/null; then
                echo "  1. Fix home-manager:"
                echo "     $0 --fix"
                echo ""
            fi

            if [ ! -f "$HOME/.npm-global/bin/claude-wrapper" ]; then
                echo "  2. Fix NPM packages:"
                echo "     $0 --fix"
                echo ""
            fi

            echo "  3. Reload shell environment:"
            echo "     source ~/.zshrc"
            echo "     # or"
            echo "     exec zsh"
            echo ""

            echo "  4. Re-apply home-manager configuration:"
            echo "     cd ~/.dotfiles/home-manager"
            echo "     home-manager switch --flake ."
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
