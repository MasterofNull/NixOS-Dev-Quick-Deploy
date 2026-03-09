# Dashboard Quick Reference

**TL;DR**: The production command center is the declarative dashboard service on `http://127.0.0.1:8889/`. Collector timing notes below are historical implementation context for the HTML dashboard path.

## Quick Commands

```bash
# View dashboard
systemctl status command-center-dashboard-api.service
xdg-open http://127.0.0.1:8889/

# Legacy collector management context
bash scripts/governance/manage-dashboard-collectors.sh status   # Check if running
bash scripts/governance/manage-dashboard-collectors.sh restart  # Restart if needed
bash scripts/governance/manage-dashboard-collectors.sh logs     # View logs
```

## What's Running

The supported operator view is:

```bash
systemctl status command-center-dashboard-api.service
bash scripts/governance/manage-dashboard-collectors.sh status
```

Collector PIDs are intentionally omitted here because they change every restart.

## Dashboard Update Rates

- **Graphs** (CPU, Memory, Network): Update every **2 seconds** ✨
- **Static Data** (services, config): Update every **60 seconds**

## System Metrics (GNOME Resources Quality)

Your dashboard now shows:

✅ **Per-core CPU usage** (all 16 cores individually)
✅ **CPU frequency** (current/min/max GHz)
✅ **Memory details** (used/cached/buffers/swap)
✅ **Disk I/O rates** (MB/s read/write)
✅ **Network traffic** (TX/RX rates)
✅ **Top processes** (by CPU usage)

## Troubleshooting

### Graphs not updating?

```bash
# Check collectors
bash scripts/governance/manage-dashboard-collectors.sh status

# Restart if needed
bash scripts/governance/manage-dashboard-collectors.sh restart
```

### Want different update rates?

```bash
# Supported paths to review or adjust:
bash scripts/governance/manage-dashboard-collectors.sh logs
sed -n '1,120p' scripts/data/generate-dashboard-data.sh
sed -n '1,120p' scripts/data/generate-dashboard-data-lite.sh

# After changes, restart:
bash scripts/governance/manage-dashboard-collectors.sh restart
```

### Need local-vs-remote AI visibility?

```bash
bash scripts/observability/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq '.effectiveness'
scripts/ai/aq-report --since=7d --format=text
```

## Complete Documentation

- [docs/operations/DASHBOARD-ARCHITECTURE-REFERENCE.md](operations/DASHBOARD-ARCHITECTURE-REFERENCE.md) - Supported runtime, collector, and AI observability boundaries
- [DASHBOARD-COLLECTORS-GUIDE.md](DASHBOARD-COLLECTORS-GUIDE.md) - Architecture and details
- [DASHBOARD-UPDATE-OPTIMIZATION.md](DASHBOARD-UPDATE-OPTIMIZATION.md) - What changed
- [SYSTEM-DASHBOARD-GUIDE.md]/docs/archive/stubs/SYSTEM-DASHBOARD-GUIDE.md - Complete guide

---

**Status**: Check `systemctl status command-center-dashboard-api.service`
**AI Metrics Cache**: `~/.local/share/nixos-system-dashboard/ai_metrics.json`
**Routing Summary**: `scripts/ai/aq-report --since=7d --format=text`
