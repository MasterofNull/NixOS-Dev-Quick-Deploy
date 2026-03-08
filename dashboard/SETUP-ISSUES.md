# Dashboard Setup Issues

**Date:** December 31, 2025  
**Status:** Historical issue log; no longer reflects current runtime status

## Purpose

This file captures early dashboard v2 setup problems during local development. It should be read as historical troubleshooting context, not as the current operational status of the dashboard.

## Current Runtime Status

### Production / Operator Runtime

The authoritative runtime is:

```bash
systemctl status command-center-dashboard-api.service
curl http://127.0.0.1:8889/api/health
xdg-open http://127.0.0.1:8889/
```

### Local Development Runtime

For development only:

```bash
cd dashboard
./start-dashboard.sh
```

Expected development ports:

- Frontend: `http://localhost:8890`
- Backend API: `http://localhost:8889`

## Historical Issues Captured Here

The original issues recorded in this file included:

- incorrect backend startup command
- missing shadcn/ui component files
- incomplete frontend dependency setup
- Tailwind configuration drift during early local development

Those issues were part of the initial bring-up process and should not be read as current production blockers.

## Current Debugging Guidance

### Check Operator Runtime

```bash
bash scripts/health/system-health-check.sh --detailed
curl http://127.0.0.1:8889/api/health/aggregate | jq .
```

### Check Local Development Stack

```bash
cd dashboard/frontend
npm run build

cd ../backend
python -m py_compile api/main.py
```

### Useful API Checks

```bash
curl http://127.0.0.1:8889/api/services | jq '.'
curl http://127.0.0.1:8889/api/metrics/system | jq '.containers'
curl http://127.0.0.1:8889/docs
```

## Recommendation

- For operators: use the declarative command center runtime.
- For UI/backend iteration: use `start-dashboard.sh`.
- Do not treat this file as a live health/status dashboard for the current system.
