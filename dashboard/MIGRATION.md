# Dashboard Migration Notes

## Status

This document is retained as migration history for the dashboard rewrite.

- Production/operator runtime: `command-center-dashboard-api.service`
- Production/operator URL: `http://127.0.0.1:8889/`
- Local frontend/backend development: `cd dashboard && ./start-dashboard.sh`

## Runtime Split

There are now two distinct paths:

### 1. Declarative Production Runtime

Use this for normal operation:

```bash
systemctl status command-center-dashboard-api.service
curl http://127.0.0.1:8889/api/health
xdg-open http://127.0.0.1:8889/
```

This is the authoritative runtime. It serves both the operator UI and the API from one port.

### 2. Local Development Runtime

Use this only when iterating on the React/Vite frontend or the FastAPI dashboard backend:

```bash
cd dashboard
./start-dashboard.sh
```

Expected local-dev ports:

- Frontend dev server: `http://localhost:8890`
- Backend API: `http://localhost:8889`

These ports are for development only and are not the production deployment model.

## Historical Context

Earlier versions used:

- static `dashboard.html`
- JSON files under `~/.local/share/nixos-system-dashboard/`
- helper scripts such as `serve-dashboard.sh` and `launch-dashboard.sh`

Those flows are now legacy compatibility/history paths. They should not be used as the operator guidance for current deployments.

## API Equivalents

```bash
curl http://127.0.0.1:8889/api/metrics/system
curl http://127.0.0.1:8889/api/services
curl http://127.0.0.1:8889/api/containers
curl http://127.0.0.1:8889/api/metrics/health-score
```

## Notes

- `dashboard.html` remains in the repo as an active surface, but production access is through the declarative command center runtime.
- If you are debugging frontend work, use the local dev path intentionally and treat its ports as temporary development details.
