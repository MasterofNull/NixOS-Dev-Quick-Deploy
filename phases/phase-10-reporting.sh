#!/usr/bin/env bash
#
# Phase 10: Success Report & Next Steps
# Purpose: Comprehensive deployment report with detailed next steps
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/reporting.sh → print_post_install()
#
# Required Variables (from config/variables.sh):
#   - SCRIPT_VERSION → Current script version
#   - SYSTEM_CONFIG_FILE → Path to system config
#   - HOME_MANAGER_FILE → Path to home-manager config
#   - FLAKE_FILE → Path to flake config
#   - HARDWARE_CONFIG_FILE → Path to hardware config
#   - LOG_FILE → Path to deployment log
#   - STATE_FILE → Path to state file
#   - BACKUP_ROOT → Path to backup directory
#   - GREEN, NC, BLUE, YELLOW → Color codes
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - print_post_install() → Print post-install info
#
# Requires Phases (must complete before this):
#   - Phase 9: ALL_PHASES_COMPLETE (1-9)
#
# Produces (for later phases):
#   - SUCCESS_REPORT → Final deployment report
#   - State: "success_report" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_10_reporting() {
    # ========================================================================
    # Phase 10: Success Report & Next Steps
    # ========================================================================
    # This is the final phase - generate comprehensive deployment report
    # and provide user with clear next steps.
    #
    # Why a dedicated reporting phase:
    # - Provide clear feedback on what was deployed
    # - Guide user on how to use the new system
    # - Document configuration file locations
    # - Highlight important next actions
    # - Create audit trail of deployment
    #
    # Report components:
    # 1. Success confirmation with visual emphasis
    # 2. Configuration status summary
    # 3. Installed components list
    # 4. Next steps for user
    # 5. Reboot recommendation (if needed)
    # 6. Configuration file locations
    # 7. Logs and troubleshooting resources
    #
    # This phase is read-only:
    # - No system changes
    # - Only generates report
    # - Safe to run multiple times
    # ========================================================================

    local phase_name="success_report"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 10 already completed (skipping)"
        return 0
    fi

    print_section "Phase 10/10: Success Report & Next Steps"
    echo ""

    # ========================================================================
    # Step 10.1: Generate Comprehensive Post-Install Report
    # ========================================================================
    # Why: Provide detailed information about what was installed
    # How: print_post_install() generates formatted report including:
    #      - NixOS generation information
    #      - Home-manager generation information
    #      - Installed package counts
    #      - Service status summary
    #      - Hardware configuration summary
    #      - Network configuration details
    #
    # Report contents:
    # - Current vs previous generations (shows what changed)
    # - Package diff (what was added/removed)
    # - Service changes (what started/stopped)
    # - Disk usage changes (how much space used)
    #
    # Why comprehensive report:
    # - Audit trail for what happened
    # - Troubleshooting reference
    # - Documentation for team members
    # - Rollback reference (what to expect if rolling back)
    print_post_install

    # ========================================================================
    # Step 10.2: Display Success Banner
    # ========================================================================
    # Why: Visual confirmation of successful deployment
    # How: Box-drawing characters create prominent visual element
    # Purpose: User clearly sees deployment succeeded
    #
    # Color codes explained:
    # - ${GREEN}: ANSI escape code for green text
    # - ${NC}: "No Color" - reset to default
    # - echo -e: Enable interpretation of backslash escapes
    #
    # Box-drawing characters:
    # - ╔═╗: Top of box (Unicode box-drawing)
    # - ║: Vertical sides
    # - ╚═╝: Bottom of box
    #
    # Why use box-drawing:
    # - Visually distinctive
    # - Hard to miss
    # - Indicates completion clearly
    # - Professional appearance
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Deployment Complete - All 10 Phases Successful!              ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ========================================================================
    # Step 10.3: Configuration Status Summary
    # ========================================================================
    # Why: Confirm all major configuration components applied
    # What: Show checkmarks for each successful component
    #
    # Components shown:
    # - NixOS system configuration: Kernel, drivers, system services
    # - Home-manager environment: User packages, dotfiles
    # - Flatpak applications: GUI apps from Flathub
    # - Development tools: CLI tools, editors, build tools
    #
    # Checkmark symbol:
    # - ${GREEN}✓${NC}: Green checkmark (Unicode U+2713)
    # - Visually indicates success
    # - Standard "done" symbol
    print_info "Configuration Status:"
    echo -e "  ${GREEN}✓${NC} NixOS system configuration applied"
    echo -e "  ${GREEN}✓${NC} Home-manager user environment active"
    echo -e "  ${GREEN}✓${NC} Flatpak applications installed"
    echo -e "  ${GREEN}✓${NC} Development tools configured"
    echo ""

    # ========================================================================
    # Step 10.4: Installed Components List
    # ========================================================================
    # Why: Show user what's available on their system
    # What: High-level summary of major components
    #
    # Components listed:
    # - Desktop: COSMIC Desktop Environment (modern, Rust-based)
    # - Containers: Podman (Docker alternative, rootless capable)
    # - Database: PostgreSQL (relational database)
    # - AI/ML: Python environment with ML libraries
    # - CLI tools: 100+ development utilities
    # - AI integration: Claude Code for AI-assisted development
    # - Services: Gitea, Qdrant, Ollama, TGI (AI/ML services)
    #
    # Bullet points (•): Unicode U+2022, better than asterisks
    print_info "Installed Components:"
    echo "  • COSMIC Desktop Environment"
    echo "  • Podman container runtime"
    echo "  • PostgreSQL database"
    echo "  • Python AI/ML environment"
    echo "  • Development CLI tools (100+)"
    echo "  • Claude Code integration"
    echo "  • System services (Gitea, Qdrant, Ollama, TGI)"
    echo ""

    # ========================================================================
    # Step 10.5: Next Steps Guide
    # ========================================================================
    # Why: User needs clear guidance on what to do now
    # What: Numbered list of immediate actions
    #
    # Color scheme:
    # - ${BLUE}: Section headers (visual grouping)
    # - ${GREEN}: Step numbers (positive, progress)
    # - ${YELLOW}: Commands to run (attention, actionable)
    # - ${NC}: Reset color
    #
    # Step-by-step approach:
    # - Numbered for clear sequence
    # - Actionable commands (copy-paste ready)
    # - Explanations of what each command does
    # - Priority order (most important first)
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""

    # Step 1: Reload shell
    # Why: home-manager modified shell config but current shell hasn't reloaded
    # exec: Replace current shell process with new one
    # zsh: User's shell (could be bash, fish, etc.)
    # Result: New shell picks up new PATH, aliases, environment variables
    echo -e "  ${GREEN}1.${NC} Reload your shell to activate new environment:"
    echo -e "     ${YELLOW}exec zsh${NC}"
    echo ""

    # Step 2: Verify system services
    # Why: Ensure critical services started successfully
    # systemctl status: Show service status
    # Multiple services: Check all major services at once
    # Services listed: AI/ML infrastructure components
    echo -e "  ${GREEN}2.${NC} Verify system services:"
    echo -e "     ${YELLOW}systemctl status ollama qdrant gitea huggingface-tgi${NC}"
    echo ""

    # Step 3: Check user services
    # Why: Verify user-level services running
    # systemctl --user: User session services (not system services)
    # jupyter-lab: Interactive Python notebook server
    echo -e "  ${GREEN}3.${NC} Check user services:"
    echo -e "     ${YELLOW}systemctl --user status jupyter-lab${NC}"
    echo ""

    # Step 4: Test Claude Code
    # Why: Verify AI assistant integration working
    # claude-wrapper: Shell wrapper for Claude CLI
    # --version: Quick test that command exists and works
    echo -e "  ${GREEN}4.${NC} Test Claude Code:"
    echo -e "     ${YELLOW}claude-wrapper --version${NC}"
    echo ""

    # Step 5: Health check script
    # Why: Comprehensive system validation on demand
    # Location: Deployment script directory
    # Tilde (~): User home directory shorthand
    echo -e "  ${GREEN}5.${NC} Run health check anytime:"
    echo -e "     ${YELLOW}~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh${NC}"
    echo ""

    # ========================================================================
    # Step 10.6: Reboot Recommendation (Conditional)
    # ========================================================================
    # Why: Some changes require reboot (kernel, init system)
    # How: Compare booted system to current system
    # When: Only if they differ (updates require reboot)
    #
    # /run/booted-system: Symlink to system booted with
    # /run/current-system: Symlink to currently active system
    # readlink: Follow symlink to see actual path
    #
    # Why recommend reboot:
    # - Kernel updates need reboot
    # - systemd updates might need reboot
    # - Hardware driver changes safer with reboot
    # - Ensures clean state
    #
    # Condition breakdown:
    # - [[ -L ... ]]: Check if symlink exists
    # - &&: AND operator (both must be true)
    # - != : Not equal
    # - "$(readlink ...)": Get target of symlink
    if [[ -L "/run/booted-system" && -L "/run/current-system" ]]; then
        if [[ "$(readlink /run/booted-system)" != "$(readlink /run/current-system)" ]]; then
            echo -e "${YELLOW}⚠ Reboot Recommended:${NC}"
            echo "  • Kernel/init system updates detected"
            echo "  • Run: ${YELLOW}sudo reboot${NC}"
            echo "  • After reboot, select 'Cosmic' from login screen"
            echo ""
        fi
    fi

    # ========================================================================
    # Step 10.7: Configuration File Locations
    # ========================================================================
    # Why: User needs to know where to edit configs
    # What: Paths to all generated configuration files
    #
    # Variables explained:
    # - $SYSTEM_CONFIG_FILE: /etc/nixos/configuration.nix
    # - $HOME_MANAGER_FILE: ~/.config/home-manager/home.nix
    # - $FLAKE_FILE: ~/.config/home-manager/flake.nix
    # - $HARDWARE_CONFIG_FILE: /etc/nixos/hardware-configuration.nix
    #
    # Why show these:
    # - User will edit these for future changes
    # - Reference for troubleshooting
    # - Version control these files
    # - Share configs across machines
    print_info "Configuration Files:"
    echo "  • System: $SYSTEM_CONFIG_FILE"
    echo "  • Home: $HOME_MANAGER_FILE"
    echo "  • Flake: $FLAKE_FILE"
    echo "  • Hardware: $HARDWARE_CONFIG_FILE"
    echo ""

    # ========================================================================
    # Step 10.8: Logs and Troubleshooting Resources
    # ========================================================================
    # Why: User needs references for troubleshooting
    # What: Locations of logs, state, and backups
    #
    # Resources provided:
    # - Deployment log: Complete record of deployment
    # - State file: Resume/rollback information
    # - Backup location: Pre-deployment backups
    #
    # Variables explained:
    # - $LOG_FILE: ~/.config/nixos-quick-deploy/logs/deploy-TIMESTAMP.log
    # - $STATE_FILE: ~/.config/nixos-quick-deploy/state.json
    # - $BACKUP_ROOT: ~/.config/nixos-quick-deploy/backups/
    #
    # Why show these:
    # - Troubleshooting failed services
    # - Understanding what happened
    # - Rollback if needed
    # - Bug reports need logs
    print_info "Logs & Troubleshooting:"
    echo "  • Deployment log: $LOG_FILE"
    echo "  • State file: $STATE_FILE"
    echo "  • Backup location: $BACKUP_ROOT"
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # This is the final phase - mark as complete
    mark_step_complete "$phase_name"
    print_success "Phase 10: Success Report & Next Steps - COMPLETE"
    echo ""

    # ========================================================================
    # Final Success Banner
    # ========================================================================
    # Why: Emphatic conclusion to deployment
    # What: Version number and project confirmation
    #
    # Double-box separator (════): Strong visual delimiter
    # Checkmarks: Reinforce success
    # Project name: Confirm what was deployed
    #
    # $SCRIPT_VERSION: Current version of deployment script
    # Shows user which version they're running
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ NixOS Quick Deploy v$SCRIPT_VERSION completed successfully!${NC}"
    echo -e "${GREEN}✓ Your AIDB development environment is ready!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Execute phase
phase_10_reporting
