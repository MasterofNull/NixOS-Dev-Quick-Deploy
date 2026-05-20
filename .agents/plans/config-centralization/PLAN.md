# Config Centralization & Routing Standardization — Implementation Plan

**PRD:** `.agent/PROJECT-CONFIG-CENTRALIZATION-PRD.md`  
**Status:** READY TO EXECUTE  
**Date:** 2026-05-20  

---

## Phase A — Env Var Contract (2 files, no service restarts)
**Goal:** One authoritative document; tier0 gate to enforce it going forward.

| Slice | File | Owner | Validation |
|-------|------|-------|-----------|
| A.1 | Create `config/env-contract.yaml` with all variable names, defaults, aliases, layers | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/env-contract.yaml'))"` |
| A.2 | Add tier0 gate: new `.py`/`.sh` files may not introduce env var names absent from contract | Claude | `scripts/governance/tier0-validation-gate.sh --pre-commit` |
| A.3 | Update `AGENTS.md` — reference `config/env-contract.yaml` as env var authority | Claude | manual review |

**Commit scope:** `config/env-contract.yaml`, `scripts/governance/tier0-validation-gate.sh`, `AGENTS.md`  
**Rebuild required:** No

---

## Phase B — Externalized Switchboard Profiles (3 files, switchboard restart)
**Goal:** Token budgets in YAML, loaded at startup, validated against ctxSize.

| Slice | File | Owner | Validation |
|-------|------|-------|-----------|
| B.1 | Create `config/switchboard-profiles.yaml` with all 13 profiles + ctxSize validation metadata | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/switchboard-profiles.yaml'))"` |
| B.2 | Modify `ai-stack/switchboard/switchboard.py`: `_load_profile_catalog()` to accept YAML via `SWB_PROFILE_CATALOG_YAML_FILE` (JSON file support already exists; add YAML) | Codex | `python3 -m py_compile ai-stack/switchboard/switchboard.py` |
| B.3 | Add startup validation: warn if `maxInputTokens + maxOutputTokens > LLAMA_CTX_SIZE - 600` | Codex | `aq-qa 0.5.4` (continue-local profile smoke) |
| B.4 | Wire `SWB_PROFILE_CATALOG_YAML_FILE = config/switchboard-profiles.yaml` in `nix/modules/roles/ai-stack.nix` | Claude | nixos-rebuild switch |

**Commit scope:** `config/switchboard-profiles.yaml`, `ai-stack/switchboard/switchboard.py`, `nix/modules/roles/ai-stack.nix`  
**Rebuild required:** Yes (for NixOS env var propagation)

---

## Phase C — Routing Policy Config (2 files, coordinator restart)
**Goal:** `auto_prefer_local` heuristic configurable, not hardcoded.

| Slice | File | Owner | Validation |
|-------|------|-------|-----------|
| C.1 | Create `config/routing-policy.yaml` with `auto_prefer_local_when`, `intent_routing`, `slot_busy` | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/routing-policy.yaml'))"` |
| C.2 | Modify `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`: load routing policy from `AI_ROUTING_POLICY_FILE` at init; replace hardcoded `timeout_s <= 10.0` with configured value | Codex | `python3 -m py_compile` + `aq-qa 0.7.1` smoke |
| C.3 | Wire `AI_ROUTING_POLICY_FILE = config/routing-policy.yaml` in coordinator NixOS service env | Claude | nixos-rebuild switch |

**Commit scope:** `config/routing-policy.yaml`, `ai_coordinator_handlers.py`, `nix/modules/roles/ai-stack.nix`  
**Rebuild required:** Yes

---

## Phase D — URL/Key Alias Standardization (5-7 files, no restart)
**Goal:** Canonical names everywhere; deprecated aliases as backward-compat shims with 30-day sunset.

| Slice | File | Owner | Validation |
|-------|------|-------|-----------|
| D.1 | `dashboard/backend/api/config/service_endpoints.py`: rename `LLAMA_URL` → `LLAMA_CPP_BASE_URL`, add alias shim | Codex | `python3 -m py_compile` + grep confirms 0 raw `LLAMA_URL` reads in new code |
| D.2 | `config/service-endpoints.sh`: rename `LLAMA_URL` → `LLAMA_CPP_BASE_URL` primary; alias shim exports old name | Claude | `bash -n` |
| D.3 | `ai-stack/switchboard/switchboard.py`: reads `HYBRID_COORDINATOR_URL` (was inline coord URL assumption) | Codex | switchboard health smoke |
| D.4 | `scripts/testing/_mock_config.py`: use `LLAMA_CPP_BASE_URL` canonical | Claude | `python3 -m py_compile` |
| D.5 | `dashboard/backend/api/routes/topology.py` + `api/main.py`: remove hardcoded `127.0.0.1:8080` etc., import from `service_endpoints` | Codex | `grep -r "127\.0\.0\.1:[0-9]" dashboard/backend/ | wc -l` → 0 |
| D.6 | `scripts/ai/aq-qa`, `scripts/ai/edgeai`: use contract variable names | Claude | `aq-qa 0` green |

**Commit scope:** dashboard config, shell configs, test mock config, topology route  
**Rebuild required:** No (env var aliases cover runtime)

---

## Phase E — Config Directory Governance (CI only)
**Goal:** Every `config/` file is versioned, owned, and validated in CI.

| Slice | File | Owner | Validation |
|-------|------|-------|-----------|
| E.1 | Add `_meta` header to all `config/*.json` and `config/*.yaml` that lack one | Codex | tier0 JSON/YAML gate |
| E.2 | Add `scripts/governance/config-directory-lint.sh` — checks for `_meta`, no duplicate keys across domain-overlapping files | Claude | tier0 gate |
| E.3 | Remove or archive orphaned config files (not referenced by any service) | Codex | grep audit |

**Commit scope:** all `config/` files (meta headers only), new lint script  
**Rebuild required:** No

---

## Execution Order

```
Phase A → (no restart needed) → commit
Phase B → (nixos-rebuild) → commit
Phase C → (nixos-rebuild) → commit
Phase D → (no restart, alias shims cover runtime) → commit
Phase E → (no restart, CI only) → commit
```

Phases A and D.1-D.4 can run in parallel. Phase B must precede Phase C (both need nixos-rebuild; batch into one rebuild).

---

## Handoff Notes for Codex

When resuming (after 1:26pm):
1. Start with **Phase A.1** — `config/env-contract.yaml` (no code changes, pure data)
2. Then **Phase B.1** — `config/switchboard-profiles.yaml` (transcribe from switchboard.py current values)
3. Then **Phase B.2** — YAML loading in switchboard (existing JSON path is the model to follow)
4. Gate every slice with: `bash -n` / `py_compile` / `aq-qa 0` before commit
5. Do NOT change any API surface, endpoint path, or NixOS option name
6. Do NOT batch Phases B+C into one commit — keep separate for rollback hygiene

**First command to run when resuming:**
```bash
aq-session-start --task "config-centralization Phase A.1: create config/env-contract.yaml"
```
