#!/usr/bin/env bash
#
# Phase 08: System Finalization & Deployment Report
# Purpose: Complete post-install configuration and generate comprehensive deployment report
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/finalization.sh → apply_final_system_configuration(), finalize_configuration_activation()
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
# Requires Phases (must complete before this):
#   - Phase 7: VALIDATION_PASSED must be true
#
# Produces (for later phases):
#   - FINALIZATION_COMPLETE → Flag indicating finalization done
#   - SUCCESS_REPORT → Final deployment report
#   - State: "finalization_and_report" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_08_finalization_and_report() {
    # ========================================================================
    # Phase 8: System Finalization & Deployment Report
    # ========================================================================
    # This is the final phase - complete post-install configuration and
    # generate comprehensive deployment report.
    #
    # Part 1: System Finalization (from old Phase 9)
    # - Apply final system configuration requiring services running
    # - Initialize databases (PostgreSQL for Gitea, etc.)
    # - Configure services (Ollama, Qdrant, HuggingFace TGI)
    # - Set up integrations and service-to-service authentication
    # - Finalize permissions on service directories
    # - Reload/restart services with final configs
    # - Enable user services
    # - Clean up temporary files
    #
    # Part 2: Deployment Report (from old Phase 10)
    # - Generate comprehensive post-install report
    # - Display success banner
    # - Show configuration status
    # - List installed components
    # - Provide next steps guide
    # - Show configuration file locations
    # - Display logs and troubleshooting resources
    # ========================================================================

    local phase_name="finalization_and_report"  # State tracking identifier for this phase

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state.json for completion marker
        print_info "Phase 8 already completed (skipping)"
            return 0  # Skip to completion
    fi

    print_section "Phase 8/8: System Finalization & Deployment Report"  # Display phase header
        echo ""

    # ========================================================================
    # PART 1: SYSTEM FINALIZATION
    # ========================================================================

    print_section "Part 1: Final System Configuration"
        echo ""

    # ========================================================================
    # Step 8.1: Apply Final System Configuration
    # ========================================================================
    # Complete system configuration that requires services running:
    # - Database initialization (PostgreSQL databases for Gitea)
    # - Service configuration (Gitea, Ollama, Qdrant, HuggingFace TGI)
    # - Integration setup (service-to-service authentication)
    # - Permission finalization (service directory ownership)
    apply_final_system_configuration  # Complete post-deployment service configuration

    # ========================================================================
    # Step 8.2: Finalize Configuration Activation
    # ========================================================================
    # Ensure all configurations active and services using them:
    # - Reload service configurations (systemctl daemon-reload)
    # - Restart services if needed
    # - Enable user services (systemctl --user enable)
    # - Verify service dependencies
    # - Clean up temporary files
    finalize_configuration_activation  # Activate final configurations and reload services

    echo ""
        print_success "System finalization complete"
    echo ""

    # Clean up temporary swapfile created in Phase 5 (if permanent swap now available)
    if [[ "${TEMP_SWAP_CREATED:-false}" == true && -n "${TEMP_SWAP_FILE:-}" ]]; then  # Temp swap was created
        print_section "Cleaning Up Temporary Swapfile"

        # Get list of all active swap devices
        local -a active_swap_devices=()  # Array to hold swap device paths
            mapfile -t active_swap_devices < <(swapon --show=NAME --noheadings 2>/dev/null || true)  # Query active swap

        # Check if there's swap other than our temporary file
        local has_alternative_swap=false  # Flag for permanent swap detection
            local device  # Loop variable for swap devices
        for device in "${active_swap_devices[@]}"; do  # Iterate through swap devices
            if [[ -n "$device" && "$device" != "$TEMP_SWAP_FILE" ]]; then  # Found non-temp swap
                has_alternative_swap=true  # Permanent swap detected
                    break  # Stop searching
            fi
        done

        # Remove temporary swap if permanent swap is available
        if [[ "$has_alternative_swap" == true ]]; then  # Have permanent swap now
            print_info "Permanent swap detected; removing temporary swapfile $TEMP_SWAP_FILE."
                if sudo swapoff "$TEMP_SWAP_FILE" 2>/dev/null; then  # Deactivate temp swap
                print_success "Temporary swapfile deactivated."
            else  # Deactivation failed
                print_warning "Unable to deactivate temporary swapfile $TEMP_SWAP_FILE automatically."
            fi

            # Delete the temporary swapfile
            if sudo rm -f "$TEMP_SWAP_FILE" 2>/dev/null; then  # Remove file
                print_success "Temporary swapfile removed."
                    unset TEMP_SWAP_CREATED TEMP_SWAP_FILE TEMP_SWAP_SIZE_GB  # Clean up variables
            else  # Deletion failed
                print_warning "Failed to delete $TEMP_SWAP_FILE. Remove manually with: sudo rm -f $TEMP_SWAP_FILE"
            fi
        else  # No permanent swap yet - keep temporary
            print_info "Temporary swapfile $TEMP_SWAP_FILE remains active because no alternative swap device is present. Remove manually once permanent swap is configured: sudo swapoff $TEMP_SWAP_FILE && sudo rm -f $TEMP_SWAP_FILE"
        fi

        echo ""
    fi

    # ========================================================================
    # PART 2: DEPLOYMENT REPORT
    # ========================================================================

    print_section "Part 2: Deployment Report"
        echo ""

    # ========================================================================
    # Step 8.3: Generate Comprehensive Post-Install Report
    # ========================================================================
    # Detailed information about what was installed:
    # - NixOS generation information
    # - Home-manager generation information
    # - Installed package counts
    # - Service status summary
    # - Hardware configuration summary
    print_post_install  # Generate and display comprehensive deployment report

    # ========================================================================
    # Step 8.4: Display Success Banner
    # ========================================================================
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Deployment Complete - All 8 Phases Successful!               ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ========================================================================
    # Step 8.5: Configuration Status Summary
    # ========================================================================
    print_info "Configuration Status:"
    echo -e "  ${GREEN}✓${NC} NixOS system configuration applied"
    echo -e "  ${GREEN}✓${NC} Home-manager user environment active"
    echo -e "  ${GREEN}✓${NC} Flatpak applications installed"
    echo -e "  ${GREEN}✓${NC} Development tools configured"
    echo ""

    # ========================================================================
    # Step 8.6: Installed Components List
    # ========================================================================
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
    # Step 8.7: Next Steps Guide
    # ========================================================================
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""

    echo -e "  ${GREEN}1.${NC} Reload your shell to activate new environment:"
    echo -e "     ${YELLOW}exec zsh${NC}"
    echo ""

    echo -e "  ${GREEN}2.${NC} Verify system services:"
    echo -e "     ${YELLOW}systemctl status ollama qdrant gitea huggingface-tgi${NC}"
    echo ""

    echo -e "  ${GREEN}3.${NC} Check user services:"
    echo -e "     ${YELLOW}systemctl --user status jupyter-lab${NC}"
    echo ""

    echo -e "  ${GREEN}4.${NC} Test Claude Code:"
    echo -e "     ${YELLOW}claude-wrapper --version${NC}"
    echo ""

    echo -e "  ${GREEN}5.${NC} Run health check anytime:"
    echo -e "     ${YELLOW}~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh${NC}"
    echo ""

    # ========================================================================
    # Step 8.8: Reboot Recommendation (Conditional)
    # ========================================================================
    # Recommend reboot if kernel/init system updated
    # Why: Kernel updates require reboot to take effect
    # Check: Compare booted system vs current system symlinks
    if [[ -L "/run/booted-system" && -L "/run/current-system" ]]; then  # Both symlinks exist
        if [[ "$(readlink /run/booted-system)" != "$(readlink /run/current-system)" ]]; then  # Different generations
            echo -e "${YELLOW}⚠ Reboot Recommended:${NC}"  # Kernel/init changed since boot
                echo "  • Kernel/init system updates detected"
            echo "  • Run: ${YELLOW}sudo reboot${NC}"
                echo "  • After reboot, select 'Cosmic' from login screen"
            echo ""
        fi
    fi

    # ========================================================================
    # Step 8.9: Configuration File Locations
    # ========================================================================
    print_info "Configuration Files:"
    echo "  • System: $SYSTEM_CONFIG_FILE"
    echo "  • Home: $HOME_MANAGER_FILE"
    echo "  • Flake: $FLAKE_FILE"
    echo "  • Hardware: $HARDWARE_CONFIG_FILE"
    echo ""

    # ========================================================================
    # Step 8.10: Logs and Troubleshooting Resources
    # ========================================================================
    print_info "Logs & Troubleshooting:"
    echo "  • Deployment log: $LOG_FILE"
    echo "  • State file: $STATE_FILE"
    echo "  • Backup location: $BACKUP_ROOT"
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Final phase complete - entire deployment succeeded!
    # All 8 phases executed successfully
    mark_step_complete "$phase_name"  # Update state.json with completion marker
        print_success "Phase 8: System Finalization & Deployment Report - COMPLETE"
    echo ""

    # ========================================================================
    # Final Success Banner
    # ========================================================================
    # Display celebratory banner for successful deployment
    echo ""
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ NixOS Quick Deploy v$SCRIPT_VERSION completed successfully!${NC}"
        echo -e "${GREEN}✓ Your AIDB development environment is ready!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        echo ""
}

# Execute phase function (called when this script is sourced by main orchestrator)
phase_08_finalization_and_report  # Run finalization and generate deployment report
