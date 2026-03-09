# Dashboard Collectors Guide

**Version**: 2.0.0
**Created**: 2025-12-22
**Status**: Dual-collector system with optimized update rates

## Overview

The system dashboard uses **two separate collectors** to optimize performance:

1. **Lite Collector** - Fast-changing metrics (system + network)
2. **Full Collector** - Static/slow-changing metrics (LLM, database, security, etc.)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Dashboard UI (browser)                 │
│  - Polls system/network every 2s                        │
│  - Polls all data every 60s                             │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │ Reads JSON files
                            │
┌─────────────────────────────────────────────────────────┐
│              ~/.local/share/nixos-system-dashboard/     │
│                                                          │
│  ┌──────────────────┐      ┌─────────────────────────┐ │
│  │ Fast-changing:   │      │ Slow-changing:          │ │
│  │ - system.json    │      │ - llm.json              │ │
│  │ - network.json   │      │ - database.json         │ │
│  │ (every ~2.5s)    │      │ - security.json         │ │
│  └──────────────────┘      │ - telemetry.json        │ │
│                            │ - feedback.json         │ │
│                            │ - config.json           │ │
│                            │ (every ~69s)            │ │
│                            └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │ Writes JSON
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────▼────────────┐              ┌──────────▼──────────┐
│  Lite Collector    │              │  Full Collector     │
│  (PID 161811)      │              │  (PID 162629)       │
│                    │              │                     │
│  Cycle: ~2.5s      │              │  Cycle: ~69s        │
│  - Run: 0.5s       │              │  - Run: 9s          │
│  - Sleep: 2s       │              │  - Sleep: 60s       │
│                    │              │                     │
│  Collects:         │              │  Collects:          │
│  - CPU usage       │              │  - LLM metrics      │
│  - Memory stats    │              │  - Database status  │
│  - Disk I/O        │              │  - Security data    │
│  - Network traffic │              │  - Telemetry        │
│  - Top processes   │              │  - Learning data    │
│                    │              │  - RAG collections  │
└────────────────────┘              └─────────────────────┘
```

## Quick Commands

```bash
# Manage collectors
bash scripts/governance/manage-dashboard-collectors.sh start    # Start both
bash scripts/governance/manage-dashboard-collectors.sh stop     # Stop both
bash scripts/governance/manage-dashboard-collectors.sh restart  # Restart both
bash scripts/governance/manage-dashboard-collectors.sh status   # Check status
bash scripts/governance/manage-dashboard-collectors.sh logs     # View logs

# Manual collection (for testing)
bash scripts/data/generate-dashboard-data-lite.sh   # Only system + network
bash scripts/data/generate-dashboard-data.sh        # Full collection
```

## Performance Metrics

### Lite Collector
- **Execution time**: ~0.5 seconds
- **Sleep interval**: 2 seconds
- **Total cycle**: ~2.5 seconds
- **Metrics collected**: 2 JSON files (system, network)
- **Data size**: ~15 KB total

### Full Collector
- **Execution time**: ~9 seconds
- **Sleep interval**: 60 seconds
- **Total cycle**: ~69 seconds
- **Metrics collected**: 13 JSON files (all)
- **Data size**: ~150 KB total

## Dashboard Update Rates

The dashboard UI in [dashboard.html](dashboard.html) uses two update intervals:

```javascript
setInterval(loadSystemMetricsOnly, 2000);  // Graphs update every 2s
setInterval(loadData, 60000);              // Full data every 60s
```

This matches the GNOME Resources monitor's 1-second update rate while being efficient with system resources.

## Files

### Collection Scripts

- [scripts/data/generate-dashboard-data.sh](/scripts/data/generate-dashboard-data.sh)
  - Main data collection script
  - Supports `--lite-mode` flag for fast collection
  - Default: Collects all metrics

- [scripts/data/generate-dashboard-data-lite.sh](/scripts/data/generate-dashboard-data-lite.sh)
  - Wrapper that calls main script with `--lite-mode`
  - Only collects system and network metrics

### Runtime Ownership

- [scripts/governance/manage-dashboard-collectors.sh](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/governance/manage-dashboard-collectors.sh)
  - Supported operator interface for collector lifecycle and logs
  - Owns any runtime loop scripts or temporary files it may create internally
  - Temporary files under `${TMPDIR:-/tmp}` are implementation details, not stable operator entrypoints

### Management Script

- [scripts/governance/manage-dashboard-collectors.sh](/scripts/governance/manage-dashboard-collectors.sh)
  - Unified manager for both collectors
  - Commands: start, stop, restart, status, logs

## Lock Files

The collection scripts use `flock` to prevent concurrent execution:

```bash
exec 9>"$DATA_DIR/.lock"
flock -n 9 || exit 1
```

This prevents the lite and full collectors from running simultaneously and corrupting data.

## Troubleshooting

### Collectors not running

```bash
# Check process status
bash scripts/governance/manage-dashboard-collectors.sh status

# Start if stopped
bash scripts/governance/manage-dashboard-collectors.sh start
```

### Dashboard graphs not updating

```bash
# Check data freshness
ls -lh ~/.local/share/nixos-system-dashboard/*.json

# Restart collectors
bash scripts/governance/manage-dashboard-collectors.sh restart
```

### Lock file conflicts

```bash
# Remove stale locks
rm -f ~/.local/share/nixos-system-dashboard/.lock

# Restart collectors
bash scripts/governance/manage-dashboard-collectors.sh restart
```

### High CPU usage

```bash
# Check collector logs
bash scripts/governance/manage-dashboard-collectors.sh logs

# If this persists, prefer changing the supported collector scripts or
# declarative dashboard runtime rather than editing temporary files.
# The first supported step is to review:
# - scripts/data/generate-dashboard-data.sh
# - scripts/data/generate-dashboard-data-lite.sh
# - scripts/governance/manage-dashboard-collectors.sh
```

## System Resources

### CPU Usage
- **Lite collector**: ~0.5% average (0.5s CPU every 2.5s)
- **Full collector**: ~1.5% average (9s CPU every 69s)
- **Combined**: ~2% average CPU usage

### Disk I/O
- **Lite writes**: ~6 KB/s (15 KB every 2.5s)
- **Full writes**: ~2 KB/s (150 KB every 69s)
- **Combined**: ~8 KB/s sustained

### Memory Usage
- Each collector: ~4 MB RAM
- Data directory: ~200 KB total

## Integration with System

### Auto-start on Boot

Prefer the declarative command center dashboard service over ad-hoc collector
service wrappers. If you need boot-time dashboard behavior, enable or inspect:

```bash
systemctl status command-center-dashboard-api.service
```

Historical examples of custom user services around collector loops are legacy
implementation context, not the recommended deployment model.

### Dashboard Runtime

The authoritative production dashboard runtime is the declarative command center service:

```bash
systemctl status command-center-dashboard-api.service
xdg-open http://127.0.0.1:8889/
```

Historical collector/server flows described in this document are legacy implementation context, not the current deployment model.

## Related Documentation

- [SYSTEM-DASHBOARD-GUIDE.md]/docs/archive/stubs/SYSTEM-DASHBOARD-GUIDE.md - Complete dashboard guide
- [SYSTEM-DASHBOARD-README.md]/docs/archive/stubs/SYSTEM-DASHBOARD-README.md - Dashboard overview
- [scripts/data/generate-dashboard-data.sh](/scripts/data/generate-dashboard-data.sh) - Main collection script

## Change Log

### Version 2.0.0 (2025-12-22)
- Split collection into dual-collector architecture
- Lite collector: 2.5s cycle for system + network
- Full collector: 69s cycle for all other metrics
- Dashboard update rates: 2s for graphs, 60s for full data
- Added `manage-dashboard-collectors.sh` management script
- Performance improvement: ~4x faster graph updates

### Version 1.0.0 (2025-12-21)
- Initial single-collector implementation
- 19s cycle for all metrics
- Dashboard update rates: 5s for graphs, 30s for full data
