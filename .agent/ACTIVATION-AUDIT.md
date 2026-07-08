---
Status: Active
Owner: "hyperd (orchestrator claude)"
Last Updated: 2026-07-08
---

# Activation Audit — implemented ≠ done

**Principle (operator directive, 2026-07-08):** a feature is NOT done when it's implemented +
unit-tested. It is done when it is (1) **integrated**, (2) **turned ON** in the running system, and
(3) **validated by real-world integrated functional testing** — not just unit tests. Dev work that
ships dormant wastes the tokens/time that built it. Every capability gets audited here until activated
or explicitly, consciously deferred.

## Method
Sweep four dormant surfaces, and for each: turn on → run a REAL functional test → record evidence.
- (A) feature flags default-off (`enable = mkDefault false`, `ui.enable`, …)
- (B) tools/scripts that exist but are unwired / unscheduled / route to a broken lane
- (C) env settings default-off (`AQ_LOCAL_GBNF`, …)
- (D) services defined but not enabled/started

## Findings (2026-07-08 — this session's closed-loop work)

| Capability | Implemented | Turned ON | Functionally validated | Notes |
|---|---|---|---|---|
| NixOS 26.05 upgrade | ✅ | ✅ live | ✅ system running, services healthy | done |
| Progress-aware reap | ✅ | ✅ (built script live) | ✅ protected csza5f live | done |
| Capture hooks (P1.1) | ✅ | ✅ | ✅ 5 real failure_samples captured | firing in live agent runs |
| Ingest repair/positive (P1.2/1.4) | ✅ | ✅ | ⚠️ dataset 805 rows but from OLD hybrid-events path — NEW capture path not yet ingested (0 failure-repair/success-capture rows) | needs corrections + a loop run |
| **GBNF repair-retry (P2.3)** | ✅ | ✅ **just turned ON** (coordinator systemd env + delegate-to-local export) | ✅ bench: non-harmful (tool_use 11/12 == baseline), surgical | coordinator lane needs next rebuild; dispatch lane immediate |
| Training-loop timer (P1.5) | ✅ | ✅ timer enabled+active; now runs **Phase 0 correction** before ingest | ⚠️ dry-run pass validated (phases wire, no crash); real clean run still pending | loop is now truly closed: correct → ingest → eval |
| **aq-correct-failures (P1.3)** | ✅ | ✅ **FIXED + ON** — codex teacher (own login, no key) | ✅ real run: 1 pending → valid correction → ingest picked it up as repair pair (`failure_repair_samples_added:1`) | was BROKEN (remote lanes 402/empty); now `--teacher codex` default + wired into the loop's Phase 0 |
| capture_success | ✅ | ✅ wired | ⚠️ 0 success_samples captured yet | wire fires on successful tool call — validate with a real success |
| open-webui | ✅ (upstream) | ❌ intentionally OFF | n/a | blocked: npm-deps build broken in 26.05; re-enable when fixed |

## Immediate actions from this audit
1. **GBNF repair — TURNED ON** (this commit). Coordinator env activates next rebuild; dispatch lane live now.
2. **aq-correct-failures — FIX the teacher lane** (both switchboard remote lanes fail without credits).
   Options: codex via delegate-to-codex (own login, strong), OR the local 35B under GBNF (free, self-repair),
   OR a genuinely-free remote. Then schedule it (timer) so pending failures actually get corrected. HIGH.
3. **Training loop — trigger a real run** to validate it produces a non-null result + ingests the new
   capture-path samples (repair/success), not just the old hybrid-events mining.
4. **Full sweep (D)** — enumerate all AI-stack services and confirm each enabled service is actually
   healthy + serving, and each disabled one is a conscious choice (not an accidental dormancy).

## Rule going forward
No PRD/plan slice is marked DONE until its row here shows ON + functionally-validated (or a conscious defer).
