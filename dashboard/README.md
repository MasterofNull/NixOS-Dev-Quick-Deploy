# NixOS System Command Center Dashboard

**Single Source of Truth for System Monitoring and AI Stack Management**

## Quick Start

The dashboard is served directly by the FastAPI backend:

```bash
cd backend
uvicorn api.main:app --host 0.0.0.0 --port 8889 --reload
```

Access at: **http://localhost:8889/**

## Architecture

```
dashboard/
├── backend/          # FastAPI backend serving dashboard + APIs
│   ├── api/          # Route handlers and services
│   └── requirements.txt
│
../dashboard.html     # Command Center dashboard (repo root)
../assets/            # Chart.js and static assets (repo root)
```

## Features

- **System Metrics**: Real-time CPU, memory, disk, GPU, network charts
- **AI Stack Management**: 13 services with health monitoring
- **AI Insights & Intelligence**: 5 comprehensive analytics panels
- **Ralph Wiggum Configuration**: Agent iteration controls
- **Service Management**: Start/stop/restart controls
- **Live Updates**: WebSocket + polling for real-time data

## API Endpoints

- `/api/health/*` - Service health monitoring
- `/api/insights/*` - AI intelligence analytics (10 endpoints)
- `/api/services/*` - Service management
- `/api/metrics/*` - System metrics
- `/api/prsi/*` - PRSI workflow actions
- `/` - Command Center dashboard (HTML)
- `/assets/*` - Static assets (Chart.js, etc.)

## Development

Backend auto-reloads on file changes when started with `--reload` flag.
Dashboard is served as static HTML from repo root.

## Notes

- **No React/Node/pnpm required** - Pure HTML/JavaScript dashboard
- **No separate frontend build** - Single FastAPI server serves everything
- **No divergent architectures** - One dashboard, one backend, one API

For systemd service management, see main repo documentation.
