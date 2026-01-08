# Quick Deploy Market Readiness Roadmap
**Created:** 2026-01-09  
**Status:** 🚧 In Progress  
**Goal:** Ship a cohesive NixOS Quick Deploy that is production-ready on CPU/iGPU laptops and GPU workstations without duplicated work or drift.

## 🎯 Overview

This roadmap focuses on eliminating drift across phases, centralizing model selection, and enforcing reliable, testable outcomes. It uses the same structure as the production hardening roadmap to track concrete tasks, files, and success metrics.

---

## Phase 1: Cohesion & Defaults (P0 - Must Fix) 🔥

### 1.1 Unify Embedding Defaults ✅ COMPLETE
**Priority:** P0 - Prevents conflicting behavior
**Status:** ✅ Completed 2026-01-09  
**Files:** `lib/user.sh`, `ai-stack/compose/.env`, `templates/local-ai-stack/.env.example`, `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [x] Align default embedding model with runtime (`sentence-transformers/all-MiniLM-L6-v2`)
- [x] Ensure embedding model can be overridden via `.env`
- [x] Remove hardcoded compose defaults in favor of env values

**Success Criteria:** ✅ All Met  
- ✅ Quick deploy prompts reflect the same embedding default as the running stack  
- ✅ Compose uses `EMBEDDING_MODEL` from `.env`  

---

### 1.2 Enforce AI Stack Env Contract ✅ COMPLETE
**Priority:** P0 - Prevents late-stage failures  
**Status:** ✅ Completed 2026-01-09  
**Files:** `nixos-quick-deploy.sh`, `ai-stack/compose/docker-compose.yml`, `lib/ai-optimizer.sh`

**Tasks:**
- [x] Require `AI_STACK_ENV_FILE` explicitly in compose
- [x] Backfill missing required keys when reusing `.env`
- [x] Export `AI_STACK_ENV_FILE` before compose runs

**Success Criteria:** ✅ All Met  
- ✅ Deploy fails fast when `.env` is missing  
- ✅ Missing keys are prompted and filled before container start  

---

### 1.3 Remove Duplicate Model Downloads ✅ COMPLETE
**Priority:** P0 - Wastes time + bandwidth  
**Status:** ✅ Completed 2026-01-09  
**Files:** `phases/phase-09-ai-model-deployment.sh`, `phases/phase-09-ai-stack-deployment.sh`, `scripts/setup-hybrid-learning.sh`

**Tasks:**
- [x] Avoid downloading models in multiple phases
- [x] Make model downloads optional and phase-aware
- [x] Keep “download on first use” as the default fallback

**Success Criteria:** ✅ All Met  
- ✅ No duplicate model downloads in a single run  

---

## Phase 2: Model Lifecycle Coordination (P0 - Must Fix) ⚙️

### 2.1 Keyed Model Downloads ✅ COMPLETE
**Priority:** P0 - Centralizes selection  
**Status:** ✅ Completed 2026-01-09  
**Files:** `scripts/download-llama-cpp-models.sh`, `phases/phase-09-ai-model-deployment.sh`

**Tasks:**
- [x] Add `--model` and `--models` support to GGUF downloader
- [x] Map selected model to download keys

**Success Criteria:** ✅ All Met  
- ✅ Download script can fetch only the selected GGUF  

---

### 2.2 Model Swap Helpers ✅ COMPLETE
**Priority:** P0 - Developer workflow blocker  
**Status:** ✅ Completed 2026-01-09  
**Files:** `scripts/swap-llama-cpp-model.sh`, `scripts/swap-embeddings-model.sh`

**Tasks:**
- [x] Add a single command to switch llama.cpp GGUF (edit `.env` + restart)
- [x] Add a single command to switch embedding model (edit `.env` + restart embeddings)
- [x] Ensure swap does not re-download unless missing

**Success Criteria:**  
- Coder swap completes < 2 minutes (including restart)  
- Embedding swap completes < 3 minutes  

---

### 2.3 Runtime Visibility for Cached + Active Models ✅ COMPLETE
**Priority:** P0 - Debuggability  
**Status:** ✅ Completed 2026-01-09  
**Files:** `scripts/generate-dashboard-data.sh`, `dashboard.html`

**Tasks:**
- [x] Show cached GGUFs in dashboard data
- [x] Show embedding cache models and service usage

**Success Criteria:** ✅ All Met  
- ✅ Dashboard shows cached + active models  

---

## Phase 3: CPU/iGPU Profile Defaults (P0) 🧊

### 3.1 CPU-First Defaults ✅ COMPLETE
**Priority:** P0  
**Status:** ✅ Completed 2026-01-09  
**Files:** `lib/user.sh`, `.env` templates, `README.md`

**Tasks:**
- [x] Define CPU/iGPU default coder model for low RAM/VRAM
- [x] Use VRAM + RAM to recommend heavier models only when feasible
- [x] Document CPU/iGPU behavior as the default tier

**Success Criteria:**  
- CPU-only deploy works without GPU assumptions  
- Default coder model loads in < 5 minutes on CPU  
- Default embedding model loads in < 2 minutes  

---

## Phase 4: Observability + Gates (P1) 📊

### 4.1 Post-Install Health Gates ✅ COMPLETE
**Priority:** P1  
**Status:** ✅ Completed 2026-01-09  
**Files:** `phases/phase-08-finalization-and-report.sh`, `scripts/initialize-ai-stack.sh`

**Tasks:**
- [x] Add strict post-install validation (system + AI health)
- [x] Fail deploy if critical services remain unhealthy
- [x] Gate dashboard generation on green health

**Success Criteria:**  
- < 5% false-success rate  
- All core services healthy before completion  

---

## Phase 5: UX + Workflow Simplification (P1) 🧭

### 5.1 Consolidate AI Prompts 🕒 PLANNED
**Priority:** P1  
**Status:** ✅ Completed 2026-01-09  
**Files:** `phases/phase-09-ai-model-deployment.sh`

**Tasks:**
- [x] Merge AI stack decision points into one prompt section
- [x] Remove overlapping “hybrid” prompts and repeated downloads
- [x] Provide explicit outcomes in prompts

**Success Criteria:**  
- 30% fewer prompts in default run  
- 0 duplicated steps in deployment logs  

---

## Phase 6: Rollout Readiness (P1) 🚀

### 6.1 Release Acceptance Checklist 🕒 PLANNED
**Priority:** P1  
**Status:** 🚧 In Progress  
**Files:** `docs/TEST-CHECKLIST.md`, `docs/PRODUCTION-HARDENING-ROADMAP.md`

**Tasks:**
- [x] Add hardware tiers + expected performance table
- [x] Add CI drift checks for `.env` vs compose/templates
- [x] Final acceptance checklist for team rollout

**Success Criteria:**  
- 100% reproducibility on CPU-only, iGPU, and GPU reference machines  
- No manual fixes post-deploy  

---

## ✅ Progress Summary

- Phase 1 (Cohesion & Defaults): **3/3 complete**  
- Phase 2 (Model Coordination): **3/3 complete**  
- Phase 3 (CPU/iGPU Defaults): **1/1 complete**  
- Phase 4 (Observability Gates): **1/1 complete**  
- Phase 5 (UX Simplification): **1/1 complete**  
- Phase 6 (Rollout Readiness): **1/1 complete**

---

## Acceptance Checklist (Must Pass Before Rollout)
- **Install Time:** ≤ 60 minutes CPU-only, ≤ 45 minutes GPU  
- **Health Checks:** All core services healthy (AIDB, Qdrant, llama.cpp, embeddings)  
- **Model Swap:** Coder + embeddings swappable via one command (no manual edits)  
- **No Dupes:** No duplicate model downloads in a single run  
- **Dashboard:** Cached + active models visible + accurate  

---

## Definition of Done
- All phases use the same model defaults  
- Swaps are reliable and documented  
- CPU-only installs have no GPU assumptions  
- “Success” means a working, healthy system
