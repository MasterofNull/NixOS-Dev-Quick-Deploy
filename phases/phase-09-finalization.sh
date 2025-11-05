#!/usr/bin/env bash
#
# Phase 09: Post-Install Scripts & Finalization
# Purpose: Complete setup of packages requiring post-install configuration
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/finalization.sh → apply_final_system_configuration(), finalize_configuration_activation()
#
# Required Variables (from config/variables.sh):
#   - None (finalization uses system-level operations)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - apply_final_system_configuration() → Apply final config
#   - finalize_configuration_activation() → Finalize activation
#
# Requires Phases (must complete before this):
#   - Phase 8: VALIDATION_PASSED must be true
#
# Produces (for later phases):
#   - FINALIZATION_COMPLETE → Flag indicating finalization done
#   - State: "post_install_finalization" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_09_finalization() {
    # ========================================================================
    # Phase 9: Post-Install Scripts & Finalization
    # ========================================================================
    # This is the "finishing touches" phase - perform final configuration
    # steps that require the full system to be deployed and validated.
    #
    # Why separate finalization phase:
    # - Some configs depend on services being running
    # - Database initialization requires PostgreSQL active
    # - User permissions require user accounts created
    # - Service integrations require all components present
    #
    # What happens in finalization:
    # 1. Final system configuration tweaks
    #    - Service configuration that depends on runtime state
    #    - Database initialization
    #    - User permission assignments
    #    - System integration tasks
    #
    # 2. Configuration activation
    #    - Restart services with final configs
    #    - Enable user services
    #    - Trigger post-install hooks
    #    - Clean up temporary files
    #
    # Timing consideration:
    # - Run after validation (Phase 8) ensures system ready
    # - Run before reporting (Phase 10) so report is complete
    # - Services must be running for some finalization steps
    #
    # Examples of finalization tasks:
    # - Initialize PostgreSQL databases for Gitea
    # - Configure Ollama with initial models
    # - Set up Qdrant collections
    # - Generate SSH keys for services
    # - Configure service-to-service authentication
    # - Set up cron jobs or timers
    # - Initialize data directories with proper permissions
    # ========================================================================

    local phase_name="post_install_finalization"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 9 already completed (skipping)"
        return 0
    fi

    print_section "Phase 9/10: Post-Install Scripts & Finalization"
    echo ""

    # ========================================================================
    # Step 9.1: Apply Final System Configuration
    # ========================================================================
    # Why: Complete system configuration that requires services running
    # How: apply_final_system_configuration() performs:
    #      1. Database initialization
    #      2. Service configuration
    #      3. Integration setup
    #      4. Permission finalization
    #
    # Database initialization:
    # - Create application databases
    #   Example: CREATE DATABASE gitea;
    # - Create database users
    #   Example: CREATE USER gitea WITH PASSWORD '...';
    # - Grant permissions
    #   Example: GRANT ALL ON DATABASE gitea TO gitea;
    # - Run schema migrations
    # - Initialize default data
    #
    # Service configuration:
    # - Gitea: Connect to PostgreSQL, create admin user
    # - Ollama: Download initial AI models
    # - Qdrant: Create default collections
    # - Huggingface TGI: Configure model endpoints
    #
    # Integration setup:
    # - Configure service-to-service authentication
    # - Set up reverse proxy rules
    # - Configure firewall exceptions
    # - Link service configurations
    #
    # Permission finalization:
    # - Set ownership of service directories
    #   Example: chown -R gitea:gitea /var/lib/gitea
    # - Set file permissions
    #   Example: chmod 700 /var/lib/gitea/data
    # - Configure SELinux/AppArmor if enabled
    #
    # Why now:
    # - PostgreSQL is running (started in Phase 6)
    # - All services are active (deployed in Phase 6)
    # - Validation passed (Phase 8)
    # - Safe to make live changes
    apply_final_system_configuration

    # ========================================================================
    # Step 9.2: Finalize Configuration Activation
    # ========================================================================
    # Why: Ensure all configurations are active and services using them
    # How: finalize_configuration_activation() performs:
    #      1. Reload service configurations
    #      2. Restart services if needed
    #      3. Enable user services
    #      4. Verify service dependencies
    #      5. Clean up temporary files
    #
    # Service reload/restart:
    # - systemctl daemon-reload: Reload systemd unit files
    # - systemctl reload SERVICE: Hot-reload config without restart
    # - systemctl restart SERVICE: Full restart if reload not supported
    #
    # When to reload vs restart:
    # - Reload: Configuration change, keep connections (nginx, postgres)
    # - Restart: Binary update, dependency change (most services)
    #
    # Enable user services:
    # - systemctl --user enable SERVICE: Auto-start on login
    # - systemctl --user start SERVICE: Start now
    # - Examples: jupyter-lab, custom daemons
    #
    # Verify service dependencies:
    # - Check all dependencies running
    # - Example: Gitea requires PostgreSQL
    # - Wait for dependencies if needed
    # - Timeout after reasonable period
    #
    # Clean up temporary files:
    # - Remove download caches
    # - Clear temporary build directories
    # - Remove state tracking used during deployment
    # - Keep logs and backups
    #
    # Why now:
    # - All configurations in place
    # - Services have been configured
    # - Final opportunity to ensure clean state
    # - Next phase is reporting (read-only)
    finalize_configuration_activation

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Finalization complete! System is fully configured and ready for use.
    #
    # What happened:
    # - All services configured and running
    # - Databases initialized
    # - Integrations set up
    # - Permissions finalized
    # - Configuration activation complete
    #
    # System state:
    # - NixOS system: Fully deployed and configured
    # - User environment: Fully deployed and configured
    # - Services: Running with final configurations
    # - Integrations: Active and connected
    #
    # State: "post_install_finalization" marked complete
    # Next: Phase 10 will generate comprehensive deployment report
    mark_step_complete "$phase_name"
    print_success "Phase 9: Post-Install Scripts & Finalization - COMPLETE"
    echo ""
}

# Execute phase
phase_09_finalization
