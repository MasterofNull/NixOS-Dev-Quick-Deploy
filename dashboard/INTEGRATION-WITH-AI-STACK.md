# Dashboard Integration with AI Stack Monitor

**Date:** December 31, 2025
**Version:** 2.0.0

---

## Overview

This document describes the integration between the **NixOS System Dashboard v2.0** (web-based, port 8890) and the **AI Stack Monitor** (CLI-based, [scripts/ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh)).

---

## Two Monitoring Tools - Complementary Approaches

### 1. **NixOS System Dashboard** (Web UI)
**Port:** 8890 (Frontend) + 8889 (Backend API)
**Location:** [dashboard/](.)
**Start:** `./dashboard/start-dashboard.sh`

**Features:**
- ✅ Real-time WebSocket metrics (2-second updates)
- ✅ Interactive charts with historical data
- ✅ Service start/stop/restart controls
- ✅ Container management UI
- ✅ Health score calculation
- ✅ Modern React+TypeScript UI
- ✅ GPU monitoring
- ✅ Container resource stats

**Best for:**
- Long-term monitoring sessions
- Interactive control of services
- Visual data analysis with charts
- Remote access (via browser)
- Multi-panel dashboards

---

### 2. **AI Stack Monitor** (CLI Dashboard)
**Location:** [scripts/ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh)
**Start:** `./scripts/ai-stack-monitor.sh`

**Features:**
- ✅ Terminal-based real-time display
- ✅ 5-second refresh rate
- ✅ Container status at-a-glance
- ✅ CPU and Memory per container
- ✅ llama.cpp metrics endpoint integration
- ✅ Color-coded status indicators
- ✅ No browser required

**Best for:**
- Quick health checks
- SSH/terminal-only access
- tmux/screen persistent monitoring
- Low resource overhead
- Integration with terminal multiplexers

---

## Integration Points

### Shared Data Sources

Both tools monitor the same AI stack services:

| Service | Container Name | Port | Dashboard | CLI Monitor |
|---------|----------------|------|-----------|-------------|
| llama.cpp | local-ai-llama-cpp | 8080 | ✅ | ✅ |
| Qdrant | local-ai-qdrant | 6333 | ✅ | ✅ |
| Redis | local-ai-redis | 6379 | ✅ | ✅ |
| PostgreSQL | local-ai-postgres | 5432 | ✅ | ✅ |
| AIDB MCP | local-ai-aidb | 8091 | ✅ | ✅ |
| Hybrid Coordinator | local-ai-hybrid-coordinator | 8092 | ✅ | ✅ |
| **NixOS Docs** | **local-ai-nixos-docs** | **8094** | **✅** | **✅** |
| **Ralph Wiggum** | **local-ai-ralph-wiggum** | **8093** | **✅** | **✅** |
| Health Monitor | local-ai-health-monitor | 8095 | ✅ | ✅ |
| Open WebUI | local-ai-open-webui | 3001 | ✅ | ❌ |
| MindsDB | local-ai-mindsdb | 47334 | ✅ | ❌ |

---

## Recent Updates

### December 31, 2025 - AI Stack Integration

#### Dashboard Backend Updates

**File:** [backend/api/services/service_manager.py](backend/api/services/service_manager.py:13-30)

**Changes:**
- Added `nixos-docs` MCP server monitoring
- Added `ralph-wiggum` MCP server monitoring
- Added `health-monitor` service
- Reorganized services into categories (Core, MCP, UI)
- Changed `postgresql` to `postgres` for consistency

**Before:**
```python
MONITORED_SERVICES = [
    "qdrant",
    "postgresql",
    "redis",
    "aidb-mcp",
    "llama-cpp",
    "open-webui",
    "mindsdb",
]
```

**After:**
```python
MONITORED_SERVICES = [
    # Core AI Stack Services
    "llama-cpp",
    "qdrant",
    "redis",
    "postgres",

    # MCP Servers
    "aidb",
    "hybrid-coordinator",
    "nixos-docs",
    "ralph-wiggum",
    "health-monitor",

    # UI & Additional Services
    "open-webui",
    "mindsdb",
]
```

#### Dashboard Metrics Enhancement

**File:** [backend/api/services/metrics_collector.py](backend/api/services/metrics_collector.py:139-183)

**Changes:**
- Added `get_container_stats()` method
- Collects CPU, Memory, Network, Disk stats per container
- Returns container count and running list
- Integrated into main metrics endpoint

**New Metrics:**
```python
{
    "containers": {
        "count": 12,
        "running": ["local-ai-llama-cpp", "local-ai-nixos-docs", ...],
        "stats": {
            "local-ai-nixos-docs": {
                "cpu": "2.5%",
                "memory": "512MB / 4GB",
                "network": "1.2kB / 800B",
                "disk": "10MB / 5MB"
            },
            ...
        }
    }
}
```

#### CLI Monitor Updates

**File:** [scripts/ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh:39-40)

**Changes:**
- Added `local-ai-nixos-docs` to MCP Servers section
- Added `local-ai-ralph-wiggum` to MCP Servers section

---

## Auto-Start Configuration

### After NixOS Quick Deploy

Both tools are now integrated into the deployment completion:

**File:** [nixos-quick-deploy.sh](../nixos-quick-deploy.sh:1360-1367)

**What happens:**
1. Deployment completes successfully
2. User sees: "AI Stack Monitor Dashboard available at: ./scripts/ai-stack-monitor.sh"
3. User can immediately run CLI monitor OR web dashboard

**To start web dashboard after deployment:**
```bash
cd dashboard
./start-dashboard.sh
```

**To start CLI monitor after deployment:**
```bash
./scripts/ai-stack-monitor.sh
```

---

### After System Reboot

#### Web Dashboard Auto-Start (Optional)

**Option 1: Systemd User Service**

Create: `~/.config/systemd/user/dashboard.service`

```ini
[Unit]
Description=NixOS System Dashboard
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/dashboard
ExecStart=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/dashboard/start-dashboard.sh
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=default.target
```

**Enable:**
```bash
systemctl --user enable dashboard.service
systemctl --user start dashboard.service
loginctl enable-linger $USER
```

**Option 2: tmux Session**

Add to `~/.bashrc`:
```bash
# Auto-start dashboard in background tmux session
if command -v tmux &>/dev/null && [[ -z "$TMUX" ]]; then
  if ! tmux has-session -t dashboard 2>/dev/null; then
    tmux new-session -d -s dashboard \
      'cd ~/Documents/try/NixOS-Dev-Quick-Deploy/dashboard && ./start-dashboard.sh'
  fi
fi
```

**Access:**
```bash
tmux attach -t dashboard  # View dashboard terminal
# Or just visit: http://localhost:8890
```

---

#### CLI Monitor Auto-Start (Optional)

**Option 1: tmux Session** (Recommended)

Add to `~/.bashrc`:
```bash
# Auto-start CLI monitor in tmux
if command -v tmux &>/dev/null && [[ -z "$TMUX" ]]; then
  if ! tmux has-session -t ai-monitor 2>/dev/null; then
    tmux new-session -d -s ai-monitor \
      '/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-monitor.sh'
  fi
fi
```

**Access:**
```bash
tmux attach -t ai-monitor
```

**Option 2: Systemd User Service**

Create: `~/.config/systemd/user/ai-stack-monitor.service`

Already defined in [templates/nixos-improvements/ai-stack-autostart.nix](../templates/nixos-improvements/ai-stack-autostart.nix:87-97)

**Enable:**
```bash
systemctl --user enable ai-stack-monitor.service
systemctl --user start ai-stack-monitor.service
```

---

## Usage Recommendations

### When to Use Each Tool

| Scenario | Web Dashboard | CLI Monitor |
|----------|---------------|-------------|
| **Initial setup** | ✅ Best | ✅ Good |
| **Daily monitoring** | ✅ Best (interactive) | ✅ Good (quick check) |
| **Troubleshooting** | ✅ Best (logs, restart) | ⚠️ Status only |
| **SSH-only access** | ❌ Requires port forward | ✅ Perfect |
| **tmux workflow** | ❌ | ✅ Perfect |
| **Remote monitoring** | ✅ Perfect | ❌ |
| **Service control** | ✅ GUI buttons | ❌ Manual |
| **Historical data** | ✅ Charts (100 points) | ❌ Current only |
| **Resource usage** | ⚠️ Higher (Node+Python) | ✅ Minimal (bash) |

---

## Combined Workflow Example

### Scenario: Monitor AI stack during development

**Step 1:** Start web dashboard (persistent monitoring)
```bash
cd dashboard
./start-dashboard.sh
# Leave running in terminal or tmux
```

**Step 2:** Open browser
```
http://localhost:8890
```

**Step 3:** Start CLI monitor in tmux (quick reference)
```bash
tmux new-session -s monitor
./scripts/ai-stack-monitor.sh
# Detach: Ctrl+B, D
```

**Step 4:** Work on your project

**Step 5:** Quick check via CLI
```bash
tmux attach -t monitor  # See instant status
```

**Step 6:** Detailed analysis via Web
```
# Open browser, view charts, restart services as needed
```

---

## API Endpoints (Dashboard Backend)

### Metrics
```bash
# Current system metrics (includes container stats)
curl http://localhost:8889/api/metrics/system

# Health score
curl http://localhost:8889/api/metrics/health-score
```

### Services
```bash
# List all monitored services
curl http://localhost:8889/api/services

# Start nixos-docs MCP server
curl -X POST http://localhost:8889/api/services/nixos-docs/start

# Restart llama-cpp
curl -X POST http://localhost:8889/api/services/llama-cpp/restart
```

### Containers
```bash
# List all containers
curl http://localhost:8889/api/containers

# Get nixos-docs logs
curl http://localhost:8889/api/containers/local-ai-nixos-docs/logs
```

### WebSocket (Real-time)
```javascript
// Connect to metrics stream
const ws = new WebSocket('ws://localhost:8889/ws/metrics');
ws.onmessage = (event) => {
  const metrics = JSON.parse(event.data);
  console.log(metrics.containers.stats['local-ai-nixos-docs']);
};
```

---

## Architecture Comparison

### Web Dashboard Architecture
```
┌──────────────────────────────────────────┐
│  Browser (http://localhost:8890)         │
│  React 19 + TypeScript + shadcn/ui       │
└────────────────┬─────────────────────────┘
                 │ HTTP + WebSocket
                 ▼
┌──────────────────────────────────────────┐
│  Backend API (port 8889)                 │
│  FastAPI + Uvicorn + psutil              │
└────────────────┬─────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌─────────────┐  ┌──────────────────┐
│   podman    │  │   systemctl      │
│  (stats)    │  │  (services)      │
└─────────────┘  └──────────────────┘
```

### CLI Monitor Architecture
```
┌──────────────────────────────────────────┐
│  Terminal (scripts/ai-stack-monitor.sh)  │
│  Bash + podman ps + podman stats         │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  podman CLI + curl (llama.cpp metrics)   │
└──────────────────────────────────────────┘
```

---

## Troubleshooting

### Web Dashboard Not Showing Containers

**Symptom:** Dashboard shows "0 containers" but `podman ps` shows containers running

**Solution:**
```bash
# Check backend can access podman
cd dashboard/backend
source venv/bin/activate
python3 -c "import subprocess; print(subprocess.run(['podman', 'ps'], capture_output=True, text=True).stdout)"

# Check backend logs
curl http://localhost:8889/api/metrics/system | jq '.containers'
```

### Services Not Starting from Dashboard

**Symptom:** Click "Start" button but service doesn't start

**Solution:**
1. Check if service_id matches container name pattern
2. Verify podman command works manually:
```bash
podman start local-ai-nixos-docs
```
3. Check backend logs for errors

### CLI Monitor Not Showing New Services

**Symptom:** `nixos-docs` or `ralph-wiggum` not visible

**Solution:**
```bash
# Verify script was updated
grep -c "nixos-docs" scripts/ai-stack-monitor.sh  # Should be > 0

# Check container is actually running
podman ps --filter name=local-ai-nixos-docs
```

---

## Future Enhancements

### Planned Integrations

1. **Unified Health API**
   - Single endpoint that combines dashboard metrics + CLI checks
   - Expose via HTTP for remote monitoring

2. **Shared Configuration**
   - Both tools read from common config file
   - Add/remove services in one place

3. **Alert System**
   - Dashboard triggers alerts
   - CLI monitor shows notification badge

4. **Container Logs Viewer**
   - Dashboard: Real-time log streaming (WebSocket)
   - CLI: tail -f equivalent

5. **MCP Server Status**
   - Dashboard: Test MCP endpoints (/health for each)
   - CLI: Show MCP-specific metrics (cache hits, requests/sec)

---

## Summary

| Aspect | Web Dashboard | CLI Monitor |
|--------|---------------|-------------|
| **Services Monitored** | 12 (all AI stack) | 9 (core + MCP) |
| **nixos-docs** | ✅ Added | ✅ Added |
| **ralph-wiggum** | ✅ Added | ✅ Added |
| **Container Stats** | ✅ CPU, Mem, Net, Disk | ✅ CPU, Mem |
| **Interactive Control** | ✅ Yes | ❌ No |
| **Auto-Start** | ✅ Optional (systemd/tmux) | ✅ Optional (systemd/tmux) |
| **Integration** | ✅ Complete | ✅ Complete |

---

**Status:** ✅ Fully Integrated
**Last Updated:** December 31, 2025
**Maintained By:** NixOS Dev Quick Deploy Team

**Quick Links:**
- [Main Dashboard README](README.md)
- [AI Stack Auto-Start Guide](../ai-stack/AUTO-START-GUIDE.md)
- [CLI Monitor Script](../scripts/ai-stack-monitor.sh)
- [Auto-Start NixOS Module](../templates/nixos-improvements/ai-stack-autostart.nix)
