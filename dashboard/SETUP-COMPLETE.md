# Dashboard Setup Notes

**Date:** December 31, 2025  
**Status:** Historical setup summary; runtime model updated

## What This File Means Now

This file records the original dashboard v2 bring-up work. It is no longer the source of truth for how operators should access the dashboard.

Current runtime split:

- Production/operator runtime: `command-center-dashboard-api.service`
- Production/operator URL: `http://127.0.0.1:8889/`
- Local dashboard development: `cd dashboard && ./start-dashboard.sh`

## Production / Operator Use

Use the declarative command center service:

```bash
systemctl status command-center-dashboard-api.service
curl http://127.0.0.1:8889/api/health
xdg-open http://127.0.0.1:8889/
```

## Local Development Use

Use the local development stack only when iterating on dashboard code:

```bash
cd dashboard
./start-dashboard.sh
```

Expected development endpoints:

- Frontend dev server: `http://localhost:8890`
- Backend API: `http://localhost:8889`

## Historical Achievements

The original setup work in this directory established:

- React/Vite frontend scaffolding
- FastAPI backend for dashboard APIs
- shadcn/ui-based component layer
- local WebSocket-driven dashboard updates
- service and container control integration

These are still relevant as development history, but they do not override the current declarative runtime model.

## Useful API Checks

```bash
curl http://127.0.0.1:8889/api/services
curl http://127.0.0.1:8889/api/metrics/system
curl http://127.0.0.1:8889/api/containers
curl http://127.0.0.1:8889/docs
```

## Summary

- The dashboard implementation work completed successfully.
- The operator entry point is now the declarative command center service.
- `start-dashboard.sh` remains valid for local development only.
