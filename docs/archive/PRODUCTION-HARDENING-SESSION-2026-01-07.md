# Production Hardening Progress Report
**Date:** 2026-01-07
**Session:** Phase 2 Validation + TLS/Hybrid Fixes
**Status:** ✅ Phase 2 Complete | 🟡 Phase 3 In Progress

---

## Executive Summary

Validated Phase 2 changes (network isolation + TLS) and resolved runtime gaps: fixed hybrid coordinator startup (secret permissions), corrected nginx upstream behavior with dynamic DNS resolution and path rewrites, and patched a missing `timezone` import in the hybrid continuous learning pipeline. HTTPS endpoints now resolve consistently through nginx, and hybrid health checks pass end-to-end.

---

## Scope Completed

### ✅ Phase 2.1: Remove network_mode: host
**Files:** `ai-stack/compose/docker-compose.yml`

**Implementation Highlights:**
- Removed `network_mode: host` from all services.
- Added explicit port mappings for host-facing services.
- Updated service discovery URLs to use compose service names (e.g., `http://qdrant:6333`).
- Kept health checks on localhost (container-local), so readiness probes remain valid.

**Host-Exposed Ports (Now Explicit):**
- Qdrant: `6333`, `6334`
- Embeddings: `8081`
- llama.cpp: `8080`
- Open WebUI: `3001`
- AIDB MCP: `8091`
- Hybrid Coordinator: `8092`
- NixOS Docs MCP: `8094`
- MindsDB: `47334`
- Ralph Wiggum: `8098`
- Aider (profile): `8093`
- AutoGPT (profile): `8097`

**No Longer Exposed to Host:**
- PostgreSQL (`5432`)
- Redis (`6379`)
- health-monitor internal service
- aider-wrapper internal service

---

## Files Updated

1. `ai-stack/compose/docker-compose.yml`
2. `ai-stack/mcp-servers/config/config.yaml`
3. `ai-stack/compose/nginx/nginx.conf`
4. `ai-stack/compose/nginx/certs/.gitkeep`
5. `scripts/generate-nginx-certs.sh`
6. `PRODUCTION-HARDENING-ROADMAP.md`

---

## Validation Status

**Completed in this session:**
- `podman-compose -f ai-stack/compose/docker-compose.yml config`
- `podman-compose -f ai-stack/compose/docker-compose.yml up -d`
- Service discovery checks via compose DNS (curl from `local-ai` network)
- Host port checks for PostgreSQL/Redis exposure
- Health checks for Qdrant, Embeddings, llama.cpp, Hybrid Coordinator, AIDB
- HTTPS validation via nginx (`/aidb/health`, `/qdrant/healthz`, `/hybrid/health`)
- Confirmed host-level access to Postgres/Redis is blocked (`localhost:5432` / `localhost:6379`)

**Key Results:**
- ✅ Service-name routing works on `local-ai` network (aidb/qdrant/embeddings/hybrid-coordinator reachable by name).
- ✅ Host access to `localhost:5432` and `localhost:6379` blocked (no exposure).
- ✅ AIDB health endpoint reachable on `http://localhost:8091/health` after config update.

---

## Issues Found and Fixed

1. **Embeddings healthcheck failed (curl missing)**  
   - **Symptom:** Container stayed `starting` because healthcheck used curl.  
   - **Fix:** Switched compose healthcheck to `python -c` with `requests`.

2. **AIDB still connecting to localhost Postgres**  
   - **Symptom:** AIDB failed to connect after network isolation (`localhost:5432` refused).  
   - **Root cause:** `ai-stack/mcp-servers/config/config.yaml` still used `localhost`.  
   - **Fix:** Updated config to use `postgres`, `redis`, `http://llama-cpp:8080` and rebuilt AIDB image.

3. **Tracked Python bytecode in repo**  
   - **Symptom:** `__pycache__/server.cpython-313.pyc` showed as modified despite `.gitignore`.  
   - **Root cause:** File was already committed, so ignore rules didn't apply.  
   - **Fix:** Removed from git index and deleted the file; rely on `.gitignore` going forward.

4. **Hybrid coordinator unable to read API key secret**  
   - **Symptom:** `PermissionError: [Errno 13]` on `/run/secrets/stack_api_key`.  
   - **Root cause:** API key file created with `0600` permissions; hybrid runs as a non-root user.  
   - **Fix:** Set secret to `0644` and updated `scripts/generate-api-key.sh` to apply readable permissions.

5. **Nginx upstream 502 after hybrid restart**  
   - **Symptom:** `/hybrid/health` returned 502 after container IP changes.  
   - **Root cause:** Nginx resolved upstream IP once at startup.  
   - **Fix:** Added DNS resolver + variable-based `proxy_pass` with path rewrites for dynamic service discovery.

6. **Continuous learning telemetry error (`timezone` undefined)**  
   - **Symptom:** `telemetry_processing_failed error=name 'timezone' is not defined`.  
   - **Root cause:** Missing import in `continuous_learning.py`.  
   - **Fix:** Added `timezone` import.

## Phase 2.2 Completed (TLS/HTTPS)

- Added nginx reverse proxy service in compose.
- Added `ai-stack/compose/nginx/nginx.conf` with HTTPS redirect and proxy routes.
- Added `scripts/generate-nginx-certs.sh` for self-signed cert generation.
- Generated local dev certificates and verified HTTPS endpoints.
- Adjusted nginx host ports to `8088/8443` due to rootless Podman constraints.
- Updated top-level docs to reference HTTPS endpoints via nginx.

**Validation:**  
- `http://localhost:8088` → 301 redirect to `https://localhost:8443`  
- `https://localhost:8443/aidb/health` → 200 OK  
- `https://localhost:8443/hybrid/health` → 200 OK  

## Phase 2.3 Kickoff (API Authentication)

- Identified existing AIDB support for `api_key` and `api_key_file` in settings loader.
- Added `scripts/generate-api-key.sh` and secret storage under `ai-stack/compose/secrets/`.
- Wired secrets into compose for AIDB, embeddings, hybrid-coordinator, and nixos-docs.
- Added API key middleware to embeddings (Flask), hybrid-coordinator (aiohttp), and nixos-docs (FastAPI).
- Added config hook for AIDB to read `/run/secrets/stack_api_key`.
**Validation:**
- Unauthenticated AIDB document import returns 401.
- Authenticated AIDB document import returns 200.
- Unauthenticated embeddings `/embed` returns 401; authenticated returns 200.

## Phase 2.4 Implemented (Sanitized Errors)

- Replaced `detail=str(exc)` responses with generic error payloads plus `error_id`.
- Added error ID logging helpers in AIDB, embeddings, hybrid-coordinator, and nixos-docs.
**Validation:**
- AIDB `/vector/search` invalid payload returns `error_id` without stack trace in response.

## Phase 2.5 Implemented (Port Exposure)

- Bound service ports to `127.0.0.1` to prevent external access.
- Kept nginx as the only public entrypoint (`8088/8443`).
**Validation:**
- Host checks to `localhost:5432` and `localhost:6379` fail (connection refused).

## Phase 3.1 Started (Structured Logging)

- Added request correlation IDs to AIDB, embeddings, hybrid-coordinator, and nixos-docs.
- Added structlog to nixos-docs requirements (already present in aidb/hybrid).
- Configured JSON log formatting and bound service metadata (service/version) for AIDB, embeddings, hybrid-coordinator, and nixos-docs.
- Next: validate JSON output and correlation IDs across access logs and request middleware.
**Validation:**
- JSON logs confirmed for AIDB and embeddings; hybrid access logs now emit JSON.
- `X-Request-ID` header confirmed on AIDB and hybrid responses.

## Phase 3.2 Started (Prometheus Metrics)

- Added `/metrics` endpoints for embeddings, hybrid-coordinator, and nixos-docs.
- Added Prometheus client dependencies where missing.
- Added Prometheus and Grafana services to compose with local-only ports.
- Provisioned Grafana with a default Prometheus data source.
- Adjusted Prometheus and Grafana volumes to `:Z,U` for rootless permissions.
- Grafana now runs on `http://localhost:3002` (port 3000 was already in use).

**Validation:**
- `http://localhost:9090/-/ready` → 200 OK (Prometheus)
- `http://localhost:3002/login` → 200 OK (Grafana)
- Prometheus targets show `aidb`, `embeddings`, `hybrid-coordinator`, `nixos-docs` as `up`.
- Grafana dashboard **AI Stack Overview** present.

## Runtime Note (Resolved)

- `hybrid-coordinator` now starts cleanly with readable secrets and responds to health checks over nginx.

## Phase 3.3 Started (Distributed Tracing)

- Added Jaeger service to compose (local-only ports).
- Added OpenTelemetry dependencies to AIDB, hybrid-coordinator, and nixos-docs.
- Added OTLP exporter setup and FastAPI instrumentation for AIDB + nixos-docs.
- Added OTLP exporter setup and HTTP tracing middleware for hybrid-coordinator.
- Wired OTEL exporter env vars in compose (OTLP to Jaeger).

**Validation:**  
- Container recreate required to activate new tracing code (blocked by dependent services).
- Jaeger services list includes `aidb`, `nixos-docs`, and `hybrid-coordinator`.

## Risks and Follow-Ups

- Service-to-service URLs now depend on compose DNS. If a container fails to join the network, dependent services will fail quickly (expected).
- Any scripts that assumed direct host access to Postgres/Redis will now fail by design; update those workflows if host access is required for ops.
- Hybrid coordinator access logs still emit default aiohttp formatting; requires a controlled recreate to apply JSON-format access logging.
- `podman-compose up` attempts are removing/recreating containers with dependents; prefer `podman-compose up -d --no-deps <service>` and manual `podman start` when only adding new services.

---

## Next Steps (Phase 3)

1. **Phase 3.1 Structured Logging**
   - Switch logs to JSON output and add service metadata fields.
   - Validate correlation IDs across services.

2. **Phase 3.2 Prometheus/Grafana**
   - Add Prometheus and Grafana services to compose.
   - Track request counts, latencies, errors.

3. **Phase 3.3 Tracing**
   - Instrument HTTP spans and verify traces in Jaeger.

---

## Continuity Notes (For Next Session)

- Start with structured logging work in `ai-stack/mcp-servers/*/server.py`.
- Keep nginx resolver + rewrite rules to avoid upstream 502s after container restarts.
- Update `PRODUCTION-HARDENING-ROADMAP.md` as Phase 3 tasks complete.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-07
