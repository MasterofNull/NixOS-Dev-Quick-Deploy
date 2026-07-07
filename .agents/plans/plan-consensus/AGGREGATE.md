# Plan-Consensus — Aggregate (interim; ROUND OPEN for Qwen + gemini)

Last Updated: 2026-07-07

## Contributors
- **claude**: APPROVE-WITH-CHANGES ✅
- **codex/gpt-5.5**: APPROVE-WITH-CHANGES ✅ (own file, no race)
- **local[Qwen]**: APPROVE-WITH-CHANGES ✅ (`xafygf`, completed 671s/~11min — inlining worked; unique contributions below).
- **gemini**: ⏳ file/git A2A pending.

## Consensus (3/3 landed): APPROVE-WITH-CHANGES  [gemini still pending]
Both approve the keystone-first design; both require precedence/edge hardening before coding.
Strongly convergent — codex extends claude's PC1/PC3 with concrete bypass vectors.

## Resolved design tension (claude PC1 ↔ codex re-eval) — IMPORTANT
- claude PC1: `zero_trust` sticky-true — once true, never flip back even if the secret message is
  pruned from context (else pruning re-grants privilege = vuln).
- codex: per-request re-eval, "never stored as a conversation/session latch"; caller-supplied
  `true` may only RAISE, never lower.
- **Synthesis (adopt):** `zero_trust` is **task-scoped MONOTONIC (raise-only)** — re-derived each
  request from the CURRENT messages, then OR'd with the task's prior state:
  `zt = task_sticky OR scan(current_messages); task_sticky |= zt`. This is NOT a cross-session
  latch (codex's concern) and resolves the prune-downgrade vuln (claude's concern). Caller `false`
  is ignored; caller `true` raises only.

## Consolidated required changes (fold into Phase-0 plan v2)
1. **Derivation (P0.1):** canonical `zero_trust: bool` + `zero_trust_kinds: list`; task-scoped
   monotonic raise-only (above); fail-closed via ONE unit-tested helper collapsing ALL failure
   cases (exception / malformed / missing import / stale-unparseable) → `true`. Ignore caller
   `false`; honor caller `true` (raise only).
2. **Scan scope (P0.1):** scan ALL message content incl. TOOL RESULTS (claude PC2); bound the
   scanned text / reuse a bounded extractor so large contexts don't pay unbounded traversal (codex).
3. **Tool-catalog strip — THREE sites (P0.2):** base catalog BEFORE `_normalize_local_tools`,
   explicit requested `tools`, AND inside `_resolve_tool_lease`; `lease_tools` must NOT reacquire
   stripped privileged tools. (claude PC3 + codex's third site + reacquire vector.)
4. **Remote block — EVERY branch (P0.3):** check `zero_trust` before every remote-return in
   `_route_target`: `forceProvider=remote`, `ROUTING_MODE=remote_only`, `x-ai-route: remote`,
   provider hints, remote model prefixes, intent routing, `DEFAULT_PROVIDER=remote`. Guard must run
   before ALL early remote returns / override branches. Deterministic fallback (PRD V9), not silent drop.
5. **Observe vs enforce (flag):** `SWB_ZERO_TRUST_ENFORCE=off` = derive + audit ONLY (no strip/
   block); on = enforce. Test both modes.
6. **Audit (P0.4):** redacted payload fields + failure-reason labeling so ops distinguish real
   findings from scanner failure; LOUD alert (not just audit) on guard-load failure — fail-closed
   disables capability fleet-wide (claude risk).

## Consolidated tests (P0.5)
Keystone (secret → tools stripped + remote blocked) · fail-closed · mid-conversation · **tool-result
secret** · **sticky-after-prune** · **observe-vs-enforce** · **caller-false-can't-downgrade** ·
**caller-true-honored** · **lease-can't-reacquire-privileged** · **forced-remote (profile/header/
model/default-provider) downgraded under enforce** · **streaming follows the block** ·
**scanner-exception → audit w/ redacted kinds + failure reason** · **clean large request under
latency budget**.

## Status
Interim: APPROVE-WITH-CHANGES. DO NOT finalize — round OPEN for Qwen (never skip local) + gemini.
Fold both, then ratify → Phase-0 plan v2 → implement P0.1.

---
## UPDATE — local[Qwen] folded (never skip local; it paid off)
Qwen APPROVE-WITH-CHANGES, with contributions the remote models MISSED — validating the
never-skip-local principle. Add to the Phase-0 plan v2:
7. **Boot-safety on fail-closed (P0.1, NEW — qwen):** a STARTUP health-check for `a2a_guard`
   load — log a loud warning but do NOT block service boot. (Sharpens change #6: fail-closed
   must not turn a broken guard into a boot failure; degrade + alert, stay up.)
8. **Explicit privileged-tool NAME list (P0.2, qwen):** enumerate the stripped tool names in the
   plan/config (not a vague "privileged set") so the filter is unambiguous + testable.
9. **Env-schema doc for `SWB_ZERO_TRUST_ENFORCE` (qwen):** document the flag (default=off) in the
   switchboard env schema so operators/consumers know it exists.
### Added test (qwen)
- **Concurrency isolation:** dispatch a clean and a secret-bearing request CONCURRENTLY; assert
  `zero_trust` is resolved per-request (the clean one keeps full catalog + routing; the secret one
  is stripped/blocked) — proves no cross-request latch under load. (Directly stress-tests the
  task-scoped-monotonic design.)

## Status
3/3 landed APPROVE-WITH-CHANGES (claude + codex + qwen). Round OPEN for gemini only.
