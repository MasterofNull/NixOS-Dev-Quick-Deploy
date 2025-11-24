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

    # Ensure Hugging Face token file exists for TGI
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        local hf_env_file="${HUGGINGFACE_TGI_ENV_FILE:-/var/lib/nixos-quick-deploy/secrets/huggingface-tgi.env}"
        local hf_env_dir
        hf_env_dir="$(dirname "$hf_env_file")"
        local hf_token="${HUGGINGFACEHUB_API_TOKEN:-}"
        if [[ -z "$hf_token" && -f "$HOME/.config/huggingface/token" ]]; then
            hf_token="$(head -n1 "$HOME/.config/huggingface/token" 2>/dev/null | tr -d '\r')"
        fi

        if [[ -n "$hf_token" ]]; then
            if sudo mkdir -p "$hf_env_dir" && \
               echo -e "HF_TOKEN=${hf_token}\nHUGGINGFACEHUB_API_TOKEN=${hf_token}" | sudo tee "$hf_env_file" >/dev/null; then
                sudo chmod 600 "$hf_env_file" || true
                print_success "Ensured Hugging Face token file at $hf_env_file"
            else
                print_warning "Failed to write Hugging Face token to $hf_env_file; verify sudo access and rerun."
            fi
        else
            print_warning "HUGGINGFACEHUB_API_TOKEN not set and no ~/.config/huggingface/token found; TGI may fail to start."
        fi
    fi

    # Pre-pull Podman AI stack images to avoid timeouts during service startup
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]] && command -v podman >/dev/null 2>&1; then
        print_info "Pre-pulling AI stack images (ollama, open-webui, qdrant)..."
        local -a images=(
            "docker.io/ollama/ollama:latest"
            "ghcr.io/open-webui/open-webui:latest"
            "docker.io/qdrant/qdrant:latest"
        )
        local img
        for img in "${images[@]}"; do
            if podman image exists "$img" >/dev/null 2>&1; then
                continue
            fi
            if podman pull "$img"; then
                print_success "Pulled $img"
            else
                print_warning "Failed to pull $img; service startup may retry/pull."
            fi
        done
        echo ""
    fi

    # Start Podman-based AI stack now that the generation has been switched, so health checks see running services.
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_info "Starting Podman-based AI stack services (manual autoStart)"
        # Disable HF transfer acceleration if inherited from the environment to avoid missing hf_transfer.
        export HF_HUB_ENABLE_HF_TRANSFER=0
        local -a podman_units=(
            "podman-local-ai-network.service"
            "podman-local-ai-ollama.service"
            "podman-local-ai-qdrant.service"
            "podman-local-ai-open-webui.service"
        )
        local unit
        for unit in "${podman_units[@]}"; do
            if systemctl --user start "$unit" 2>/dev/null; then
                print_success "Started $unit"
            else
                print_warning "Failed to start $unit; check: journalctl --user -u $unit"
            fi
        done
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

        if [[ -x "$health_script" ]]; then
            print_info "Running detailed health check via $health_script"
            set +e
            "$health_script" --detailed
            health_status=$?
            set -e
        else
            print_warning "Health check script not found at $health_script; running internal validation fallback"
            set +e
            run_system_health_check_stage
            health_status=$?
            set -e
        fi

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
    # PART 2: FINAL SYSTEM CONFIGURATION
    # ========================================================================

    print_section "Part 2: Final System Configuration"
    echo ""

    # ========================================================================
    # Step 8.2: Apply Final System Configuration
    # ========================================================================
    # Complete system configuration that requires services running:
    # - Database initialization (PostgreSQL databases for Gitea)
    # - Service configuration (Gitea, Ollama, Qdrant, HuggingFace TGI)
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
    # Step 8.4: Enable AI Services and Pull Ollama Models
    # ========================================================================
    # Note: Hugging Face models were already downloaded in Phase 5 (before system switch)
    # so that TGI services start with cached models. Here we just enable services
    # and pull Ollama models (which require the API to be running).
    print_section "Step 8.4: Enable AI Services and Pull Ollama Models"

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        print_warning "Local AI stack disabled; skipping AI service setup."
    else
        # Create systemd drop-ins to increase timeout for large container startups
        print_info "Creating service timeout overrides for Ollama and Open WebUI..."
        mkdir -p "$HOME/.config/systemd/user/podman-local-ai-ollama.service.d"
        mkdir -p "$HOME/.config/systemd/user/podman-local-ai-open-webui.service.d"

        cat > "$HOME/.config/systemd/user/podman-local-ai-ollama.service.d/timeout.conf" <<'EOF'
[Service]
# Increase timeout for large container (Ollama is 3.75GB)
TimeoutStartSec=300
EOF

        cat > "$HOME/.config/systemd/user/podman-local-ai-open-webui.service.d/timeout.conf" <<'EOF'
[Service]
# Increase timeout for large container (Open WebUI is 4.38GB)
TimeoutStartSec=300
EOF

        systemctl --user daemon-reload
        print_success "Timeout overrides created"

        # Enable user-level Podman units for the AI stack
        print_info "Enabling Podman AI stack services (network, Ollama, Qdrant, Open WebUI)..."
        systemctl --user enable --now podman-local-ai-network.service podman-local-ai-ollama.service podman-local-ai-qdrant.service podman-local-ai-open-webui.service >/dev/null 2>&1 || true

        # Pull Ollama models (requires API to be running)
        if ! command -v curl >/dev/null 2>&1 || ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            print_info "Waiting for Ollama API to become available..."
            local retry=0
            local max_retries=10
            until curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || [[ $retry -ge $max_retries ]]; do
                sleep 3
                ((retry++))
            done
        fi

        if command -v curl >/dev/null 2>&1 && curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            print_success "Ollama API is available"
            # Keep Ollama preloads lean: single lightweight model for quick testing
            local -a ollama_models=("phi4")
            local ollama_model
            local existing_tags=""
            existing_tags="$(curl -fsS http://127.0.0.1:11434/api/tags 2>/dev/null || true)"
            for ollama_model in "${ollama_models[@]}"; do
                if [[ "${FORCE_OLLAMA_PULL:-false}" != "true" ]] && printf '%s' "$existing_tags" | grep -q "\"name\"\s*:\s*\"${ollama_model}\""; then
                    print_success "Ollama model already present: $ollama_model (skipping)"
                    continue
                fi
                print_info "Pulling Ollama model: $ollama_model"
                if ollama pull "$ollama_model"; then
                    print_success "Pulled $ollama_model"
                else
                    print_warning "Ollama pull failed for $ollama_model (check connectivity or GPU drivers)"
                fi
            done
        else
            print_warning "Ollama API not reachable; skipping model pulls"
            print_info "Start manually with: systemctl --user start podman-local-ai-ollama.service"
        fi

        if command -v systemctl >/dev/null 2>&1; then
            if systemctl list-unit-files | grep -q '^huggingface-tgi\\.service'; then
                print_info "Enabling Hugging Face TGI system service"
                if sudo systemctl enable --now huggingface-tgi 2>/dev/null; then
                    sleep 3  # Give service time to start
                    if systemctl is-active --quiet huggingface-tgi 2>/dev/null; then
                        print_success "HuggingFace TGI service started successfully"
                    else
                        local tgi_status=$(systemctl show huggingface-tgi --property=ActiveState --value 2>/dev/null | tr -d '\r')
                        if [[ "$tgi_status" == "failed" ]]; then
                            print_error "HuggingFace TGI service failed to start"
                            print_info "Check logs: journalctl -u huggingface-tgi.service -n 30"
                            local error_msg=$(systemctl status huggingface-tgi --no-pager -l 2>/dev/null | grep -i "No such file or directory" | tail -n 1 | sed 's/^[[:space:]]*//')
                            if [[ -n "$error_msg" ]]; then
                                print_info "Error: $error_msg"
                                print_info "This may require a system reboot or nixos-rebuild switch to create missing directories"
                            fi
                        else
                            print_warning "HuggingFace TGI service is not active (status: $tgi_status)"
                        fi
                    fi
                else
                    print_warning "Unable to enable/start huggingface-tgi service automatically"
                fi
            fi
            if systemctl list-unit-files | grep -q '^huggingface-tgi-scout\\.service'; then
                print_info "Enabling Hugging Face TGI Scout service"
                if sudo systemctl enable --now huggingface-tgi-scout 2>/dev/null; then
                    sleep 3  # Give service time to start
                    if systemctl is-active --quiet huggingface-tgi-scout 2>/dev/null; then
                        print_success "HuggingFace TGI Scout service started successfully"
                    else
                        local scout_status=$(systemctl show huggingface-tgi-scout --property=ActiveState --value 2>/dev/null | tr -d '\r')
                        if [[ "$scout_status" == "failed" ]]; then
                            print_error "HuggingFace TGI Scout service failed to start"
                            print_info "Check logs: journalctl -u huggingface-tgi-scout.service -n 30"
                            local error_msg=$(systemctl status huggingface-tgi-scout --no-pager -l 2>/dev/null | grep -i "No such file or directory" | tail -n 1 | sed 's/^[[:space:]]*//')
                            if [[ -n "$error_msg" ]]; then
                                print_info "Error: $error_msg"
                                print_info "This may require a system reboot or nixos-rebuild switch to create missing directories"
                            fi
                        else
                            print_warning "HuggingFace TGI Scout service is not active (status: $scout_status)"
                        fi
                    fi
                else
                    print_warning "Unable to enable/start huggingface-tgi-scout service automatically"
                fi
            fi
        fi

        # Health checks for all endpoints
        print_section "Local AI endpoint health checks"

        # Ollama
        if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            print_success "Ollama API reachable on 11434"
            curl -fsS http://127.0.0.1:11434/api/tags 2>/dev/null | jq -r '.models[].name' | sed 's/^/  - /' || true
        else
            print_warning "Ollama API not reachable on 11434"
        fi

        # DeepSeek TGI
        if curl -fsS http://127.0.0.1:8080/v1/models >/dev/null 2>&1; then
            print_success "TGI (DeepSeek) reachable on 8080"
        else
            print_warning "TGI (DeepSeek) not reachable on 8080"
        fi

        # Scout TGI
        if curl -fsS http://127.0.0.1:8085/v1/models >/dev/null 2>&1; then
            print_success "TGI (Llama 4 Scout) reachable on 8085"
        else
            print_warning "TGI (Llama 4 Scout) not reachable on 8085"
        fi

        # Open WebUI
        if curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:8081 2>/dev/null | grep -q '^200$'; then
            print_success "Open WebUI reachable on 8081"
        else
            print_warning "Open WebUI not reachable on 8081"
        fi

        # Optional lightweight smoke prompts (do not fail deployment)
        print_section "Local AI smoke prompts (best-effort)"
        if command -v ollama >/dev/null 2>&1; then
            ollama run phi4 "test" >/tmp/ollama-smoke.log 2>/dev/null && print_success "Ollama phi4 smoke prompt succeeded" || print_warning "Ollama phi4 smoke prompt failed"
        fi
        curl -fsS -X POST http://127.0.0.1:8080/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{"model":"'"${huggingfaceModelId:-deepseek-ai/DeepSeek-R1-Distill-Qwen-7B}"'","messages":[{"role":"user","content":"ping"}],"max_tokens":10}' >/tmp/tgi-8080-smoke.log 2>/dev/null &&
            print_success "TGI 8080 (DeepSeek) smoke prompt succeeded" || print_warning "TGI 8080 (DeepSeek) smoke prompt failed"

        curl -fsS -X POST http://127.0.0.1:8085/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{"model":"'"${huggingfaceScoutModelId:-meta-llama/Llama-4-Scout-17B-16E}"'","messages":[{"role":"user","content":"ping"}],"max_tokens":10}' >/tmp/tgi-8085-smoke.log 2>/dev/null &&
            print_success "TGI 8085 (Scout) smoke prompt succeeded" || print_warning "TGI 8085 (Scout) smoke prompt failed"
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
    echo "  • System services (Gitea, Qdrant, Ollama, TGI)"
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

    echo -e "  ${GREEN}6.${NC} Adjust git identity later if needed:"
    echo -e "     ${YELLOW}./nixos-quick-deploy.sh --resume 1${NC} to rerun Phase 1 prompts"
    echo -e "     ${YELLOW}git config --global user.name \"Your Name\"${NC}"
    echo -e "     ${YELLOW}git config --global user.email \"you@example.com\"${NC}"
    if [[ -n "$git_identity_hint" ]]; then
        echo -e "     or edit ${YELLOW}$git_identity_hint${NC} (user.name/user.email) and rerun Phase 1."
    fi
    echo ""

    echo -e "  ${GREEN}7.${NC} Update Gitea admin bootstrap settings:"
    echo -e "     ${YELLOW}./nixos-quick-deploy.sh --resume 1${NC} and opt into the Gitea prompt"
    if [[ -n "$gitea_secrets_hint" ]]; then
        echo -e "     or edit ${YELLOW}$gitea_secrets_hint${NC} (shell-quoted secrets) then rerun Phase 1."
    fi
    echo ""


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
