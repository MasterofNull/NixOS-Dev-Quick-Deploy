# Command Center Dashboard

This directory contains the command-center dashboard code and local development helpers.

## Runtime Authority

Production runtime is declarative and managed by NixOS/systemd.

- Authoritative service: `command-center-dashboard-api.service`
- Authoritative operator URL: `${DASHBOARD_URL}` at runtime, typically `http://127.0.0.1:8889`
- The FastAPI service serves both:
  - the operator UI at `/`
  - the dashboard/API routes at `/api/*`

Do not treat `scripts/deploy/start-unified-dashboard.sh` or `scripts/deploy/serve-dashboard.sh` as the production deployment path. They are compatibility or local troubleshooting helpers only.

## Operator Usage

Use the declarative runtime:

```bash
systemctl status command-center-dashboard-api.service
curl http://127.0.0.1:8889/api/health
open http://127.0.0.1:8889/
```

If configuration changed:

```bash
sudo nixos-rebuild switch --flake .#$(hostname)
systemctl restart command-center-dashboard-api.service
```

## Local Development Only

For frontend/backend development work in this directory:

```bash
cd dashboard
./start-dashboard.sh
```

That path is for iterative local development only. It is intentionally separate from the declarative production runtime and may use dev-server ports such as `8890`.

## Directory Notes

- `backend/`: FastAPI backend and service integration layer
- `frontend/`: React/Vite frontend used for active UI development
- `public/` via Nix module: production-served dashboard entry point
- `control-center.html`: legacy dashboard surface pending cleanup/integration

## Phase 1 Cleanup Intent

This README now reflects the cleanup rule for dashboard runtime authority:

- one production runtime,
- one operator entry point,
- local dev helpers must not present themselves as deployment mechanisms.
