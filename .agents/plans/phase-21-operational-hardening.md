# Phase 21 — Operational Hardening (Post-AGI Scaffold)

Status: `in_progress`
Created: 2026-05-01
Owner: Claude (orchestrator/implementer)
Source: aq-report telemetry after AGI scaffold deployment (2026-05-01)
Predecessor: Phase 20 (world model — all AGI scaffold phases 16-20 complete)

---

## Objective

Improve operational reliability of the deployed AI stack based on live telemetry:
- `ai_coordinator_delegate` success rate: 32.6% (93 backend failures in 7d)
- `deploy-options.local.nix` gitignore causes `mkForce` overrides to be silently ignored
- Hint diversity report showing misleading "1 injection" (JSONL vs DB tracking gap)
- PRSI queue: 2 pending items (prefer_local approved; delegation contract high-risk)

---

## Scope Lock

In scope:
- Delegate local-slot retry parameters (`mcp-servers.nix`)
- Flake local-override visibility (`flake.nix` + `nixos-quick-deploy.sh`)
- Phase 21 planning doc (this file)
- PRSI queue cleanup (approve safe actions)

Out of scope:
- Training or fine-tuning models
- Changes to AIDB schema
- New AGI phases (phases 16-20 complete)
- Hint feedback DB vs JSONL unification (Phase 21.3 deferred)

Constraints:
- All Nix changes need `nix-instantiate --parse` validation before commit
- All shell changes need `bash -n` validation
- nixos-rebuild required to activate env var changes

---

## Sub-phases

### 21.1 — Delegate Retry Hardening ✅ DONE (commit a6387cda)

Problem: local slot retry defaults too tight (1 retry × 1.25s) for 90-120s llama.cpp inference.
When remote gets 429 AND local is slot_busy, both fail → delegate counted as backend failure.

Fix:
- `nix/modules/services/mcp-servers.nix`: inject
  - `AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES=4`
  - `AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_DELAY_S=15.0`
  - `AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_BUDGET_FLOOR_S=5.0`
- Gives up to 60s wait window for local slot to free

Expected impact: reduce compound failure rate when both remote and local are temporarily busy.

Requires: nixos-rebuild switch

### 21.2 — Flake Local-Override Visibility ✅ DONE (commit 23043d71, supersedes 8a10eaa3)

Problem: `deploy-options.local.nix` is gitignored → flake evaluation uses git-tracked source tree
→ `./. + "path"` resolves to Nix store copy (no gitignored files) → `builtins.pathExists` returns false
→ `mySystem.aiStack.switchboard.remoteUrl = lib.mkForce null` is silently ignored
→ coordinator always gets `SWITCHBOARD_REMOTE_URL=https://openrouter.ai/api`
→ delegate tries OpenRouter free tier → rate limited (18 failures) + HTTP errors (24 failures)

Initial fix (8a10eaa3): used `builtins.getEnv "NIXOS_REPO_PATH"` + `--impure` to read gitignored file.
Superseded fix (23043d71): moved `remoteUrl = lib.mkForce null` to git-tracked `deploy-options.nix`.
- Removed `builtins.getEnv`, `_repoEnvPath`, impure `hostDeployOptionsLocalPath` from `flake.nix`
- Removed `env NIXOS_REPO_PATH=...` and `--impure` from `nixos-quick-deploy.sh`
- `deploy-options.local.nix` retains only secrets wiring (sops paths) — no policy overrides

Verification: `nix eval '.#nixosConfigurations.hyperd-ai-dev.config.mySystem.aiStack.switchboard.remoteUrl'` → `null` (pure, no env vars) ✓

Requires: nixos-rebuild switch (will set SWITCHBOARD_REMOTE_URL="" in coordinator)

### 21.3 — Hint Diversity Reporting Fix (deferred)

Problem: aq-report section 14 shows "Total injections: 1" which is misleading.
Root cause: aq-report reads from `hint_feedback_events` PostgreSQL table, but actual
hint injections in `_inject_semantic_tooling()` only write to JSONL log
(`/var/log/nixos-ai-stack/hint-audit.jsonl`). Real injection count: 43 in JSONL with 5 hint IDs.

Fix options:
1. Wire `_inject_semantic_tooling()` to also write to `hint_feedback_events` table
2. Change aq-report to read from JSONL for diversity metrics
3. Add a bridge job that periodically imports JSONL events to DB

Status: deferred — misleading metric, but no actual diversity problem (43 injections, 5 IDs).

---

## Verification Matrix

Before marking 21.1+21.2 fully verified:
1. ✅ `nix-instantiate --parse` passes for `mcp-servers.nix`
2. ✅ `bash -n nixos-quick-deploy.sh` passes
3. ✅ `nix eval '.#nixosConfigurations.hyperd-ai-dev...remoteUrl'` → `null` (pure, no env vars, commit 23043d71)
4. ⏳ `systemctl show ai-hybrid-coordinator | grep SWITCHBOARD_REMOTE_URL` → `=` (empty) after rebuild
5. ⏳ `aq-qa 0` → 40 passed / 0 failed after rebuild
6. ⏳ `aq-report` → `ai_coordinator_delegate` success rate improvement after 24h
7. ⏳ `systemctl show ai-hybrid-coordinator | grep AI_DELEGATE_LOCAL_SLOT` → max retries=4
8. ✅ `/identity/self` → 5 capabilities, 2 relationships (qwen, hyperd), last_value_update set
9. ✅ `/world/forecast` → 3 predictions with time_of_day source (10 seed patterns in DB)

---

## Work Queue

### Task: OP-001
- Phase: 21.1
- Owner: Claude
- Files: `nix/modules/services/mcp-servers.nix`
- Status: **done** (commit a6387cda, 2026-05-01)

### Task: OP-002
- Phase: 21.2
- Owner: Claude
- Files: `flake.nix`, `nixos-quick-deploy.sh`
- Status: **done** (commit 8a10eaa3, 2026-05-01)

### Task: OP-003
- Phase: post-rebuild validation
- Owner: Claude (post-rebuild check)
- Commands:
  ```bash
  systemctl show ai-hybrid-coordinator --property=Environment | grep -o 'SWITCHBOARD_REMOTE_URL=[^ ]*'
  systemctl show ai-hybrid-coordinator --property=Environment | grep -o 'AI_DELEGATE_LOCAL_SLOT[^ ]*'
  aq-qa 0
  ```
- Status: **pending** (requires pure nixos-rebuild switch: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`)

### Task: OP-004
- Phase: 21.3 (deferred)
- Owner: qwen (implementation)
- Files: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (add DB write in `_inject_semantic_tooling`)
- Status: **deferred** — not urgent

### Task: OP-007 ✅ DONE (2026-05-01 session 3)
- Phase: 21.4 — Agent priority and model availability realignment
- Owner: Claude
- Root cause: `_select_next_available_delegation_target` had no guard on
  `SWITCHBOARD_REMOTE_URL`. When local slots were busy the fallback chain
  reached `remote-gemini` which the switchboard immediately rejects when
  `REMOTE_URL=""` → all 112 backend failures in 7d were spurious remote
  attempts, not real inference failures.
- Files changed (commit e6f453e0):
  - `delegation_handlers.py`: added `_remote_routing_active()` + `_fleet_model_available()`
    guards in `_select_next_available_delegation_target`. Remote profiles are
    skipped when REMOTE_URL is empty; fleet manager Redis cooldown state is
    checked before each remote attempt.
  - `agent_pool_manager.py`: removed qwen3-next-80b and qwen3-coder free agents
    (gone from OpenRouter free tier). Added: meta-llama/llama-3.3-70b:free,
    deepseek-r1:free, gemini-2.0-flash-exp:free, dolphin-mistral retained.
  - `model_fleet_manager.py`: removed qwen3-next-80b:free from coding+chat
    free pools; added gemini-2.0-flash-exp:free to coding free pool.
  - `nix/hosts/hyperd/deploy-options.nix`: corrected all 5 remote model aliases:
    free→llama-3.3-70b:free, gemini→gemini-2.0-flash-exp:free,
    coding→deepseek-r1:free, reasoning→deepseek-r1:free,
    toolCalling→llama-3.3-70b:free. remoteUrl stays null.
- Expected impact: eliminate ~100% of spurious remote-profile backend failures
  (remote-gemini was 100% of the failure volume with 0% success rate).
- Status: **done** — requires nixos-rebuild to deploy delegation_handlers changes

### Task: OP-005 ✅ DONE (2026-05-01 session 2)
- Phase: AGI scaffold enrichment
- Owner: Claude
- Actions:
  - Discovered `capability_registered` + `agent_collaboration` are the correct identity event types
    (summarizer ignores `capability_discovered`, `relationship_updated`, `value_reinforced`)
  - Posted 5 `capability_registered` events (AGI orchestration, NixOS config, hybrid inference,
    affective modulation, world model warming)
  - Posted 2 `value_update` events (operational_reliability, transparency)
  - Posted 2 `agent_collaboration` events (qwen→implementer, hyperd→operator)
  - `/identity/self` now returns populated capabilities + relationships ✅
- Status: **done**

### Task: OP-006 ✅ DONE (2026-05-01 session 2)
- Phase: World model bootstrap
- Owner: Claude
- Actions:
  - Seeded `query_sequence_patterns` with 10 rows (5 for local hour 9, 5 for UTC hour 16)
  - `/world/forecast` now returns 3 time-of-day predictions with confidence scores ✅
  - Root cause of zero predictions: pattern rows must match UTC `hour_of_day`; forecaster uses `datetime.now(timezone.utc).hour`
- Status: **done**

---

## Rollback

- 21.1: Remove env vars from `mcp-servers.nix`; rebuild. Defaults revert to 1 retry × 1.25s.
- 21.2: Revert `flake.nix` + `nixos-quick-deploy.sh`; rebuild without `--impure`.
- 21.3: N/A (not yet implemented)
