#!/usr/bin/env bash
#
# Phase 02: Prerequisite Package Installation
# Purpose: Install ALL packages needed by deployment script FIRST
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/nixos.sh → select_nixos_version(), update_nixos_channels()
#   - lib/packages.sh → ensure_preflight_core_packages(), cleanup_conflicting_home_manager_profile()
#   - lib/home-manager.sh → install_home_manager()
#   - lib/python.sh → ensure_python_runtime()
#
# Required Variables (from config/variables.sh):
#   - PYTHON_BIN → Python interpreter path (array)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - select_nixos_version() → Let user select NixOS version
#   - update_nixos_channels() → Update system channels
#   - ensure_preflight_core_packages() → Install core packages
#   - cleanup_conflicting_home_manager_profile() → Remove conflicts
#   - install_home_manager() → Install home-manager
#   - ensure_python_runtime() → Ensure Python available
#
# Requires Phases (must complete before this):
#   - Phase 1: GPU_TYPE detection needed for package selection
#
# Produces (for later phases):
#   - PREREQUISITES_INSTALLED → Flag indicating prerequisites ready
#   - PYTHON_BIN → Python interpreter path
#   - State: "install_prerequisites" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_02_prerequisites() {
    # ========================================================================
    # Phase 2: Prerequisite Package Installation
    # ========================================================================
    # This phase ensures ALL tools needed for deployment are installed BEFORE
    # we start making system changes. This is the "tool preparation" phase.
    #
    # Why install prerequisites first:
    # 1. Avoid mid-deployment failures due to missing tools
    # 2. Ensure consistent package versions across the deployment
    # 3. Set up home-manager before it manages packages
    # 4. Establish Python runtime for config generation scripts
    #
    # Critical packages installed:
    # - home-manager: User environment manager (alternative to nix-env)
    # - git: Version control (needed for config management)
    # - jq: JSON processor (needed for state file manipulation)
    # - python3: Script runtime (needed for advanced config generation)
    #
    # NixOS package management concepts:
    # - Channel: Package repository (like unstable, 24.05, etc.)
    # - Binary cache: Pre-compiled packages from cache.nixos.org
    # - nix-env: Imperative package management (user profile)
    # - home-manager: Declarative user environment management
    # ========================================================================

    local phase_name="install_prerequisites"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    # Same resume logic as Phase 1 - check state.json for completion
    if is_step_complete "$phase_name"; then
        print_info "Phase 2 already completed (skipping)"
        return 0
    fi

    print_section "Phase 2/10: Prerequisite Package Installation"
    echo ""

    # ========================================================================
    # Step 2.1: NixOS Version Selection
    # ========================================================================
    # Why: User can choose which NixOS version to use:
    #      - stable: Latest stable release (e.g., 24.05) - fewer bugs, tested
    #      - unstable: Rolling release - newest packages, more features
    # How: select_nixos_version() prompts user for preference
    # Sets: NIXOS_CHANNEL variable (used for package installation)
    #
    # NixOS versioning:
    # - Stable: Released every 6 months (YY.MM format: 24.05, 24.11)
    # - Unstable: Tracks nixpkgs master branch, updated continuously
    # - Old stable: Previous releases (23.11, 23.05, etc.)
    #
    # Why choose unstable: Newer packages, experimental features, COSMIC desktop
    # Why choose stable: Production systems, stability, long-term support
    select_nixos_version

    # ========================================================================
    # Step 2.2: Update NixOS Channels
    # ========================================================================
    # Why: Ensure we have the latest package definitions and security updates
    # How: update_nixos_channels() runs:
    #      1. sudo nix-channel --update nixos (system channel)
    #      2. nix-channel --update (user channel)
    # What: Downloads package metadata from cache.nixos.org
    #
    # NixOS channel concept:
    # - Channel = Git branch + package metadata + binary cache
    # - System channel: /nix/var/nix/profiles/per-user/root/channels/nixos
    # - User channel: ~/.nix-defexpr/channels/
    # - Update: Fetch latest package list (doesn't install/upgrade yet)
    #
    # Why update both: System and user packages come from different channels
    # Time: Can take 30-60 seconds to download channel metadata
    update_nixos_channels

    # ========================================================================
    # Step 2.3: Install Core Prerequisite Packages
    # ========================================================================
    # Why: Install essential tools needed by later phases
    # How: ensure_preflight_core_packages() installs:
    #      - git: Version control (config management, home-manager)
    #      - jq: JSON parsing (state file manipulation)
    #      - curl/wget: File downloads
    #      - gnupg: GPG for package signing verification
    # Method: Uses nix-env for immediate availability
    #
    # nix-env vs nixos configuration:
    # - nix-env: Imperative install (like apt-get) - immediate
    # - configuration.nix: Declarative install - requires rebuild
    # We use nix-env here because we need these tools NOW to continue deployment
    #
    # Why fail here: Without these tools, later phases cannot function
    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
        exit 1
    fi

    # ========================================================================
    # Step 2.4: Cleanup Conflicting Home-Manager Profiles
    # ========================================================================
    # Why: Legacy home-manager installations can conflict with new install
    # How: cleanup_conflicting_home_manager_profile() scans nix profile:
    #      1. Lists all installed packages (nix profile list)
    #      2. Finds old home-manager entries
    #      3. Removes conflicting versions
    # What: Prevents "multiple home-manager versions" error
    #
    # Home-manager installation methods:
    # - Via nix-env: Old method, imperative
    # - Via channel: Recommended, declarative
    # - Via flake: Modern, reproducible
    # This step removes old nix-env installations
    #
    # Why important: Can't have both imperative and declarative home-manager
    # Safe: Only removes home-manager itself, not managed packages
    print_info "Scanning nix profile for legacy home-manager entries..."
    cleanup_conflicting_home_manager_profile

    # ========================================================================
    # Step 2.5: Ensure Home-Manager is Available
    # ========================================================================
    # Why: home-manager manages user environment (dotfiles, packages, services)
    # How: Check if 'home-manager' command exists in PATH
    # If not found: install_home_manager() installs it
    # If found: Verify it's working with $(which home-manager)
    #
    # What is home-manager:
    # - User-level package manager (alternative to nix-env)
    # - Manages dotfiles (.bashrc, .zshrc, .config/*)
    # - Manages user services (systemd --user)
    # - Declarative configuration (home.nix file)
    # - Rollback capability (like NixOS generations)
    #
    # Why use home-manager:
    # - Declarative: All user config in one file
    # - Reproducible: Same config on multiple machines
    # - Versioned: Track config changes in git
    # - Atomic: Changes applied all-at-once
    #
    # command -v: Returns path if command exists, empty if not
    if command -v home-manager &>/dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        install_home_manager
    fi

    # ========================================================================
    # Step 2.6: Verify Python Runtime Available
    # ========================================================================
    # Why: Some configuration generation scripts are written in Python
    # How: ensure_python_runtime() tries multiple methods:
    #      1. Check for system python3
    #      2. Check user profile python
    #      3. Create ephemeral Nix shell with python
    # Sets: PYTHON_BIN array with python command
    #
    # Why Python needed:
    # - Advanced NixOS config generation (complex templating)
    # - Hardware detection scripts
    # - JSON/YAML configuration processing
    # - Integration with external APIs
    #
    # Python installation methods:
    # - System python: In NixOS configuration.nix
    # - User python: Via home-manager or nix-env
    # - Ephemeral: nix-shell -p python3 --run "python script.py"
    # We prefer system/user for speed, ephemeral as fallback
    #
    # PYTHON_BIN array format:
    # - Direct: ["python3"] or ["/usr/bin/python3"]
    # - Ephemeral: ["nix", "shell", "nixpkgs#python3", "-c", "python3"]
    print_info "Verifying Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        exit 1
    fi

    # Display Python runtime information for user
    # ${PYTHON_BIN[0]}: First element of array (command or "nix")
    # ${PYTHON_BIN[@]}: All elements of array
    # $(command): Command substitution - run command and capture output
    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        # Ephemeral Nix shell - will invoke python via nix-shell each time
        print_success "Python runtime: ephemeral Nix shell"
    else
        # Direct python binary - faster execution
        # 2>&1: Redirect stderr to stdout (python --version prints to stderr)
        print_success "Python runtime: ${PYTHON_BIN[0]} ($(${PYTHON_BIN[@]} --version 2>&1))"
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # All prerequisites installed and verified.
    # State file now records: "install_prerequisites" complete
    # Later phases can safely assume these tools are available
    mark_step_complete "$phase_name"
    print_success "Phase 2: Prerequisite Package Installation - COMPLETE"
    echo ""
}

# Execute phase
phase_02_prerequisites
