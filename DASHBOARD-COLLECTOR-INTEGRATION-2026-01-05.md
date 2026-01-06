# Dashboard Collector Integration with AI Stack

**Date:** 2026-01-05
**Status:** ✅ Complete and Tested

## Overview

The dashboard data collector has been fully integrated into the AI stack startup workflow, ensuring that system metrics are continuously collected and the dashboard displays accurate, real-time health information.

## Components Fixed

### 1. Dashboard Collector Service (`~/.config/systemd/user/dashboard-collector.service`)

**Issue:** Service was failing with exit code 127 because standard commands like `mkdir` couldn't be found.

**Fix:** Added proper PATH environment variable to the service:

```ini
[Service]
Type=oneshot
Environment="PATH=/run/current-system/sw/bin:/run/wrappers/bin:/home/hyperd/.nix-profile/bin:/etc/profiles/per-user/hyperd/bin:/nix/var/nix/profiles/default/bin:/run/current-system/sw/bin"
ExecStart=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh
```

**Result:** Service now runs successfully and completes data collection.

### 2. Dashboard Collector Timer (`~/.config/systemd/user/dashboard-collector.timer`)

**Issue:** Timer showed "active (elapsed)" with no next trigger time, never scheduling the next run.

**Fix:** Changed from `OnUnitActiveSec=15s` to calendar-based scheduling:

```ini
[Timer]
OnBootSec=10s
OnCalendar=*:*:0,15,30,45  # Run at :00, :15, :30, :45 seconds past each minute
AccuracySec=1s
Persistent=true
```

**Result:** Timer now reliably triggers every 15 seconds.

### 3. AI Stack Startup Service (`~/.config/systemd/user/ai-stack-startup.service`)

**Enhancement:** Added dashboard services as dependencies to ensure they start together:

```ini
[Unit]
Wants=network-online.target dashboard-collector.timer dashboard-server.service dashboard-api.service
```

**Result:** Dashboard services are automatically started when the AI stack starts at boot.

### 4. AI Stack Compose Workflow (`scripts/hybrid-ai-stack.sh`)

**Enhancement:** Added dashboard collector startup to the `cmd_up()` function:

```bash
# Start dashboard collector if not already running
if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl --user is-active --quiet dashboard-collector.timer 2>/dev/null; then
        info "Starting dashboard collector..."
        systemctl --user start dashboard-collector.timer 2>/dev/null && success "Dashboard collector started" || warning "Could not start dashboard collector"
    fi

    # Trigger initial data collection
    if [[ -x "${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" ]]; then
        info "Collecting initial dashboard metrics..."
        "${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" >/dev/null 2>&1 || warning "Initial metrics collection had issues"
    fi
fi
```

**Result:** When users run `./scripts/hybrid-ai-stack.sh up`, the dashboard collector is automatically started and initial metrics are collected.

### 5. AI Stack Startup Script (`scripts/ai-stack-startup.sh`)

**Status:** Already includes dashboard collector startup at lines 194-204:

```bash
# Start dashboard collector timer
if systemctl --user is-active --quiet dashboard-collector.timer; then
    info "Dashboard collector already running"
else
    systemctl --user start dashboard-collector.timer 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard collector start failed"
fi

# Force initial metrics collection
info "Collecting initial dashboard metrics..."
bash "$PROJECT_ROOT/scripts/collect-ai-metrics.sh" 2>&1 | tee -a "$LOG_FILE" || warn "Initial metrics collection failed"
bash "$PROJECT_ROOT/scripts/generate-dashboard-data-lite.sh" 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard data generation failed"
```

**Result:** No changes needed; already properly integrated.

## Integration Points

### Boot-Time Startup

1. **SystemD Dependency Chain:**
   ```
   ai-stack-startup.service
   ├── Wants: dashboard-collector.timer
   ├── Wants: dashboard-server.service
   └── Wants: dashboard-api.service
   ```

2. **Execution Flow:**
   - `ai-stack-startup.service` triggers at boot
   - Calls `scripts/ai-stack-startup.sh`
   - Script starts containers via `podman-compose`
   - Script explicitly starts `dashboard-collector.timer`
   - Script runs initial data collection
   - Dashboard displays 100% health

### Manual Compose Bring-Up

1. **User Command:**
   ```bash
   ./scripts/hybrid-ai-stack.sh up
   ```

2. **Execution Flow:**
   - Script runs `podman-compose up -d`
   - All containers start with healthchecks
   - Script checks if `dashboard-collector.timer` is active
   - If not active, starts the timer
   - Runs initial data collection
   - Dashboard is immediately updated

### Continuous Operation

1. **Timer Schedule:**
   - Runs every 15 seconds (at :00, :15, :30, :45 seconds)
   - Collects all metrics: system, services, containers, telemetry
   - Updates JSON files in `~/.local/share/nixos-system-dashboard/`

2. **Data Files Updated:**
   - `llm.json` - Service health status
   - `system.json` - CPU, memory, disk metrics
   - `config.json` - Required services configuration
   - `database.json` - PostgreSQL metrics
   - `feedback.json` - Telemetry feedback
   - `hybrid-coordinator.json` - Coordinator metrics
   - Plus 10 additional metric files

## Verification

### Service Status
```bash
$ systemctl --user is-active dashboard-collector.timer dashboard-server.service dashboard-api.service
active
active
active
```

### Timer Schedule
```bash
$ systemctl --user list-timers | grep dashboard-collector
Mon 2026-01-05 01:07:45 PST   810ms left   Mon 2026-01-05 01:07:30 PST   15s ago   dashboard-collector.timer
```

### Recent Data Collection
```bash
$ ls -lh ~/.local/share/nixos-system-dashboard/*.json | head -3
Jan 5 01:07 config.json
Jan 5 01:07 database.json
Jan 5 01:07 feedback.json
```

### Dashboard Health
```bash
$ curl -s http://localhost:8888/llm.json | jq -r '.services | to_entries[] | "\(.key): \(.value.status)"'
qdrant: online
llama_cpp: online
postgres: online
redis: online
open_webui: online
mindsdb: online
aidb: online
hybrid_coordinator: online
```

**Result:** Dashboard displays **100% health** ✅

## Benefits

1. **Automatic Startup:** Dashboard collector starts automatically with AI stack at boot
2. **Manual Convenience:** Running `hybrid-ai-stack.sh up` ensures collector is active
3. **Real-Time Updates:** Metrics collected every 15 seconds
4. **Accurate Health:** Dashboard shows current service status, not stale data
5. **Reliable Operation:** Fixed systemd timer ensures consistent scheduling
6. **No Manual Steps:** Users don't need to separately start the collector

## Files Modified

1. `~/.config/systemd/user/dashboard-collector.service` - Added PATH environment
2. `~/.config/systemd/user/dashboard-collector.timer` - Changed to calendar scheduling
3. `~/.config/systemd/user/ai-stack-startup.service` - Added dashboard service dependencies
4. `scripts/hybrid-ai-stack.sh` - Added collector startup to compose workflow

## Testing

All integration points tested and verified:

- ✅ SystemD dependencies correctly configured
- ✅ Timer runs every 15 seconds reliably
- ✅ Service completes successfully (no exit code 127)
- ✅ Data files update every 15 seconds
- ✅ Dashboard shows 100% health with all services online
- ✅ Boot-time startup includes collector
- ✅ Manual compose brings up collector
- ✅ No stale data in dashboard

## Conclusion

The dashboard data collector is now fully integrated into all AI stack startup workflows. Whether the system boots automatically, or users manually start the stack with `hybrid-ai-stack.sh up`, the collector will be active and continuously updating metrics. The dashboard will always display accurate, real-time health information.
