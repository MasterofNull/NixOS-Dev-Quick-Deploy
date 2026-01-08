# 🚀 AI STACK AUTO-START CONFIGURATION GUIDE
**Date**: December 31, 2025
**Status**: ✅ **CONFIGURED AND ENABLED**

---

## 📋 OVERVIEW

The AI Stack now automatically starts on system boot with all components:
- ✅ Core infrastructure (Postgres, Redis, Qdrant, llama.cpp, MindsDB)
- ✅ MCP services (AIDB, Hybrid Coordinator, Health Monitor)
- ✅ Qdrant vector collections (auto-initialized if missing)
- ✅ Dashboard monitoring (server + collectors)

---

## 🔧 CONFIGURATION FILES

### **1. Startup Script**
**Location**: `~/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-startup.sh`

**Features:**
- Network connectivity check
- Podman availability verification
- Sequential service startup (core → MCP → dashboard)
- Health checks for all services
- Qdrant collection auto-initialization
- Comprehensive logging
- Startup report generation

**Startup Sequence:**
1. Wait for network (max 60s)
2. Wait for Podman (max 60s)
3. Start core infrastructure (Postgres, Redis, Qdrant, llama.cpp, MindsDB)
4. Wait 30s for initialization
5. Start MCP services (AIDB, Hybrid Coordinator, Health Monitor)
6. Wait 20s for MCP initialization
7. Check/initialize Qdrant collections (5 collections)
8. Start dashboard services
9. Collect initial metrics
10. Run comprehensive health checks
11. Generate startup report

### **2. Systemd Service**
**Location**: `~/.config/systemd/user/ai-stack-startup.service`

**Configuration:**
```ini
[Unit]
Description=AI Stack Automatic Startup Service
After=network-online.target podman.socket
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=%h/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-startup.sh
TimeoutStartSec=300
Restart=no

[Install]
WantedBy=default.target
```

**Service Type**: OneShot (runs once at startup, remains active)
**Timeout**: 5 minutes (300 seconds)
**Dependencies**: Network online, Podman socket

---

## ✅ ENABLED SERVICES

The following systemd user services are now enabled for auto-start:

### **AI Stack Services:**
1. ✅ **ai-stack-startup.service** - Main startup orchestrator
2. ✅ **dashboard-server.service** - Dashboard HTTP server (port 8888)
3. ✅ **dashboard-collector.timer** - Metrics collection (every 15s)
4. ✅ **dashboard-collector.service** - Metrics collector service

### **User Lingering:**
✅ **Enabled** - User services start even when user not logged in

---

## 🎯 WHAT STARTS AUTOMATICALLY

### **On System Boot:**

**Phase 1: Core Infrastructure (30s wait)**
- local-ai-postgres (PostgreSQL with pgvector)
- local-ai-redis (Redis cache)
- local-ai-qdrant (Vector database)
- local-ai-llama-cpp (LLM inference)
- local-ai-mindsdb (Analytics)

**Phase 2: MCP Services (20s wait)**
- local-ai-aidb (MCP server + tool discovery)
- local-ai-hybrid-coordinator (Continuous learning)
- local-ai-health-monitor (Self-healing)

**Phase 3: Vector Collections (if needed)**
- codebase-context
- skills-patterns
- error-solutions
- interaction-history
- best-practices

**Phase 4: Dashboard**
- dashboard-server.service
- dashboard-collector.timer
- Initial metrics collection

**Phase 5: Health Checks**
- Container status verification
- Service endpoint checks
- Health check summary
- Startup report generation

---

## 📊 MONITORING STARTUP

### **Check Service Status:**
```bash
# Main startup service
systemctl --user status ai-stack-startup.service

# Dashboard services
systemctl --user status dashboard-server.service
systemctl --user status dashboard-collector.timer

# View startup logs
journalctl --user -u ai-stack-startup.service -b

# Latest startup log file
ls -lt ~/.cache/nixos-quick-deploy/logs/ai-stack-startup-*.log | head -1

# View startup report
ls -lt ~/.local/share/nixos-ai-stack/startup-report-*.txt | head -1
```

### **Check Container Status:**
```bash
# All AI containers
podman ps | grep local-ai

# Container health
podman ps --format "table {{.Names}}\t{{.Status}}"

# Resource usage
podman stats --no-stream | grep local-ai
```

### **Check Service Health:**
```bash
# AIDB
curl http://localhost:8091/health | jq

# Hybrid Coordinator
curl http://localhost:8092/health | jq

# Qdrant
curl http://localhost:6333/collections | jq

# llama.cpp
curl http://localhost:8080/health | jq

# Dashboard
curl http://localhost:8888/data/ai_metrics.json | jq
```

---

## 🔧 MANAGEMENT COMMANDS

### **Manual Control:**
```bash
# Start AI stack manually (if not auto-started)
systemctl --user start ai-stack-startup.service

# Stop all AI services
cd ~/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose down

# Restart AI stack
systemctl --user restart ai-stack-startup.service

# Check what will start on boot
systemctl --user list-unit-files | grep enabled | grep -E "(ai-stack|dashboard)"
```

### **Enable/Disable Auto-Start:**
```bash
# Disable auto-start
systemctl --user disable ai-stack-startup.service

# Re-enable auto-start
systemctl --user enable ai-stack-startup.service

# Disable lingering (services won't start until login)
loginctl disable-linger $USER

# Re-enable lingering
loginctl enable-linger $USER
```

### **Dashboard Management:**
```bash
# Restart dashboard server
systemctl --user restart dashboard-server.service

# Restart metrics collector
systemctl --user restart dashboard-collector.timer

# Force metrics update
cd ~/Documents/try/NixOS-Dev-Quick-Deploy
bash scripts/collect-ai-metrics.sh
bash scripts/generate-dashboard-data-lite.sh
```

---

## 📝 STARTUP LOGS

### **Log Locations:**

**Startup Script Logs:**
- Directory: `~/.cache/nixos-quick-deploy/logs/`
- Pattern: `ai-stack-startup-YYYYMMDD_HHMMSS.log`
- Latest: Use `ls -lt` to find most recent

**Startup Reports:**
- Directory: `~/.local/share/nixos-ai-stack/`
- Pattern: `startup-report-YYYYMMDD_HHMMSS.txt`
- Contains: Service status, health checks, resource usage

**Systemd Journal:**
```bash
# View all startup logs from current boot
journalctl --user -u ai-stack-startup.service -b

# Follow startup logs in real-time
journalctl --user -u ai-stack-startup.service -f

# Last 50 lines
journalctl --user -u ai-stack-startup.service -n 50

# Filter by date
journalctl --user -u ai-stack-startup.service --since today
```

**Dashboard Logs:**
```bash
# Dashboard server
journalctl --user -u dashboard-server.service -n 50

# Dashboard collector
journalctl --user -u dashboard-collector.service -n 50
```

---

## ⚠️ TROUBLESHOOTING

### **Services Don't Start on Boot:**

**Check service is enabled:**
```bash
systemctl --user is-enabled ai-stack-startup.service
# Should show: enabled
```

**Check lingering:**
```bash
loginctl show-user $USER | grep Linger
# Should show: Linger=yes
```

**Check service status:**
```bash
systemctl --user status ai-stack-startup.service
# Look for errors in output
```

**View detailed logs:**
```bash
journalctl --user -u ai-stack-startup.service -b -p err
# Shows only errors from current boot
```

### **Startup Takes Too Long:**

**Current timeout**: 300 seconds (5 minutes)

**To increase timeout:**
```bash
# Edit service file
nano ~/.config/systemd/user/ai-stack-startup.service

# Change line:
TimeoutStartSec=600  # 10 minutes

# Reload and restart
systemctl --user daemon-reload
systemctl --user restart ai-stack-startup.service
```

### **Some Services Fail to Start:**

**Check individual service logs:**
```bash
# View startup log
cat $(ls -t ~/.cache/nixos-quick-deploy/logs/ai-stack-startup-*.log | head -1)

# Check failed container
podman logs local-ai-SERVICE_NAME

# Manual service start
cd ~/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose up -d SERVICE_NAME
```

### **Qdrant Collections Missing:**

**Auto-initialization** runs if <5 collections found.

**Manual initialization:**
```bash
cd ~/Documents/try/NixOS-Dev-Quick-Deploy
bash scripts/initialize-qdrant-collections.sh
```

### **Dashboard Not Accessible:**

**Check dashboard server:**
```bash
systemctl --user status dashboard-server.service

# Restart if needed
systemctl --user restart dashboard-server.service
```

**Check port 8888:**
```bash
ss -ltn | grep 8888
# Should show listening socket
```

**Access dashboard:**
```bash
# Local browser
xdg-open http://localhost:8888/dashboard.html

# Or use curl to test
curl -I http://localhost:8888/dashboard.html
```

---

## 🎯 EXPECTED STARTUP TIME

**Typical startup sequence timing:**

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Network wait | 2-10s | 10s |
| Podman ready | 1-5s | 15s |
| Core infrastructure | 30-45s | 60s |
| MCP services | 20-30s | 90s |
| Qdrant init (if needed) | 10-20s | 110s |
| Dashboard start | 5-10s | 120s |
| Health checks | 10-20s | 140s |
| **Total** | **~2-2.5 minutes** | |

**Note**: First boot after system restart may take longer due to image caching.

---

## 📊 VERIFICATION CHECKLIST

After system reboot, verify auto-start worked:

- [ ] Check service status: `systemctl --user status ai-stack-startup.service`
- [ ] Verify containers running: `podman ps | grep local-ai | wc -l` (should be 8)
- [ ] Test AIDB: `curl http://localhost:8091/health`
- [ ] Test Hybrid: `curl http://localhost:8092/health`
- [ ] Test Qdrant: `curl http://localhost:6333/collections`
- [ ] Test llama.cpp: `curl http://localhost:8080/health`
- [ ] Check dashboard: `curl http://localhost:8888/data/ai_metrics.json`
- [ ] View startup report: `cat $(ls -t ~/.local/share/nixos-ai-stack/startup-report-*.txt | head -1)`
- [ ] Check dashboard in browser: http://localhost:8888/dashboard.html

---

## 🔄 TESTING AUTO-START

**To test without rebooting:**

```bash
# Stop all services
cd ~/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose down

systemctl --user stop dashboard-server.service dashboard-collector.timer

# Simulate boot by starting service
systemctl --user start ai-stack-startup.service

# Watch logs
journalctl --user -u ai-stack-startup.service -f

# Wait for completion (up to 5 minutes)
# Check status
systemctl --user status ai-stack-startup.service

# View startup report
cat $(ls -t ~/.local/share/nixos-ai-stack/startup-report-*.txt | head -1)
```

---

## 🎉 SUMMARY

**Auto-Start Configuration**: ✅ **COMPLETE AND ENABLED**

**What Happens on Boot:**
1. System starts → systemd user services activate
2. ai-stack-startup.service runs automatically
3. All 8 AI containers start in correct order
4. Qdrant collections initialized (if needed)
5. Dashboard services start
6. Health checks verify everything working
7. System ready for use in ~2 minutes

**Manual Intervention**: **NOT REQUIRED**

**Dashboard Available**: http://localhost:8888/dashboard.html

**All Services**: Start automatically, no login needed (lingering enabled)

---

**Configuration Date**: December 31, 2025
**Service Status**: ✅ Enabled and ready for next boot
**User Lingering**: ✅ Enabled
**Expected Boot Time**: ~2-2.5 minutes

🚀 **Your AI Stack will now start automatically on every system boot!**
