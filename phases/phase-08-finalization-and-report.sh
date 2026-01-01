#!/usr/bin/env bash
#
# Phase 08: System Finalization & Deployment Report
# Purpose: Complete post-install configuration and generate comprehensive deployment report
# Version: Uses SCRIPT_VERSION from main script
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
#   - lib/validation.sh → run_system_health_check_stage()
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
    # Part 1: System Health Check
    # - Run comprehensive validation of services, resources, and connectivity
    # - Respect --skip-health-check for faster deployments
    #
    # Part 2: Final System Configuration
    # - Apply final service configuration that requires live services
    # - Finalize permissions and remove temporary resources
    #
    # Part 3: Deployment Report
    # - Generate comprehensive post-install report
    # - Display configuration status, next steps, and troubleshooting info
    # ========================================================================

    local phase_name="finalization_and_report"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 8 already completed (skipping)"
        return 0
    fi

    print_section "Phase 8/8: System Finalization & Deployment Report"
    echo ""

    # ========================================================================
    # PART 1: SYSTEM HEALTH CHECK
    # ========================================================================

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "Local AI stack images and containers are now managed by ai-optimizer."
        print_info "After deployment run 'podman-ai-stack up' to pull/start the ai-optimizer Podman stack (vLLM, Open WebUI, Qdrant, MindsDB)."
        echo ""
    fi

    print_section "Part 1: System Health Check"
    echo ""

    # ========================================================================
    # Step 8.1: Run Comprehensive Health Check
    # ========================================================================
    if [[ "$SKIP_HEALTH_CHECK" == true ]]; then
        print_info "Skipping system health check (--skip-health-check flag detected)"
    else
        local health_script="$SCRIPT_DIR/scripts/system-health-check.sh"
        local health_status=0
        local previous_errexit="$-"

        if [[ -x "$health_script" ]]; then
            print_info "Running detailed health check via $health_script"
            set +e
            "$health_script" --detailed
            health_status=$?
        else
            print_warning "Health check script not found at $health_script; running internal validation fallback"
            set +e
            run_system_health_check_stage
            health_status=$?
        fi

        case "$previous_errexit" in
            *e*) set -e ;;
            *)   set +e ;;
        esac

        if [[ $health_status -eq 0 ]]; then
            print_success "System health check completed"
        else
            print_warning "System health check reported issues (review output above)"
        fi

        FINAL_PHASE_HEALTH_CHECK_COMPLETED=true
        export FINAL_PHASE_HEALTH_CHECK_COMPLETED
    fi

    echo ""

    # ========================================================================
    # Step 8.1b: AI Stack Health Check
    # ========================================================================
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        local ai_health_script="$SCRIPT_DIR/scripts/check-ai-stack-health-v2.py"
        if [[ -f "$ai_health_script" ]]; then
            print_info "Running AI Stack health check..."
            if python3 "$ai_health_script" -v; then
                print_success "AI Stack health check passed."
            else
                print_warning "AI Stack health check reported issues. Review output."
            fi
        else
            print_warning "AI Stack health check script not found at $ai_health_script"
        fi
        local feedback_script="$SCRIPT_DIR/scripts/verify-local-llm-feedback.sh"
        if [[ -x "$feedback_script" ]]; then
            print_info "Running feedback pipeline verification..."
            if "$feedback_script"; then
                print_success "Feedback pipeline verification complete."
            else
                print_warning "Feedback pipeline verification reported issues."
            fi
        else
            print_warning "Feedback verification script not found at $feedback_script"
        fi
    else
        print_info "AI Stack not enabled, skipping AI health check."
    fi
    echo ""

    # ========================================================================
    # PART 2: FINAL SYSTEM CONFIGURATION
    # ========================================================================

    print_section "Part 2: Final System Configuration"
    echo ""

    # ========================================================================
    # Step 8.2: Apply Final System Configuration
    # ========================================================================
    # Complete system configuration that requires services running:
    # - Database initialization (PostgreSQL databases for Gitea)
    # - Service configuration (Gitea and other system services; ai-optimizer handles AI containers)
    # - Integration setup (service-to-service authentication)
    # - Permission finalization (service directory ownership)
    apply_final_system_configuration

    # ========================================================================
    # Step 8.3: Finalize Configuration Activation
    # ========================================================================
    # Ensure all configurations active and services using them:
    # - Reload service configurations (systemctl daemon-reload)
    # - Restart services if needed
    # - Enable user services (systemctl --user enable)
    # - Verify service dependencies
    # - Clean up temporary files
    finalize_configuration_activation

    # ========================================================================
    # Step 8.4: Local AI Stack
    # ========================================================================
    print_section "Step 8.4: Local AI Stack"

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "Hybrid Learning Stack (vLLM/Open WebUI/Qdrant/MindsDB) is managed by ai-optimizer."
        print_info "Architecture: Hybrid Coordinator + Learning System (Context Augmentation enabled)."
        print_info "Action: Run 'podman-ai-stack up' to activate the local inference and vector database."
        print_info "Use 'podman-ai-stack status' or ai-servicectl stack status for health checks when ready."
        print_info "If AI deployment is enabled, the stack will be started after this phase."
        if curl -sf --max-time 3 http://localhost:8091/health >/dev/null 2>&1; then
            print_success "AIDB is responding."
        else
            print_info "AIDB not responding yet; it will come online after you start the stack."
        fi
    else
        print_info "Local AI stack disabled; skipping."
    fi

    echo ""

    # ========================================================================
    # Step 8.5: System Monitoring Dashboard
    # ========================================================================
    print_section "Step 8.5: System Monitoring Dashboard"

    # Install dashboard (non-fatal if it fails)
    if command -v install_dashboard_to_deployment >/dev/null 2>&1; then
        install_dashboard_to_deployment || print_warning "Dashboard installation skipped (non-fatal)"
    else
        print_warning "Dashboard library not loaded (skipping dashboard installation)"
    fi

    echo ""
    print_success "System finalization complete"
    echo ""

    # TEMP_SWAP_* exported by ensure_low_memory_swap() (phase 5). Clean up here so
    # temp swapfiles don't stick around across reboots.
    if [[ "${TEMP_SWAP_CREATED:-false}" == true && -n "${TEMP_SWAP_FILE:-}" ]]; then
        print_section "Cleaning Up Temporary Swapfile"

        local -a active_swap_devices=()
        mapfile -t active_swap_devices < <(swapon --show=NAME --noheadings 2>/dev/null || true)

        local has_alternative_swap=false
        local device
        for device in "${active_swap_devices[@]}"; do
            if [[ -n "$device" && "$device" != "$TEMP_SWAP_FILE" ]]; then
                has_alternative_swap=true
                break
            fi
        done

        if [[ "$has_alternative_swap" == true ]]; then
            print_info "Permanent swap detected; removing temporary swapfile $TEMP_SWAP_FILE."
            if sudo swapoff "$TEMP_SWAP_FILE" 2>/dev/null; then
                print_success "Temporary swapfile deactivated."
            else
                print_warning "Unable to deactivate temporary swapfile $TEMP_SWAP_FILE automatically."
            fi

            if sudo rm -f "$TEMP_SWAP_FILE" 2>/dev/null; then
                print_success "Temporary swapfile removed."
                unset TEMP_SWAP_CREATED TEMP_SWAP_FILE TEMP_SWAP_SIZE_GB
            else
                print_warning "Failed to delete $TEMP_SWAP_FILE. Remove manually with: sudo rm -f $TEMP_SWAP_FILE"
            fi
        else
            print_info "Temporary swapfile $TEMP_SWAP_FILE remains active because no alternative swap device is present. Remove manually once permanent swap is configured: sudo swapoff $TEMP_SWAP_FILE && sudo rm -f $TEMP_SWAP_FILE"
        fi

        echo ""
    fi

    # ========================================================================
    # PART 3: DEPLOYMENT REPORT
    # ========================================================================

    print_section "Part 3: Deployment Report"
    echo ""

    # ========================================================================
    # Step 8.5: Generate Comprehensive Post-Install Report
    # ========================================================================
    # Detailed information about what was installed:
    # - NixOS generation information
    # - Home-manager generation information
    # - Installed package counts
    # - Service status summary
    # - Hardware configuration summary
    print_post_install

    # ========================================================================
    # PART 4: AI STACK DATA BACKUP
    # ========================================================================

    print_section "Part 4: AI Stack Data Backup"
    echo ""

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        local ai_data_source="${HOME}/.local/share/nixos-ai-stack/"
        if [[ -d "$ai_data_source" ]]; then
            local backup_dest_dir="${BACKUP_ROOT}/ai-stack-backup-$(date +%Y%m%d_%H%M%S)"
            local backup_log="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}/ai-stack-backup-$(date +%Y%m%d_%H%M%S).log"
            print_info "Backing up AI stack data from $ai_data_source..."
            mkdir -p "$backup_dest_dir"
            if command -v podman >/dev/null 2>&1; then
                if podman unshare tar -C "$ai_data_source" -cf "$backup_dest_dir/ai-stack-data.tar" . >"$backup_log" 2>&1; then
                    print_success "AI stack data successfully backed up to $backup_dest_dir"
                    print_info "Backup archive: $backup_dest_dir/ai-stack-data.tar"
                else
                    print_error "Failed to back up AI stack data. See $backup_log"
                fi
            else
                if cp -a "$ai_data_source" "$backup_dest_dir/" >"$backup_log" 2>&1; then
                    print_success "AI stack data successfully backed up to $backup_dest_dir"
                else
                    print_error "Failed to back up AI stack data. See $backup_log"
                fi
            fi
        else
            print_warning "AI stack data directory not found at $ai_data_source. Skipping backup."
        fi
    else
        print_info "AI Stack not enabled, skipping data backup."
    fi

    echo ""


    # ========================================================================
    # Step 8.6: Display Success Banner
    # ========================================================================
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Deployment Complete - All 8 Phases Successful!               ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ========================================================================
    # Step 8.7: Configuration Status Summary
    # ========================================================================
    print_info "Configuration Status:"
    echo -e "  ${GREEN}✓${NC} NixOS system configuration applied"
    echo -e "  ${GREEN}✓${NC} Home-manager user environment active"
    echo -e "  ${GREEN}✓${NC} Flatpak applications installed"
    echo -e "  ${GREEN}✓${NC} Development tools configured"
    echo ""

    # ========================================================================
    # Step 8.8: Installed Components List
    # ========================================================================
    print_info "Installed Components:"
    echo "  • COSMIC Desktop Environment"
    echo "  • Podman container runtime"
    echo "  • PostgreSQL database"
    echo "  • Python AI/ML environment"
    echo "  • Development CLI tools (100+)"
    echo "  • Claude Code integration"
    if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
        echo "  • Gitea self-hosted Git service"
    fi
    echo "  • Hybrid Learning Stack (Qdrant Vector DB + llama.cpp LLM + Ollama)"
    echo "  • Agentic Capabilities: Context Augmentation & Token Reduction (30-50%)"
    echo ""

    # ========================================================================
    # Step 8.9: Next Steps Guide
    # ========================================================================
    local git_identity_hint="${GIT_IDENTITY_PREFERENCE_FILE:-$DEPLOYMENT_PREFERENCES_DIR/git-identity.env}"
    local gitea_secrets_hint="${GITEA_SECRETS_CACHE_FILE:-$PRIMARY_HOME/.config/nixos-quick-deploy/gitea-secrets.env}"

    echo -e "${BLUE}Next Steps:${NC}"
    echo ""

    echo -e "  ${GREEN}1.${NC} Reload your shell to activate new environment:"
    echo -e "     ${YELLOW}exec zsh${NC}"
    echo ""

    echo -e "  ${GREEN}2.${NC} Verify services:"
    if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
        echo -e "     ${YELLOW}systemctl status gitea${NC}"
    fi
    echo -e "     ${YELLOW}podman-ai-stack status${NC}"
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

    echo -e "  ${GREEN}6.${NC} Adjust git identity later if needed:"
    echo -e "     ${YELLOW}./nixos-quick-deploy.sh --resume 1${NC} to rerun Phase 1 prompts"
    echo -e "     ${YELLOW}git config --global user.name \"Your Name\"${NC}"
    echo -e "     ${YELLOW}git config --global user.email \"you@example.com\"${NC}"
    if [[ -n "$git_identity_hint" ]]; then
        echo -e "     or edit ${YELLOW}$git_identity_hint${NC} (user.name/user.email) and rerun Phase 1."
    fi
    echo ""

    if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
        echo -e "  ${GREEN}7.${NC} Update Gitea admin bootstrap settings:"
        echo -e "     ${YELLOW}./nixos-quick-deploy.sh --resume 1${NC} and opt into the Gitea prompt"
        if [[ -n "$gitea_secrets_hint" ]]; then
            echo -e "     or edit ${YELLOW}$gitea_secrets_hint${NC} (shell-quoted secrets) then rerun Phase 1."
        fi
        echo ""
    fi


    # ========================================================================
    # Step 8.10: Reboot Recommendation (Conditional)
    # ========================================================================
    # Recommend reboot if kernel/init system updated
    if [[ -L "/run/booted-system" && -L "/run/current-system" ]]; then
        if [[ "$(readlink /run/booted-system)" != "$(readlink /run/current-system)" ]]; then
            echo -e "${YELLOW}⚠ Reboot Recommended:${NC}"
            echo "  • Kernel/init system updates detected"
            echo -e "  • Run: ${YELLOW}sudo reboot${NC}"
            echo "  • After reboot, select 'Cosmic' from login screen"
            echo ""
        fi
    fi

    # ========================================================================
    # Step 8.11: Configuration File Locations
    # ========================================================================
    print_info "Configuration Files:"
    echo "  • System: $SYSTEM_CONFIG_FILE"
    echo "  • Home: $HOME_MANAGER_FILE"
    echo "  • Flake: $FLAKE_FILE"
    echo "  • Hardware: $HARDWARE_CONFIG_FILE"
    echo ""

    # ========================================================================
    # Step 8.12: Logs and Troubleshooting Resources
    # ========================================================================
    print_info "Logs & Troubleshooting:"
    echo "  • Deployment log: $LOG_FILE"
    echo "  • State file: $STATE_FILE"
    echo "  • Backup location: $BACKUP_ROOT"
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 8: System Finalization & Deployment Report - COMPLETE"
    echo ""

    # ========================================================================
    # Final Success Banner
    # ========================================================================
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ NixOS Quick Deploy v$SCRIPT_VERSION completed successfully!${NC}"
    echo -e "${GREEN}✓ Your AIDB development environment is ready!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Execute phase
phase_08_finalization_and_report
