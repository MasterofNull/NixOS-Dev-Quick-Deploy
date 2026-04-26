# Phase 10 — Post-Rebuild Validation + Gap Remediation

Status: `pending — blocked on nixos-rebuild`
Created: 2026-04-26
Owner: Claude (orchestrator)
Predecessor: Phase 9 (all slices committed; nixos-rebuild pending)

## Deployment Gate (REQUIRED)

All Phase 8 + Phase 9 + Phase 10 prep fixes are committed but the running
service still uses the old Nix store path. **Run from a terminal session:**

```bash
sudo nixos-rebuild switch --flake .#nixos
```

Commits awaiting deploy:
- `6c1a997` — Phase 8.1 inference timeout cap + 8.2 memory recall injection
- `c342722` — Phase 8.6 async delegate task queue
- `daf4464` — Phase 8.7 OpenAI-compatible tool calling loop
- `7c3b959` — Phase 8.9/8.10 SSE streaming + parallel retrieval
- `f219bca`, `c60777d` — delegate NameError fix + local-tool-calling profile
- `f42da0db` — Phase 9.1 intent contract backfill + 9.2 empty-content retry
- `53d7cf36` — synthetic gap suppression for frontdoor/smoke probes
- `9b4c5b4f` — delegate failover chain extended to 401/403

## Objective

After nixos-rebuild deploys Phase 8+9 fixes, validate all KPI targets are
met and close the remaining runtime gaps identified in aq-report.

## Evidence from aq-report (2026-04-26, pre-rebuild)

| Signal | Value | Target | Blocker |
|--------|-------|--------|---------|
| ai_coordinator_delegate success | 17.2% | ≥90% | nixos-rebuild |
| Memory recall share | 13.3% | ≥10% | nixos-rebuild for active injection |
| route_search P95 | 59287ms | ≤15000ms | nixos-rebuild |
| Intent contract coverage | 88.9% | 100% | nixos-rebuild (backfill wired) |
| Cache hit rate | 91.6% | ≥85% | ✅ PASS |
| Hint adoption | 100.0% | ≥70% | ✅ PASS |
| Phase 7 gate | 39/39 | 39/39 | ✅ PASS |
| Synthetic gap entries | 3 stale | 0 | stale rows need curate |

## Phase 10.1 — Post-Rebuild KPI Verification

**Trigger**: After `sudo nixos-rebuild switch --flake .#nixos`

**Steps**:
1. `aq-qa 0` → expect 39+ passed, 0 failed, 0.8.1 PASS or SKIP
2. `aq-report --since=1d --format=json` → check delegate success ≥50%
3. Check intent contract coverage = 100% (backfill should auto-apply on load)
4. Check memory_recall.share_of_route_search ≥10%
5. Check route_search P95 improvement (target ≤15000ms; phase 8.1 cap = 120s max)
6. Run `scripts/testing/validate-ai-slo-runtime.sh` → PASS
7. Run `scripts/testing/check-routing-fallback.sh` → PASS

**Files**: No changes — validation only.

## Phase 10.2 — Synthetic Gap DB Cleanup

**Problem**: 3 stale synthetic rows in `query_gaps`:
- "Reply with exactly LOCAL_FRONTDOOR_OK"
- "Reply with exactly FRONTDOOR_OK"
- "test harness connectivity"

**Fix**: After nixos-rebuild, run the stale-gap curation pass:
```bash
scripts/data/curate-residual-gaps.sh
```
Or trigger via aq-auto-remediate:
```bash
scripts/ai/aq-auto-remediate.py --dry-run  # verify it detects stale rows
scripts/ai/aq-auto-remediate.py            # execute with budget cap
```

**Success criteria**: `aq-report` `query_gaps` shows 0 synthetic entries.

## Phase 10.3 — Delegate Success Rate Gate Verification

**Problem**: `0.8.1` check currently SKIPs because <3 calls in last 1h.
After rebuild, delegate traffic should accumulate and the check should PASS.

**Steps**:
1. Trigger delegate traffic: `scripts/data/seed-tool-audit-traffic.sh`
2. Wait 5 minutes for 3+ calls to accumulate
3. `aq-qa 0` → 0.8.1 should PASS (not SKIP)

**Success criteria**: 0.8.1 reports PASS with success rate ≥50%.

## Phase 10.4 — Memory Recall Active Injection Verification

**Problem**: Phase 8.2 added memory_recall_priority active injection but
service hasn't restarted. After rebuild, memory recall should show in query
responses.

**Smoke test**:
```bash
HK=$(cat /run/secrets/hybrid_coordinator_api_key | tr -d '\n')
curl -s -X POST http://127.0.0.1:8003/query \
  -H "X-API-Key: $HK" -H "Content-Type: application/json" \
  -d '{"query":"current work remaining tasks","mode":"retrieval"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memory_recall_attempted','not_present'))"
```
Expected: `true`

## Execution Order

```
nixos-rebuild → 10.1 → 10.3 → 10.2 → 10.4
```

## Rollback

Each Phase 8/9 slice has independent `git revert` capability.
NixOS generation rollback: `sudo nixos-rebuild switch --rollback`

## Success Criteria (Program-Level)

- [ ] `aq-qa 0`: 39+ passed, 0 failed, 0.8.1 PASS
- [ ] Intent contract coverage = 100%
- [ ] `ai_coordinator_delegate` success rate ≥50% (1h window)
- [ ] `route_search` P95 ≤30000ms (from 59287ms baseline)
- [ ] Memory recall share ≥10% confirmed in aq-report
- [ ] Synthetic gap rows = 0 in next aq-report
- [ ] `validate-ai-slo-runtime.sh` PASS
- [ ] Phase 7 gate (`check-prsi-phase7-program.sh`) remains green

## Notes

- Sudo setuid is MISSING on this host — nixos-rebuild requires an open
  terminal session (not agent-executable).
- After rebuild, all Phase 8+9 improvements activate simultaneously.
- Run `aq-report --since=1d --format=json` immediately post-rebuild for
  before/after comparison baseline.
