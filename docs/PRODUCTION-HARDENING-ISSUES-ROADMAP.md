# Production Hardening Issues Roadmap
**Created:** 2026-01-09
**Status:** 🚧 In Progress
**Goal:** Close gaps found after the latest hardening pass (TLS consistency, secrets, resource limits, docs, and health checks)

## 🎯 Overview

This roadmap tracks newly discovered issues after the existing production hardening plan was created. Each phase includes a task list and concrete success criteria, mirroring the production hardening roadmap format.

---

## Phase 1: TLS & Ingress Consistency (P0) 🔒

### 1.1 Remove TLS Bypass Ports
**Priority:** P0 - Security regression
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`, `ai-stack/compose/nginx/nginx.conf`

**Tasks:**
- [x] Remove host port exposure for services already proxied by nginx (AIDB, Hybrid, Qdrant, NixOS Docs)
- [x] Add nginx route for Embeddings so external access goes through TLS
- [x] Keep internal container-to-container HTTP unchanged
- [x] Verify only nginx ports are exposed for core APIs

**Success Criteria:**
- No direct host access to core APIs outside nginx
- All core API calls use `https://localhost:8443/...`
- Internal service communication remains functional

---

### 1.2 Fix TLS Usage Guidance
**Priority:** P0 - Insecure guidance
**Status:** ✅ Completed 2026-01-09
**Files:** `AI-AGENT-START-HERE.md`, `AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`, `DOCUMENTATION-INDEX.md`

**Tasks:**
- [x] Replace blanket `curl -k` advice with `--cacert` guidance
- [x] Keep `-k` only as a troubleshooting fallback
- [x] Update example commands to use TLS endpoints consistently

**Success Criteria:**
- Documentation defaults to verified TLS
- `-k` usage labeled as last-resort

---

## Phase 2: Secrets & Auth Reliability (P0) 🔐

### 2.1 Harden Secret Delivery
**Priority:** P0 - Auth reliability
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [x] Switch to Compose secrets for `stack_api_key`
- [x] Ensure secrets are readable by non-root containers
- [x] Remove ad-hoc secrets bind mounts where possible

**Success Criteria:**
- API key delivery is consistent across services
- Permissions do not break non-root containers

---

### 2.2 Fix Auth Examples
**Priority:** P0 - Broken quickstart
**Status:** ✅ Completed 2026-01-09
**Files:** `AI-AGENT-START-HERE.md`, `AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`, `DOCUMENTATION-INDEX.md`

**Tasks:**
- [x] Add `X-API-Key` headers to all authenticated examples
- [x] Clearly note when auth is optional or disabled

**Success Criteria:**
- All example requests succeed when auth is enabled

---

## Phase 3: Runtime Reliability (P1) ⚙️

### 3.1 Fix Tilde Path Defaults
**Priority:** P1 - Broken defaults
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [x] Replace `~` in default path fallbacks with `${HOME}`

**Success Criteria:**
- Default data paths resolve correctly in Compose

---

### 3.2 Make Resource Limits Real
**Priority:** P1 - False sense of safety
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`, docs

**Tasks:**
- [x] Document that `deploy.resources` is advisory in podman-compose
- [x] Add `cpus` and `mem_limit` for podman-compose enforced limits

**Success Criteria:**
- Resource limits are either enforced or explicitly documented as advisory

---

### 3.3 Harden Health Checks
**Priority:** P1 - Startup flakiness
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [x] Use stdlib Python for health checks in python-based services
- [x] Remove bash-only or missing tooling in third-party images where possible

**Success Criteria:**
- Health checks do not fail due to missing binaries

**Validation Notes:**
- Open WebUI and MindsDB healthchecks restored using Python urllib (verified image tool presence).

---

### 3.4 Reduce Privileged Surface
**Priority:** P1 - Security exposure
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [x] Document why elevated access is required if it remains
- [x] Re-evaluate `health-monitor` privileges and socket access (now opt-in via `self-heal` profile)

**Success Criteria:**
- Privileged access justified or removed

---

### 3.5 Remove Deprecated systemd.extraConfig Usage
**Priority:** P1 - Build failure
**Status:** ✅ Completed 2026-01-09
**Files:** `lib/config.sh`

**Tasks:**
- [x] Replace `systemd.extraConfig` with `systemd.settings.Manager`
- [x] Keep `systemd.user.extraConfig` for user units (since `systemd.user.settings` is not available)
- [x] Keep swap accounting and `DefaultMemorySwapMax` behavior intact

**Success Criteria:**
- `nixos-rebuild` dry-build no longer fails on deprecated option assertion
- Generated configuration sets `DefaultMemoryAccounting` and `DefaultMemorySwapMax` for both system and user units

### 3.6 Continuous Learning: Guard Against Deprecated Options
**Priority:** P2 - Regression prevention
**Status:** ✅ Completed 2026-01-09
**Files:** `docs/TEST-CHECKLIST.md`

**Tasks:**
- [x] Add a pre-flight dry-build validation step to catch deprecated options early
- [x] Require recording any dry-build failures in the issues log

**Success Criteria:**
- Deprecated option regressions are caught before full deploy runs

---

### 3.7 Fix Missing Grafana Admin User Env Var
**Priority:** P1 - Deployment blocker
**Status:** ✅ Completed 2026-01-09
**Files:** `ai-stack/compose/.env`, `docs/TEST-CHECKLIST.md`

**Tasks:**
- [x] Add `GRAFANA_ADMIN_USER` to the AI stack env template
- [x] Add an env sanity check to the test checklist

**Success Criteria:**
- `podman-compose` no longer fails with `set GRAFANA_ADMIN_USER`
- Pre-flight checks catch missing Grafana credentials before deployment

---

### 3.8 Prompt for Missing AI Stack Credentials
**Priority:** P1 - Deployment reliability
**Status:** ✅ Completed 2026-01-09
**Files:** `nixos-quick-deploy.sh`

**Tasks:**
- [x] Detect missing AI stack env vars when reusing an existing `~/.config/nixos-ai-stack/.env`
- [x] Prompt for and backfill missing values instead of failing later

**Success Criteria:**
- Quick deploy no longer proceeds with missing `POSTGRES_*` or Grafana admin values
