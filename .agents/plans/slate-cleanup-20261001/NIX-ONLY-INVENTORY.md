# Nix-only dependency layer: inventory and disposition (2026-10-01)

Owner decision: Nix is the single source of truth for deployed dependencies. The parallel
Docker/pip layer is retired; the real Nix system closure is scanned instead.
Evidence: ai-aidb, ai-hybrid-coordinator, ai-nixos-docs, ai-ralph-wiggum, ai-aider-wrapper run from
Nix python3.13 envs; postgres/redis/qdrant are native NixOS services; no container runtime runs;
no Nix module builds the Dockerfiles. 198 Trivy alerts came from never-deployed images.

Archive root: `.agent/archive/20261001-docker-pip-layer/` (paths mirror the originals; moved with `git mv`).

## A. Inventory (before)

| Artifact | Disposition |
|---|---|
| Dockerfile x10 under ai-stack/mcp-servers (aidb, aider-wrapper, container-engine, embeddings-service, health-monitor, hybrid-coordinator, nixos-docs, qdrant-populator, ralph-wiggum) + templates/mcp-servers/embeddings-service | archived |
| requirements.lock x8 (aidb, aider-wrapper, container-engine, health-monitor, hybrid-coordinator, nixos-docs, ralph-wiggum) | archived |
| requirements.txt: aider-wrapper, ralph-wiggum, health-monitor, container-engine | archived |
| requirements.txt: aidb, hybrid-coordinator, nixos-docs | KEPT: still installed by CI test envs (`.github/workflows/tests.yml` unit-tests matrix, `test-coverage.yml`). They feed CI unit tests, not deployment. Follow-up: move CI test envs to a Nix devShell, then archive. |
| ai-stack/autonomous-improvement/requirements.txt, ai-stack/agents/skills/*/requirements.txt | out of scope (not container/deploy layer) |
| dashboard/backend/Dockerfile + requirements.txt | out of scope (outside ai-stack/ and templates/); requirements.txt used by `test-coverage.yml` |

### CI (rg docker|trivy|image .github/workflows)
- security.yml `trivy-scan-core` (7 pulled images: postgres, redis, qdrant, nginx, grafana, prometheus, jaeger): removed
- security.yml `trivy-scan-custom` (docker build + scan of aidb, embeddings-service, hybrid-coordinator, nixos-docs): removed
- security.yml `dockerfile-lint` (hadolint): removed
- security.yml `security-summary` needs/echo lines: updated
- No other workflow builds or scans images.

### Readers of the artifacts
- scripts/testing/test-requirements-floor-policy.py: UPDATED (kept guarding live requirements.txt floors; Dockerfile and lock checks dropped)
- scripts/testing/test-verify-python-lock-runtime.py + scripts/security/verify-python-lock-runtime.py: archived (guard only locks, none remain)
- scripts/testing/test-security-trivy-sarif-upload.py (untracked): archived, replaced by test-security-nix-closure-scan.py
- scripts/security/security-audit.sh: kept; pip-audit/lock loops are now no-ops (no lockfiles; lock verifier absent reports scanner_unavailable with zero issues)
- scripts/security/{summarize-github-code-scanning-alerts,cleanup-stale-code-scanning-analyses,report-github-code-scanning-residuals}.sh: UPDATED. They read `jobs["trivy-scan-core"]` and would have crashed; categories now come from upload-sarif steps.
- scripts/security/rsi-intake-code-scanning.py: UPDATED (nix-closure category; legacy kept)
- config/aq-integrity-logical-orphans.json: removed the qdrant-populator/populate.py entry (path archived)
- Untouched string-only mentions: scripts/data/populate-qdrant-directly.py, scripts/ai/aq-capability-gap, config/capability-package-resolvers.json (generic manifest names), scripts/ai/aqd (skill requirements)

## Unit-less service dirs

| Dir | Referenced by | Result |
|---|---|---|
| qdrant-populator | only a stale logical-orphans baseline entry and a prose string in config/system-state-authorities.yaml | archived whole dir |
| container-engine | templates/vscode MCP configs (by name/port), `create_container_engine_client` helper in shared/auth_http_client.py | server.py KEPT; Docker/pip files archived |
| embeddings-service | runtime URL/health name only (aidb/server.py, embedder.py, check-mcp-health.sh); templates/mcp-servers/embeddings-service/server.py copy | server.py KEPT; Dockerfiles archived |
| mlops-tools, qa-tools, trading-tools | LIVE: hybrid-coordinator extensions/mcp_handlers.py:1583-1599 spawns their server.py | KEPT untouched (they had no Docker/pip files) |
| health-monitor (not in owner list, had Docker/pip files) | logical-orphans baseline entry for self_healing_daemon.py | python KEPT; Docker/pip files archived |
