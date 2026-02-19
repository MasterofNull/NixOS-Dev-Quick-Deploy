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

phase_08_backfill_env_key() {
    local key="$1"
    local value="$2"
    local file="$3"

    if grep -qE "^[[:space:]]*${key}=" "$file" 2>/dev/null; then
        if grep -qE "^[[:space:]]*${key}=$" "$file" 2>/dev/null; then
            sed -i "s|^[[:space:]]*${key}=.*|${key}=${value}|" "$file"
        fi
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

phase_08_run_system_health_check() {
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "AI stack services are deployed via K3s cluster (Phase 9)."
        print_info "Check status with: kubectl get pods -n ${PHASE_08_AI_STACK_NS}"
        echo ""
    else
        print_info "AI stack deployment is configured in Phase 9."
        print_info "If you skipped AI stack, you can deploy it later with --with-ai-model."
        echo ""
    fi

    print_section "Part 1: System Health Check"
    echo ""

    local strict_health_checks="${STRICT_HEALTH_CHECKS:-false}"
    if [[ "$SKIP_HEALTH_CHECK" == true ]]; then
        print_info "Skipping system health check (--skip-health-check flag detected)"
        echo ""
        return 0
    fi

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
        if [[ "$strict_health_checks" == "true" ]]; then
            print_error "System health check failed with STRICT_HEALTH_CHECKS=true"
            return 1
        fi
        print_warning "System health check reported issues (review output above)"
    fi

    FINAL_PHASE_HEALTH_CHECK_COMPLETED=true
    export FINAL_PHASE_HEALTH_CHECK_COMPLETED
    echo ""
}

phase_08_run_ai_stack_health_check() {
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        print_info "AI Stack not enabled, skipping AI health check."
        echo ""
        return 0
    fi

    local enforce_ai_health="${ENFORCE_AI_STACK_HEALTH:-false}"
    local require_ai_running="${REQUIRE_AI_STACK_RUNNING:-false}"
    local ai_health_script="$SCRIPT_DIR/scripts/check-ai-stack-health-v2.py"

    local running_ai_pods=0
    if command -v kubectl >/dev/null 2>&1; then
        if declare -F kubectl_safe >/dev/null 2>&1; then
            running_ai_pods=$(kubectl_safe get pods -n "${PHASE_08_AI_STACK_NS}" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo "0")
        else
            running_ai_pods=$(kubectl --request-timeout="${KUBECTL_TIMEOUT:-60}s" get pods -n "${PHASE_08_AI_STACK_NS}" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo "0")
        fi
    fi

    if [[ "$running_ai_pods" -eq 0 ]]; then
        if [[ "$require_ai_running" == "true" ]]; then
            print_error "AI Stack pods are not running and REQUIRE_AI_STACK_RUNNING=true"
            return 1
        fi
        print_warning "AI Stack pods are not running in K3s; skipping AI health check."
    elif [[ -f "$ai_health_script" ]]; then
        print_info "Running AI Stack health check..."
        local python_bin
        python_bin="$(command -v python3 2>/dev/null || true)"
        if [[ -z "$python_bin" ]]; then
            local hm_python="$HOME/.local/state/nix/profiles/home-manager/bin/python3"
            if [[ -x "$hm_python" ]]; then
                python_bin="$hm_python"
            fi
        fi
        if [[ -z "$python_bin" ]]; then
            print_warning "python3 not available; skipping AI Stack health check."
        elif "$python_bin" "$ai_health_script" -v; then
            print_success "AI Stack health check passed."
        else
            if [[ "$enforce_ai_health" == "true" ]]; then
                print_error "AI Stack health check failed with ENFORCE_AI_STACK_HEALTH=true"
                return 1
            fi
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

    if declare -f ensure_ai_stack_env >/dev/null 2>&1; then
        ensure_ai_stack_env
    fi

    local env_file="${AI_STACK_ENV_FILE:-${AI_STACK_CONFIG_DIR:-$HOME/.config/nixos-ai-stack}/.env}"
    if [[ -f "$env_file" ]]; then
        local ai_stack_data_default
        ai_stack_data_default="${AI_STACK_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/nixos-ai-stack}"
        phase_08_backfill_env_key "AI_STACK_DATA" "$ai_stack_data_default" "$env_file"
        phase_08_backfill_env_key "LLAMA_CPP_DEFAULT_MODEL" "${LLAMA_CPP_DEFAULT_MODEL:-unsloth/Qwen3-4B-Instruct-2507-GGUF}" "$env_file"
        phase_08_backfill_env_key "LLAMA_CPP_MODEL_FILE" "${LLAMA_CPP_MODEL_FILE:-qwen2.5-coder-7b-instruct-q4_k_m.gguf}" "$env_file"
    fi

    local drift_script="$SCRIPT_DIR/scripts/validate-ai-stack-env-drift.sh"
    local enforce_drift_check="${ENFORCE_ENV_DRIFT_CHECK:-true}"
    if [[ -x "$drift_script" ]]; then
        print_info "Running AI stack env drift check..."
        if "$drift_script"; then
            print_success "AI stack env drift check passed."
        else
            if [[ "$enforce_drift_check" == "true" ]]; then
                print_error "AI stack env drift check failed with ENFORCE_ENV_DRIFT_CHECK=true"
                return 1
            fi
            print_warning "AI stack env drift check reported issues."
        fi
    else
        print_warning "AI stack env drift check script not found at $drift_script"
    fi

    echo ""
}

phase_08_run_final_system_config() {
    print_section "Part 2: Final System Configuration"
    echo ""

    apply_final_system_configuration
    finalize_configuration_activation
}

phase_08_report_ai_stack_status() {
    print_section "Step 8.4: Local AI Stack"

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "AI Stack (llama-cpp/Qdrant/PostgreSQL/Grafana) runs in K3s cluster."
        print_info "Architecture: K3s orchestrated services in '${PHASE_08_AI_STACK_NS}' namespace."
        print_info "Check status: kubectl get pods -n ${PHASE_08_AI_STACK_NS}"
        print_info "View services: kubectl get svc -n ${PHASE_08_AI_STACK_NS}"
        if command -v kubectl >/dev/null 2>&1; then
            local running_pods
            if declare -F kubectl_safe >/dev/null 2>&1; then
                running_pods=$(kubectl_safe get pods -n "${PHASE_08_AI_STACK_NS}" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo "0")
            else
                running_pods=$(kubectl --request-timeout="${KUBECTL_TIMEOUT:-60}s" get pods -n "${PHASE_08_AI_STACK_NS}" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo "0")
            fi
            if [[ "$running_pods" -gt 0 ]]; then
                print_success "K3s AI stack: $running_pods pods running"
            else
                print_info "AI stack pods not running yet; they will start in Phase 9."
            fi
        fi
    else
        print_info "Local AI stack disabled; skipping."
    fi

    echo ""
}

phase_08_install_dashboard() {
    print_section "Step 8.5: System Monitoring Dashboard"

    if command -v install_dashboard_to_deployment >/dev/null 2>&1; then
        install_dashboard_to_deployment || print_warning "Dashboard installation skipped (non-fatal)"
    else
        print_warning "Dashboard library not loaded (skipping dashboard installation)"
    fi

    echo ""
    print_success "System finalization complete"
    echo ""
}

phase_08_cleanup_temp_swap() {
    if [[ "${TEMP_SWAP_CREATED:-false}" != true || -z "${TEMP_SWAP_FILE:-}" ]]; then
        return 0
    fi

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
        if sudo -n swapoff "$TEMP_SWAP_FILE" 2>/dev/null; then
            print_success "Temporary swapfile deactivated."
        else
            print_warning "Unable to deactivate temporary swapfile $TEMP_SWAP_FILE automatically."
        fi

        if sudo -n rm -f "$TEMP_SWAP_FILE" 2>/dev/null; then
            print_success "Temporary swapfile removed."
            unset TEMP_SWAP_CREATED TEMP_SWAP_FILE TEMP_SWAP_SIZE_GB
        else
            print_warning "Failed to delete $TEMP_SWAP_FILE. Remove manually with: sudo rm -f $TEMP_SWAP_FILE"
        fi
    else
        print_info "Temporary swapfile $TEMP_SWAP_FILE remains active because no alternative swap device is present. Remove manually once permanent swap is configured: sudo swapoff $TEMP_SWAP_FILE && sudo rm -f $TEMP_SWAP_FILE"
    fi

    echo ""
}

phase_08_generate_report() {
    print_section "Part 3: Deployment Report"
    echo ""
    print_post_install
}

phase_08_backup_ai_stack_data() {
    print_section "Part 4: AI Stack Data Backup"
    echo ""

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "K3s AI stack data is managed via PersistentVolumeClaims."
        print_info "Automated backups run via CronJobs in the 'backups' namespace."
        print_info "Check backup status: kubectl get cronjobs -n backups"

        local ai_data_source="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack/}"
        if [[ -d "$ai_data_source" ]]; then
            local backup_dest_dir
            local backup_log
            backup_dest_dir="${BACKUP_ROOT}/ai-stack-backup-$(date +%Y%m%d_%H%M%S)"
            backup_log="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}/ai-stack-backup-$(date +%Y%m%d_%H%M%S).log"
            print_info "Backing up local AI data from $ai_data_source..."
            mkdir -p "$backup_dest_dir"
            if tar --ignore-failed-read -cf - -C "$ai_data_source" . 2>"$backup_log" | tar -xf - -C "$backup_dest_dir" 2>>"$backup_log"; then
                print_success "Local AI data backed up to $backup_dest_dir"
            else
                if grep -q "Permission denied" "$backup_log" 2>/dev/null; then
                    print_warning "Local AI data backup completed with unreadable paths. See $backup_log"
                else
                    print_warning "Failed to back up local AI data. See $backup_log"
                fi
            fi
        fi
    else
        print_info "AI Stack not enabled, skipping data backup."
    fi

    echo ""
}

phase_08_print_success_banner() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Deployment Complete - All 8 Phases Successful!               ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

phase_08_print_status_summary() {
    print_info "Configuration Status:"
    echo -e "  ${GREEN}✓${NC} NixOS system configuration applied"
    echo -e "  ${GREEN}✓${NC} Home-manager user environment active"
    echo -e "  ${GREEN}✓${NC} Flatpak applications installed"
    echo -e "  ${GREEN}✓${NC} Development tools configured"
    echo ""
}

phase_08_print_installed_components() {
    print_info "Installed Components:"
    echo "  • COSMIC Desktop Environment"
    echo "  • K3s container orchestration"
    echo "  • PostgreSQL database (K3s)"
    echo "  • Python AI/ML environment"
    echo "  • Development CLI tools (100+)"
    echo "  • Claude Code integration"
    if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
        echo "  • Gitea self-hosted Git service"
    fi
    echo "  • AI Stack: Qdrant Vector DB + llama.cpp LLM (K3s orchestrated)"
    echo "  • Monitoring: Grafana + Prometheus + Loki (K3s)"
    echo ""
}

phase_08_print_next_steps() {
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
    echo -e "     ${YELLOW}kubectl get pods -n ${PHASE_08_AI_STACK_NS}${NC}"
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
    echo -e "     ${YELLOW}git config --global user.name "Your Name"${NC}"
    echo -e "     ${YELLOW}git config --global user.email "you@example.com"${NC}"
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
}

phase_08_print_reboot_recommendation() {
    if [[ -L "/run/booted-system" && -L "/run/current-system" ]]; then
        if [[ "$(readlink /run/booted-system)" != "$(readlink /run/current-system)" ]]; then
            echo -e "${YELLOW}⚠ Reboot Recommended:${NC}"
            echo "  • Kernel/init system updates detected"
            echo -e "  • Run: ${YELLOW}sudo reboot${NC}"
            echo "  • After reboot, select 'Cosmic' from login screen"
            echo ""
        fi
    fi
}

phase_08_print_config_locations() {
    print_info "Configuration Files:"
    echo "  • System: $SYSTEM_CONFIG_FILE"
    echo "  • Home: $HOME_MANAGER_FILE"
    echo "  • Flake: $FLAKE_FILE"
    echo "  • Hardware: $HARDWARE_CONFIG_FILE"
    echo ""
}

phase_08_print_logs_resources() {
    print_info "Logs & Troubleshooting:"
    echo "  • Deployment log: $LOG_FILE"
    echo "  • State file: $STATE_FILE"
    echo "  • Backup location: $BACKUP_ROOT"
    echo ""
}

phase_08_print_final_banner() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ NixOS Quick Deploy v$SCRIPT_VERSION completed successfully!${NC}"
    echo -e "${GREEN}✓ Your AIDB development environment is ready!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

phase_08_finalization_and_report() {
    local phase_name="finalization_and_report"
    PHASE_08_AI_STACK_NS="${AI_STACK_NAMESPACE:-ai-stack}"

    if is_step_complete "$phase_name"; then
        print_info "Phase 8 already completed (skipping)"
        return 0
    fi

    print_section "Phase 8/8: System Finalization & Deployment Report"
    echo ""

    phase_08_run_system_health_check || return $?
    phase_08_run_ai_stack_health_check || return $?
    phase_08_run_final_system_config
    phase_08_report_ai_stack_status
    phase_08_install_dashboard
    phase_08_cleanup_temp_swap
    phase_08_generate_report
    phase_08_backup_ai_stack_data
    phase_08_print_success_banner
    phase_08_print_status_summary
    phase_08_print_installed_components
    phase_08_print_next_steps
    phase_08_print_reboot_recommendation
    phase_08_print_config_locations
    phase_08_print_logs_resources

    mark_step_complete "$phase_name"
    # Ensure phase marker exists even if this script is run directly.
    mark_step_complete "phase-08"
    print_success "Phase 8: System Finalization & Deployment Report - COMPLETE"
    echo ""

    phase_08_print_final_banner
}


# Execute phase
phase_08_finalization_and_report
