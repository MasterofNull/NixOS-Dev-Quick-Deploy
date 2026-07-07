# PRD-Consensus — Aggregate (interim)

Last Updated: 2026-07-06 (gemini pending; local failed)

## Contributors
- **claude**: APPROVE-WITH-CHANGES ✅
- **codex/gpt-5.5**: APPROVE (no required changes, substantive risks added) ✅
- **local[Qwen]**: FAILED ❌ — `no-progress timeout: server silent for >420s`. Agent-mode
  context (grounding + tools + 137-line PRD) exceeds the APU first-token prefill budget;
  direct-mode produced 0 bytes in PASS-1. Measured capability limit — local cannot do
  large-context consensus review on this hardware. [FINDING logged.]
- **gemini**: ⏳ file/git A2A pending.

## CONSENSUS VERDICT (2/2 landed): APPROVE-WITH-CHANGES
Both independent passes approve the design; the "changes" are pre-implementation refinements,
not blockers. The two sets are **complementary** — codex's numeric budgets fill exactly the
threshold gap claude flagged (C2). Strong signal.

## Consolidated required changes → fold into PRD v2 (before Phase 0)
1. **Keystone wire contract** (claude C1): where `zero_trust` is set (switchboard on ingest,
   from `secret_findings`), how ONE field propagates to both tool-filter and router, default=false.
2. **`zero_trust` FAIL-CLOSED** (codex, CRITICAL): if `a2a_guard` result is absent/stale/
   malformed/unavailable → treat as `zero_trust=true`. Degraded guard plumbing must never
   silently restore privileged routing.
3. **Re-evaluate `zero_trust` per request** (claude): a secret entering mid-conversation must
   flip the flag; never latch once at task start.
4. **Numeric acceptance thresholds** (claude C2 + codex budgets):
   - GBNF accepted only if it removes ≥90% of repair attempts on the golden suite.
   - Sandbox startup p95 ≤ 750 ms (edit/yolo), ≤ 1500 ms (eval).
   - Grammar conversion p95 ≤ 100 ms (cache miss), ≤ 10 ms (cache hit); end-to-end tool-call
     latency regression ≤ 8% (local 8B/35B).
   - 35B session-load p95 > 45 s → keep 35B as an explicit session mode only (resident 8B default).
5. **Structured sandbox failure reason codes** (codex): every sandbox exit classified as
   `policy_denied | missing_bind | resource_limit | tool_catalog_denied | process_error | timeout`,
   visible in logs/telemetry/dashboard. Raw stderr is not enough.
6. **Network = time-bound capability lease** (claude C3 + codex): scoped by destination class +
   task id, revoked via the same dispatch/capability state as the reduced tool catalog. No global
   "network allowed" profile.
7. **Grammar-cache invalidation key** (codex + claude): include final post-lease tool schema, tool
   names, argument schemas, AND `zero_trust` filter state — stale grammar could re-enable stripped
   tools or reject newly-valid calls.
8. **Remote downgrade deterministic fallback** (codex): large-context AND `zero_trust` → local
   chunking or an explicit refusal contract, not just "block remote" (which becomes an
   availability failure).
9. **Nix-store bind = store root, not hashed subpaths** (claude): bwrap binds `/nix/store` ro;
   never pin hashed paths (break on rebuild).
10. **Grammar-gen fallback** (claude): if `json_schema_to_grammar` fails on a complex schema,
    degrade to non-grammar decode (log + proceed), never block the call.

## Decision
Ratify **APPROVE-WITH-CHANGES**: fold changes 1–10 into PRD v2, then Phase-0 keystone is
buildable. Hold final ratification for gemini's `gemini.md` (fold any additions); local is
excused (capability limit). PASS-2 angles (ops/failure-recovery, tokenomics) are captured in
the per-agent files and changes 4–8.

---
## UPDATE — 3-agent consensus reached (gemini landed)
- **gemini**: APPROVE-WITH-CHANGES ✅ (own file, no race — per-agent protocol validated again).
- **Contributors now**: claude (APPROVE-WITH-CHANGES), codex (APPROVE), gemini (APPROVE-WITH-CHANGES).
  local[Qwen] re-dispatched with a 1800s first-token budget (eo9h11, running — was killed at 420s);
  will be folded if it lands.

### CONSENSUS: APPROVE-WITH-CHANGES (3/3 landed)
Gemini reinforced the keystone wire contract (concrete: `zero_trust: bool = false` in the base
switchboard request model), grammar-gen fallback (#10), network capability lease (#6), mid-conv
re-eval (#3), and path canonicalization (#9 red-team). Three independent passes, highly convergent.

### Additional changes from gemini (fold into PRD v2)
11. **VRAM pool manager (Slice 3, NEW)**: running 8B + 35B concurrently thrashes the 4GB APU.
    A strict pool manager must UNLOAD inactive models before initializing a new session if the
    memory-headroom is exceeded. (Sharpens R3.3 — resident-small is not free; enforce headroom.)
### Refinements (fold into existing changes)
- #6 network lease → a **coordinator-SIGNED time-bound token** scoped by destination class + task id
  (gemini strengthens "lease" to a cryptographic token; no global network profile).
- #5 sandbox failure reason codes → **stream categorized failures to `a2a-audit.log`** for dashboard
  inclusion (gemini ties diagnostics to the existing A2A audit trail).
- Concrete PASS-2 numbers: bwrap startup <5ms (gemini) / p95 ≤750ms budget (codex); GBNF saves
  ~1.5s per invalid 35B call (gemini); clamp swaps if tasks queued within a 20s window (gemini).

### Decision
**RATIFY APPROVE-WITH-CHANGES.** Fold changes 1–11 (+ refinements) into PRD v2 → Phase-0 keystone
is buildable. Qwen may append; local is not a blocker.

### local[Qwen] final (eo9h11)
COMPLETED (2333s, no timeout — the 1800s first-token budget fixed the premature kill) but produced NO usable verdict: it spent its turns reading the PRD in chunks and never wrote local.md. Finding: with enough time Qwen *completes*, but is not a reviewer-tier lane for large-context multi-step review on this APU. Excused from review-class tasks; retained for bounded single-edit work.
