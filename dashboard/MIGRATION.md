# Migration from v1 to v2

## Overview

Dashboard v2 is a **complete rewrite** with a modern React frontend and FastAPI backend. The old HTML/CSS/JS dashboard has been replaced with a full-stack application.

## What Changed

### Architecture
- **v1**: Static HTML + Chart.js + Vanilla JS
- **v2**: React 19 + Vite + FastAPI + WebSocket

### Data Collection
- **v1**: `scripts/generate-dashboard-data.sh` → JSON files
- **v2**: FastAPI backend with psutil → WebSocket stream

### Deployment
- **v1**: Python HTTP server on port 8888
- **v2**: Vite dev server (8890) + FastAPI (8889)

### Features Added
- ✅ Real-time WebSocket streaming (2s updates)
- ✅ Interactive service controls (start/stop/restart)
- ✅ Modern UI with shadcn components
- ✅ TypeScript type safety
- ✅ Responsive design

### Features Removed (Temporarily)
- ⏳ Container list viewer (coming in Phase 2)
- ⏳ Configuration editor (coming in Phase 3)
- ⏳ Log viewer (coming in Phase 3)
- ⏳ Network topology (planned)

## Migration Steps

### 1. Stop Old Dashboard
```bash
# Kill old services
systemctl --user stop dashboard-server.service
systemctl --user stop dashboard-collector.timer

# Or kill manually
pkill -f "generate-dashboard-data.sh"
pkill -f "serve-dashboard.sh"
```

### 2. Install New Dashboard
```bash
cd NixOS-Dev-Quick-Deploy/dashboard
./start-dashboard.sh
```

### 3. Update Bookmarks
- Old URL: `http://localhost:8888/dashboard.html`
- New URL: `http://localhost:8890`

### 4. Optional: Keep Old Dashboard
The old dashboard files are preserved in the repo root:
- `dashboard.html` (old)
- `launch-dashboard.sh` (old)
- `scripts/generate-dashboard-data.sh` (still used by old version)

You can run both side-by-side on different ports.

## Data Compatibility

### JSON Files
The new backend does **not** use the old JSON files in `~/.local/share/nixos-system-dashboard/`.

Data is now:
- Collected in real-time by FastAPI backend
- Streamed via WebSocket to frontend
- Stored in-memory (last 100 points)

### Historical Data
To preserve old historical data:
1. Old dashboard stored JSON snapshots every 15 seconds
2. New dashboard stores data in-memory (resets on restart)
3. Future: Database persistence (Phase 5)

## Configuration

### Old Dashboard
```bash
# Environment variables in launch-dashboard.sh
DASHBOARD_COLLECT_INTERVAL=15
DATA_DIR="${HOME}/.local/share/nixos-system-dashboard"
```

### New Dashboard
```bash
# Environment variables in backend/.env
API_PORT=8889
CORS_ORIGINS=http://localhost:8890
AI_STACK_DATA=$HOME/.local/share/nixos-ai-stack
```

## Systemd Services

### Old Services (disable these)
```bash
systemctl --user disable dashboard-collector.timer
systemctl --user disable dashboard-server.service
```

### New Services (optional, not created yet)
Future: Create systemd units for v2 dashboard
```bash
# backend/systemd/dashboard-api.service
# frontend/systemd/dashboard-ui.service
```

## Rollback Plan

If you need to rollback to v1:

```bash
# Stop v2
cd dashboard
# Press Ctrl+C in start-dashboard.sh terminal

# Start v1
cd ..
./launch-dashboard.sh
```

Both dashboards can coexist:
- v1 on port 8888
- v2 on ports 8889/8890

## Feature Parity Checklist

### ✅ Implemented
- [x] CPU, Memory, Disk metrics
- [x] Real-time charts
- [x] Service status monitoring
- [x] System health score
- [x] Dark theme

### 🚧 In Progress
- [ ] Container list with search
- [ ] Network device listing
- [ ] GPU monitoring (AMD)
- [ ] Persistence & data export

### 📋 Planned
- [ ] Terminal emulator
- [ ] File browser
- [ ] Log viewer
- [ ] Configuration editor
- [ ] Alert notifications

## API Equivalents

### Old Data Files → New API Endpoints

```bash
# system.json
curl http://localhost:8889/api/metrics/system

# llm.json → services
curl http://localhost:8889/api/services

# container list
curl http://localhost:8889/api/containers

# health score
curl http://localhost:8889/api/metrics/health-score
```

## Known Issues

1. **No persistence**: Data lost on restart (in-memory only)
2. **No alerts**: Notification system not yet implemented
3. **Limited history**: Only last 100 points (vs. 24h in v1)
4. **No export**: CSV/JSON export coming in Phase 5

## Getting Help

- Check [README.md](./README.md) for setup instructions
- Review [API docs](http://localhost:8889/docs) when backend running
- Check browser console for frontend errors
- Check terminal output for backend errors

---

**Last Updated**: 2025-01-01
