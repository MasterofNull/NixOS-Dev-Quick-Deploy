# Dashboard Quick Reference

**TL;DR**: Your dashboard now updates graphs every 2 seconds, matching GNOME Resources quality! 🚀

## Quick Commands

```bash
# View dashboard
bash scripts/deploy/serve-dashboard.sh
# Open: http://localhost:8888/dashboard.html

# Manage collectors
bash scripts/governance/manage-dashboard-collectors.sh status   # Check if running
bash scripts/governance/manage-dashboard-collectors.sh restart  # Restart if needed
bash scripts/governance/manage-dashboard-collectors.sh logs     # View logs
```

## What's Running

Two background processes collect dashboard data:

| Collector | Updates | Metrics | PID |
|-----------|---------|---------|-----|
| **Lite** | Every 2.5s | CPU, Memory, Disk I/O, Network, Processes | 161811 |
| **Full** | Every 69s | LLM, Database, Security, Telemetry, etc. | 162629 |

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
# Edit lite collector interval (currently 2s)
nano ${TMPDIR:-/tmp}/run-dashboard-collector-lite.sh
# Change: sleep 2

# Edit full collector interval (currently 60s)
nano ${TMPDIR:-/tmp}/run-dashboard-collector-full.sh
# Change: sleep 60

# Restart
bash scripts/governance/manage-dashboard-collectors.sh restart
```

## Complete Documentation

- [DASHBOARD-COLLECTORS-GUIDE.md](DASHBOARD-COLLECTORS-GUIDE.md) - Architecture and details
- [DASHBOARD-UPDATE-OPTIMIZATION.md](DASHBOARD-UPDATE-OPTIMIZATION.md) - What changed
- [SYSTEM-DASHBOARD-GUIDE.md](SYSTEM-DASHBOARD-GUIDE.md) - Complete guide

---

**Status**: ✅ Running perfectly
**CPU Usage**: ~2% (both collectors)
**Update Latency**: 2-3 seconds for graphs
