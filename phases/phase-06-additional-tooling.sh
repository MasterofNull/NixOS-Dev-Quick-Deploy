#!/usr/bin/env bash
#
# Phase 06: Additional Tooling
# Purpose: Install additional tools (Flatpak, Claude Code, etc.) in parallel
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/tools.sh → install_flatpak_stage(), install_claude_code(), configure_vscodium_for_claude(), install_vscodium_extensions(), install_openskills_tooling()
#   - lib/flake.sh → setup_flake_environment()
#
# Required Variables (from config/variables.sh):
#   - None (tools install to standard locations)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - install_flatpak_stage() → Install Flatpak apps
#   - install_claude_code() → Install Claude Code
#   - configure_vscodium_for_claude() → Configure VSCodium
#   - install_vscodium_extensions() → Install extensions
#   - install_openskills_tooling() → Install OpenSkills
#   - setup_flake_environment() → Setup flake env
#
# Requires Phases (must complete before this):
#   - Phase 6: DEPLOYMENT_COMPLETE must be true
#
# Produces (for later phases):
#   - TOOLS_INSTALLED → Flag indicating tools ready
#   - State: "install_tools_services" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_06_additional_tooling() {
    # ========================================================================
    # Phase 6: Additional Tooling
    # ========================================================================
    # This is the "extras" phase - install additional tools and services
    # that enhance the development environment but aren't part of core NixOS.
    #
    # Why separate phase for these tools:
    # - Not critical for basic system functionality
    # - Can be installed in parallel (saves time)
    # - Failures are non-fatal (system still usable)
    # - Optional components (user can skip)
    # - Sourced from different package managers (Flatpak, npm, custom)
    #
    # Tools installed in this phase:
    # 1. Flatpak Applications
    #    - Slack, Discord, Zoom (communication)
    #    - GIMP, Inkscape (graphics)
    #    - LibreOffice (productivity)
    #    - Sandboxed apps from Flathub
    #
    # 2. Claude Code CLI
    #    - Anthropic's Claude AI assistant
    #    - VSCodium integration
    #    - Development workflow enhancement
    #    - API key configuration
    #
    # 3. OpenSkills Tooling
    #    - Custom development tools
    #    - Project-specific utilities
    #    - Integration scripts
    #
    # 4. Flake Environment
    #    - Development shells
    #    - Project-specific dependencies
    #    - Reproducible dev environments
    #
    # Parallelization strategy:
    # - These installations are independent
    # - Run in background (&) for concurrency
    # - wait for completion before moving on
    # - Faster than sequential: 15 min vs 30 min
    #
    # Error handling:
    # - Failures don't stop deployment
    # - Warnings logged but phase continues
    # - User can manually install failed components later
    # ========================================================================

    local phase_name="install_tools_services"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 6 already completed (skipping)"
        return 0
    fi

    print_section "Phase 6/8: Additional Tooling"
    echo ""

    # ------------------------------------------------------------------------
    # Declarative Prerequisite Validation (jq must already be present)
    # ------------------------------------------------------------------------
    if ! command -v jq >/dev/null 2>&1; then
        print_section "Validating declarative toolchain prerequisites"
        print_warning "jq not detected on PATH. Phase 6 relies on declarative jq availability."

        local health_script="$SCRIPT_DIR/scripts/system-health-check.sh"

        if [ -x "$health_script" ]; then
            print_info "Running system health check before continuing Phase 6..."
            if ! "$health_script" --detailed; then
                print_error "System health check reported issues. Ensure jq is declared in your configuration and rerun the deploy."
                return 1
            fi
        else
            print_error "Unable to locate system health check script at $health_script"
            print_error "Add jq to the declarative package set before rerunning Phase 6."
            return 1
        fi

        if ! command -v jq >/dev/null 2>&1; then
            print_error "jq is still missing after health check. Update configuration.nix/home.nix to include jq declaratively."
            return 1
        fi
    fi

    # ========================================================================
    # Parallel Installation: Flatpak Applications
    # ========================================================================
    # What is Flatpak:
    # - Universal Linux package format (like AppImage, Snap)
    # - Sandboxed applications for security
    # - Distribution-agnostic (works on any Linux)
    # - Repository: Flathub (flathub.org)
    #
    # Why use Flatpak on NixOS:
    # - Some apps not in nixpkgs (proprietary, niche)
    # - Latest versions (nixpkgs stable can be older)
    # - Upstream-maintained (app developers manage updates)
    # - Sandboxing (extra security layer)
    #
    # How Flatpak works:
    # - Runtimes: Base libraries (Freedesktop, GNOME, KDE)
    # - Apps: Reference a runtime, add app-specific files
    # - Sandboxing: Limited filesystem/network access by default
    # - Installation: System-wide (/var/lib/flatpak) or user (~/.local/share/flatpak)
    #
    # Background execution:
    # & (ampersand): Run command in background
    # $!: PID of last background job
    # Purpose: Continue to next installation while this runs
    print_section "Flatpak Application Installation"
    install_flatpak_stage &
    local flatpak_pid=$!  # Save PID to wait for later

    # ========================================================================
    # Parallel Installation: Claude Code CLI
    # ========================================================================
    # What is Claude Code:
    # - Official CLI for Anthropic's Claude AI
    # - Command-line interface for AI assistance
    # - VSCodium/VSCode integration
    # - Code generation, review, documentation
    #
    # Installation steps:
    # 1. install_claude_code():
    #    - Downloads latest Claude CLI binary
    #    - Installs to ~/.local/bin/ or /usr/local/bin/
    #    - Sets up configuration file
    #    - Prompts for API key (or uses existing)
    #
    # 2. configure_vscodium_for_claude():
    #    - Installs Claude extension for VSCodium
    #    - Configures extension settings
    #    - Sets up keybindings
    #    - Enables AI features in editor
    #
    # 3. install_vscodium_extensions():
    #    - Installs complementary extensions
    #    - Language support (Python, Nix, Rust, etc.)
    #    - Productivity tools (GitLens, Prettier, etc.)
    #    - Uses VSCodium's extension API
    #
    # Error handling:
    # - If install_claude_code fails: Skip configuration steps
    # - If configuration fails: Warn but continue (can configure manually)
    # - || print_warning: Show warning if step fails, don't exit
    #
    # Background execution:
    # & at end of compound command: Entire block runs in background
    # local claude_pid=$!: Save PID for later wait
    print_section "Claude Code CLI Installation"
    if install_claude_code; then
        configure_vscodium_for_claude || print_warning "VSCodium configuration had issues"
    else
        print_warning "Claude Code installation skipped due to errors"
    fi &
    local claude_pid=$!  # Save PID

    # ========================================================================
    # Parallel Installation: OpenSkills Tooling
    # ========================================================================
    # What is OpenSkills:
    # - Custom tooling for skills assessment and development
    # - Project-specific utilities
    # - Integration with learning platforms
    # - Custom scripts and automation
    #
    # Installation:
    # - Clones repositories
    # - Installs dependencies
    # - Sets up configuration
    # - Integrates with shell environment
    #
    # Background execution: Same pattern as above
    print_info "Installing OpenSkills tooling..."
    install_openskills_tooling &
    local openskills_pid=$!  # Save PID

    # ========================================================================
    # Synchronization Point: Wait for Parallel Installations
    # ========================================================================
    # Why wait here:
    # - Need all installations complete before next phase
    # - Collect exit codes to detect failures
    # - Provide status feedback to user
    #
    # wait command:
    # - wait PID: Block until process PID completes
    # - Returns: Exit code of the waited process
    # - 0 = success, non-zero = failure
    #
    # Error handling:
    # - || print_warning: If wait returns non-zero (failure), show warning
    # - Don't exit: These are optional, non-critical components
    # - User informed of issues but deployment continues
    #
    # Why separate waits (not wait $pid1 $pid2 $pid3):
    # - Get individual status for each installation
    # - Provide specific feedback per component
    # - Distinguish which installation failed
    print_info "Waiting for parallel installations to complete..."

    # Wait for Flatpak installation
    # If it fails (returns non-zero), show warning but continue
    wait $flatpak_pid || print_warning "Flatpak installation had issues"

    # Wait for Claude Code installation
    wait $claude_pid || print_warning "Claude Code installation had issues"

    # Run VSCodium extension installation as its own group so logs clearly show progress
    print_section "VSCodium Extension Installation"
    if ! install_vscodium_extensions; then
        print_warning "Some VSCodium extensions may not have installed"
    fi

    # Wait for OpenSkills installation
    wait $openskills_pid || print_warning "OpenSkills installation had issues"

    # ========================================================================
    # Flake Environment Setup
    # ========================================================================
    # What is Nix Flakes environment:
    # - Per-project development environments
    # - flake.nix defines exact dependencies
    # - nix develop: Drops into dev shell with all tools
    # - Reproducible across machines
    #
    # Why set up flake environment:
    # - Isolate project dependencies
    # - Multiple projects with different tool versions
    # - Share dev environment setup via git
    # - Quick onboarding for new developers
    #
    # What setup_flake_environment() does:
    # - Creates template flake.nix files
    # - Configures direnv integration (auto-activate on cd)
    # - Sets up common development shells
    # - Configures Nix settings for flakes
    #
    # Non-critical:
    # - System works without flakes
    # - Can set up manually later
    # - Failure doesn't affect core functionality
    # - Just a convenience feature
    #
    # Error handling:
    # - ! inverts exit code (! false = true)
    # - if ! ...: If command fails...
    # - print_warning but continue
    if ! setup_flake_environment; then
        print_warning "Flake environment setup had issues (non-critical)"
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # All additional tools installed (or attempted).
    # System now has full development environment.
    #
    # What's available after this phase:
    # - Flatpak apps (GUI applications)
    # - Claude AI assistance (CLI and editor)
    # - OpenSkills tools (custom utilities)
    # - Flake dev environments (project isolation)
    #
    # State: "install_tools_services" marked complete
    # Next: Phase 8 will validate everything is working
    mark_step_complete "$phase_name"
    print_success "Phase 6: Additional Tooling - COMPLETE"
    echo ""
}

# Execute phase
phase_06_additional_tooling
