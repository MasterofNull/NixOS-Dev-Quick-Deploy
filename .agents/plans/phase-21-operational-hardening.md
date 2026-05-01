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

### 21.2 — Flake Local-Override Visibility ✅ DONE (commit 8a10eaa3)

Problem: `deploy-options.local.nix` is gitignored → flake evaluation uses git-tracked source tree
→ `./. + "path"` resolves to Nix store copy (no gitignored files) → `builtins.pathExists` returns false
→ `mySystem.aiStack.switchboard.remoteUrl = lib.mkForce null` is silently ignored
→ coordinator always gets `SWITCHBOARD_REMOTE_URL=https://openrouter.ai/api`
→ delegate tries OpenRouter free tier → rate limited (18 failures) + HTTP errors (24 failures)

Fix:
- `flake.nix`: use `builtins.getEnv "NIXOS_REPO_PATH"` to resolve absolute filesystem path
  for `hostDeployOptionsLocalPath` when env var is set
- `nixos-quick-deploy.sh`: pass `NIXOS_REPO_PATH=${REPO_ROOT} --impure` to nixos-rebuild

Verification: `NIXOS_REPO_PATH=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy nix eval --impure '.#nixosConfigurations.hyperd-ai-dev.config.mySystem.aiStack.switchboard.remoteUrl'` → `null` ✓

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
3. ✅ `NIXOS_REPO_PATH=... nix eval --impure ...remoteUrl` → `null`
4. ⏳ `systemctl show ai-hybrid-coordinator | grep SWITCHBOARD_REMOTE_URL` → `=` (empty) after rebuild
5. ⏳ `aq-qa 0` → 40 passed / 0 failed after rebuild
6. ⏳ `aq-report` → `ai_coordinator_delegate` success rate improvement after 24h
7. ⏳ `systemctl show ai-hybrid-coordinator | grep AI_DELEGATE_LOCAL_SLOT` → max retries=4

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
- Status: **pending** (requires nixos-rebuild switch with `NIXOS_REPO_PATH`)

### Task: OP-004
- Phase: 21.3 (deferred)
- Owner: qwen (implementation)
- Files: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (add DB write in `_inject_semantic_tooling`)
- Status: **deferred** — not urgent

---

## Rollback

- 21.1: Remove env vars from `mcp-servers.nix`; rebuild. Defaults revert to 1 retry × 1.25s.
- 21.2: Revert `flake.nix` + `nixos-quick-deploy.sh`; rebuild without `--impure`.
- 21.3: N/A (not yet implemented)
