# Dashboard Deployment Integration

**Status**: Historical integration notes; runtime model superseded
**Version**: 1.0.0
**Integration Point**: Legacy Phase 8 integration notes

---

## Overview

This document describes an older imperative dashboard deployment flow. The current production runtime is the declarative `command-center-dashboard-api.service`, which serves both the operator UI and API from `http://127.0.0.1:8889/`.

---

## Integration Points

### 1. Phase 8: Finalization (Step 8.5)

**Location**: [phases/phase-08-finalization-and-report.sh](phases/phase-08-finalization-and-report.sh#L173-L183)

**Current Runtime**:
```bash
systemctl status command-center-dashboard-api.service
curl http://127.0.0.1:8889/api/health
xdg-open http://127.0.0.1:8889/
```

Legacy user-service setup notes below are retained for migration history only.

### 2. Libraries

**Added**: [lib/dashboard.sh](lib/dashboard.sh)

**Functions**:
- `setup_system_dashboard()` - Main installation function
- `install_dashboard_to_deployment()` - Wrapper for Phase 8 integration

**Loaded**: Automatically in [nixos-quick-deploy.sh](/nixos-quick-deploy.sh#L234) library list

### 3. Scripts

**Current Authoritative Components**:
- [nix/modules/services/command-center-dashboard.nix](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/services/command-center-dashboard.nix) - declarative dashboard runtime
- [dashboard/backend/api/main.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard/backend/api/main.py) - API + SPA serving
- [dashboard.html](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html) - served operator UI

Legacy scripts mentioned elsewhere in this document are compatibility or historical references only.

---

## Post-Deployment

### Automatic Setup

After deployment completes, users will see:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 System Dashboard Installed!

Quick Start Options:

1. Declarative runtime:
   systemctl status command-center-dashboard-api.service
   xdg-open http://127.0.0.1:8889/

2. API health:
   curl http://127.0.0.1:8889/api/health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Created Resources

**Current Runtime Service**:
- `command-center-dashboard-api.service` - unified operator UI + API service

**Data Directory**: `~/.local/share/nixos-system-dashboard/`
- system.json - CPU, memory, disk, uptime
- llm.json - AI stack services
- network.json - Network & firewall
- security.json - Security metrics
- database.json - PostgreSQL stats
- links.json - Quick access links

**Desktop Launcher**: `~/.local/share/applications/nixos-dashboard.desktop`

**Legacy Shell Aliases** (historical references only):
```bash
alias dashboard='cd /path/to/deploy && ./scripts/deploy/launch-dashboard.sh'
alias dashboard-start='systemctl --user start dashboard-collector.timer dashboard-server.service'
alias dashboard-stop='systemctl --user stop dashboard-collector.timer dashboard-server.service'
alias dashboard-status='systemctl --user status dashboard-collector.timer dashboard-server.service'
```

---

## User Actions Required

### None (Fully Automated)

The dashboard is installed and configured automatically. Users can:

**Option 1: Start Immediately**
```bash
dashboard  # If shell reloaded, or:
./scripts/deploy/launch-dashboard.sh
```

**Option 2: Start as Service**
```bash
systemctl --user start dashboard-server
systemctl --user start dashboard-collector.timer
```

**Option 3: Enable Auto-Start on Boot**
```bash
systemctl --user enable dashboard-server
systemctl --user enable dashboard-collector.timer
```

---

## Deployment Testing

### Test Dashboard Installation

To verify integration works correctly:

```bash
# Run build-only validation (no live switch)
./nixos-quick-deploy.sh --build-only

# Check Phase 8 logs for dashboard installation
grep -A 20 "Step 8.5: System Monitoring Dashboard" ~/.cache/nixos-quick-deploy/logs/*.log

# Verify setup script was called
grep "Installing System Command Center Dashboard" ~/.cache/nixos-quick-deploy/logs/*.log
```

### Manual Installation Test

To test dashboard installation separately:

```bash
# Run setup script directly
./scripts/deploy/setup-dashboard.sh

# Verify systemd services created
systemctl --user list-unit-files | grep dashboard

# Check data generation
ls -la ~/.local/share/nixos-system-dashboard/
```

---

## Configuration Options

### Disable Dashboard Installation

If you want to skip dashboard installation during deployment:

**Method 1: Environment Variable**
```bash
export SKIP_DASHBOARD_INSTALL=true
./nixos-quick-deploy.sh
```

**Method 2: Edit Phase 8**
Comment out Step 8.5 in [phases/phase-08-finalization-and-report.sh](phases/phase-08-finalization-and-report.sh#L173-L183)

### Customize Dashboard Port

The authoritative dashboard port is managed declaratively. To change it, update the Nix options for the command center service rather than editing helper scripts.

**After changing Nix configuration**:
```bash
sudo nixos-rebuild switch --flake .#$(hostname)
systemctl restart command-center-dashboard-api.service
```

### Disable Auto-Collection

To prevent automatic data collection:

```bash
# Disable timer
systemctl --user disable dashboard-collector.timer
systemctl --user stop dashboard-collector.timer

# Manual collection when needed
./scripts/data/generate-dashboard-data.sh
```

---

## Troubleshooting Deployment Integration

### Dashboard Not Installed

**Check Phase 8 Logs**:
```bash
# View deployment log
tail -100 ~/.cache/nixos-quick-deploy/logs/deploy-*.log | grep -A 20 "Dashboard"
```

**Common Issues**:
1. **Library not loaded**: Check `load_libraries()` includes "dashboard.sh"
2. **Setup script not found**: Verify [scripts/deploy/setup-dashboard.sh](/scripts/deploy/setup-dashboard.sh) exists and is executable
3. **Permission errors**: Ensure `~/.local/share` and `~/.config/systemd/user` are writable

### Dashboard Installed but Not Working

**Verify Installation**:
```bash
# Check systemd services exist
systemctl --user list-unit-files | grep dashboard

# Check data directory
ls -la ~/.local/share/nixos-system-dashboard/

# Check aliases added
grep "dashboard" ~/.zshrc
```

**Test Manually**:
```bash
# Check service
systemctl status command-center-dashboard-api.service

# Check API
curl http://127.0.0.1:8889/api/health

# Open dashboard
xdg-open http://127.0.0.1:8889/
```

---

## Rollback / Removal

### Uninstall Dashboard

```bash
# Stop declarative runtime
systemctl stop command-center-dashboard-api.service

# Revert dashboard-related configuration through Nix and rebuild
sudo nixos-rebuild switch --flake .#$(hostname)

# Remove data directory
rm -rf ~/.local/share/nixos-system-dashboard

# Remove desktop launcher
rm ~/.local/share/applications/nixos-dashboard.desktop

# Remove aliases from shell config
sed -i '/# NixOS System Dashboard/,+4d' ~/.zshrc

# Reload systemd
systemctl --user daemon-reload
```

---

## Future Enhancements

### Planned Features

1. **NixOS Module Integration**
   - Add as optional NixOS module in [templates/](templates/)
   - Enable with `services.nixos-dashboard.enable = true`

2. **Configuration File**
   - JSON config for customization
   - Dashboard port, refresh rate, theme selection

3. **Multi-Host Support**
   - Monitor multiple NixOS machines from one dashboard
   - Aggregated metrics and health scores

4. **Prometheus Integration**
   - Export metrics for long-term storage
   - Grafana dashboard compatibility

5. **Alert Configuration**
   - Custom thresholds for notifications
   - Email/webhook alerts for critical issues

---

## Documentation

### For Users

- **Quick Start**: [DASHBOARD-QUICKSTART.md]/docs/archive/stubs/DASHBOARD-QUICKSTART.md
- **Complete Guide**: [SYSTEM-DASHBOARD-GUIDE.md]/docs/archive/stubs/SYSTEM-DASHBOARD-GUIDE.md

### For Developers

- **Library Code**: [lib/dashboard.sh](lib/dashboard.sh)
- **Setup Script**: [scripts/deploy/setup-dashboard.sh](/scripts/deploy/setup-dashboard.sh)
- **Phase Integration**: [phases/phase-08-finalization-and-report.sh](phases/phase-08-finalization-and-report.sh#L173-L183)

---

## Version History

### 1.0.0 (2025-12-21)
- ✅ Initial integration into NixOS Quick Deploy
- ✅ Automatic installation in Phase 8
- ✅ Systemd service creation
- ✅ Desktop launcher support
- ✅ Shell alias configuration
- ✅ Non-fatal error handling
- ✅ Complete documentation

---

## Summary

The System Command Center Dashboard is now a **standard component** of every NixOS Quick Deploy installation:

✅ **Automatic Installation** - No user action required
✅ **Non-Breaking** - Deployment continues if dashboard fails
✅ **Full Documentation** - Complete guides and troubleshooting
✅ **Production Ready** - Tested and integrated
✅ **User Friendly** - Multiple launch options and clear instructions

Every new NixOS system deployed with this script will have real-time monitoring capabilities from day one!

---

**Integration Status**: ✅ Complete
**Testing Status**: ✅ Verified
**Documentation**: ✅ Comprehensive
**Production Ready**: ✅ Yes
