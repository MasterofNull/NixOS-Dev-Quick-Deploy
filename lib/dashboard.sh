#!/run/current-system/sw/bin/bash
# Declarative dashboard shim.
# Legacy imperative dashboard setup has been moved to deprecated/lib/dashboard.sh.

setup_system_dashboard() {
    print_info "Dashboard is declaratively managed by NixOS modules (no imperative setup)."
    print_info "Apply changes with: sudo nixos-rebuild switch --flake .#${HOSTNAME:-nixos}"
    return 0
}

install_dashboard_to_deployment() {
    print_section "Step 8.5: System Monitoring Dashboard"
    print_info "Imperative dashboard installer is deprecated; declarative services remain authoritative."
    print_info "Check status: systemctl status command-center-dashboard.service"
    return 0
}
