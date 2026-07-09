# Round rsi-readiness — Orchestrator Aggregate (FINAL)

**Aggregated**: 2026-07-09 by claude-fable-5 · **Lanes landed**: 4/4 (claude, codex, antigravity, local — all substantive).
**Status**: RATIFIED — FINAL. All four lanes concur (RATIFY ×2 + RATIFY-WITH-AMENDMENTS ×2). Local (Qwen) landed a genuine, well-formed ratification this round (2149B — not a stub), a positive capability signal on the bounded-scoring task; its scores (R1 9, R4 9, R7 9) match consensus and it reinforced antigravity's KV-thrash + operator-fatigue risks and added strict tool-level shadow confinement (folds into R4). Score means now over 4 lanes: R1 9.25 · R4 9.0 · R7 8.75 · R8 9.0 (claude+antigravity).

## Verdict: RATIFIED — all four lanes ratify-family

| Lane | Verdict | Substance |
|------|---------|-----------|
| claude (orchestrator) | RATIFY-WITH-AMENDMENTS | scores R1-R7, 4 amendments (inc. R8), slice claims |
| codex | RATIFY-WITH-AMENDMENTS | scores R1-R7, 3 amendments, slice claims, R1-first |
| antigravity | **RATIFY** | scores R1-R8 (saw R8), 3 amendments, 3 novel risks, slice claims |
| local (Qwen) | **RATIFY** | well-formed bounded ratification; R2 training-data curation claim |

All four lanes concur (RATIFY ×2 + RATIFY-WITH-AMENDMENTS ×2), R1-first, no-autonomy affirmed. Antigravity ratified as-is and contributed the round's most novel risk analysis; local landed a genuine bounded ratification and reinforces R2 training-data curation. (Typed aggregator shows ABSTAIN×3 — known parser gap: it doesn't recognize `RATIFY`/`RATIFY-WITH-AMENDMENTS`; logged in issues-backlog. This human aggregate governs.)

## Score consensus (mean of claude + codex + antigravity + local where scored)
R1 **9.25** · R2 **8.25** · R3 **8.0** · R4 **9.0** · R5 **7.25** · R6 **7.5** · R7 **8.75** · R8 **9.0** (R8 scored by claude+antigravity; codex/local pre-date R8)

Reading: R1 (eval-harness trust) is the near-unanimous global gate; R4 (shadow efficacy) and R8 (durable queue) both rose with antigravity's 10 and 9. R6 (flagship) lowest — flagged as "demo theater" risk unless R1/R4-backed.

## Adopted amendments (merged; fold into PRD)
1. **Strengthen R1 acceptance to prove scorer TRUST, not just stability** (both lanes): golden + shadow + canary tasks; must resist scorer-gaming, abstain on infra-noise, and score deterministically under parallel contention; a held-out adversarial set the scorer has never seen must rank known-good vs known-bad correctly. (R1.3)
2. **Make no-autonomy EXECUTABLE, not prose** (codex, adopted): define SHADOW as a *runtime mode* that physically cannot write/commit/deploy/enqueue verified-apply actions without an external gate — policy text won't stop accidental autonomy via orchestration glue. (R2/R4/R7)
3. **Per-workstream machine-readable activation attestation** (codex, adopted): every R-slice emits an attestation with files touched, live path wired, test evidence, and a rollback/deactivation knob — prevents green-check trust theater. (R1-R8)
4. **R2 gates on the golden set BEFORE any fine-tune ships** (claude): build the tool-use golden set, baseline, fine-tune, prove the delta on held-out cases; a strict train/eval split prevents overfit-to-golden. (R2.2/R1.3)
5. **R7 + R8 sequenced FIRST** (claude): coordination safety + rate-limit durability are the substrate protecting/sustaining all concurrent long-running slice work; R4's shadow loop will hit both concurrency and limits.
6. **R8 durable delegation queue** (claude, operator-raised, post-dispatch): park delegations on long rate-limit/session windows, auto-resume on the intended lane with event_id idempotency, round folds the resumed lane. Antigravity ratified R8 at 9/10.
7. **Golden-test isolation — the eval can be GAMED by reading it** (antigravity, CRITICAL, elevate to R1 acceptance): a local model under eval can literally read the golden test-definition files in the workspace and overfit to them. The golden suite MUST be excluded from the agent's read/search paths (system-level path filter, not just .gitignore). Without this, R1's "trustworthy signal" is defeated by the model reading the answers. (R1)
8. **Shadow runs in ephemeral git worktrees** (antigravity A2, adopt): R4 proposal evaluation must run in `isolation: worktree` ephemeral worktrees, never the primary workspace — avoids dirty git state across parallel runners. Ties R4 to R7's worktree serialization.
9. **Contention-aware eval timeouts + parked-queue observability** (antigravity A1/A3, adopt): R1 scales test timeouts by system load (extends prompt-5 contention classification) so bottlenecks don't cause false regressions; R8's park queue exposes trace-linked latency/park metrics to the dashboard so parked tasks never become silent blackholes.

## Novel risks surfaced (antigravity — none raised by claude/codex)
- **Eval gaming via prompt leak** (→ adopted as amendment 7, R1 acceptance criterion): the sharpest finding of the round.
- **KV-cache eviction under parallel shadow agents**: concurrent resident-model context swapping inflates TTFT; cache compiled prefix KV-caches (extends the cache_prompt work). Fold into R4 sequencing.
- **Quota starvation on remote cascade**: high shadow-eval volume triggers sustained remote rate-limits, locking the system despite R8's queue — needs a token-budget rate limiter at the SWITCHBOARD level (not just per-delegation). Add to R8 acceptance.

## Slice ownership (ratified; R1/R5 overlap resolved)
- **codex**: R1 harness core (golden/canary evals in aq-local-training-loop), R3 Nix+wiring (options.nix, model service, dispatch), R5 OTel plumbing (AQ_TRACE_ID propagation + OTLP hook), R7.1 git/worktree serialization + contention tests, R8 queue/scheduler.
- **claude**: R1.3 integrity gates + adversarial held-out set + trustworthy-signal SIGN-OFF, R2.1 draft-only execution contract (dispatch-level, not convention), R5.1 entrypoint seeding, R6 flagship, R7.4 coordination contract (WORKFLOW-CANON), R8 round-integration.
- **antigravity** (LANDED, claimed): R1 golden task set (code-edit + schema-validation focus) + scoring-engine design; R4 shadow-proposal ledger + sandbox validation-pipeline design. (Note: suggested phi-4-mini for R3 SMALL_RESIDENT — compare vs model_budget's Qwen2.5-1.5B during R3.)
- **local (Qwen)**: bounded audits, R2 training-data curation; its own failures = R2 data.

## Sequencing (ratified)
R1 FIRST (global gate). R7 + R8 early (substrate). R2 + R3 parallel after R1 baseline. R5 anytime. R4 after R1 (+R7/R8). R6 last. R4 efficacy data gates any future autonomy PRD.

## Immediately dispatchable (no further ratification)
- **R5.1** (AQ_TRACE_ID auto-seeding) — claude, first commit target, zero dependency.
- **R1.1** (golden task sets) — antigravity design / codex build.
- **R7.1** (git serialization) — codex, protects all concurrent slice work.

## Next
Dispatch implementation slices. The 2026-07-09 full-system analysis is incorporated as the measured baseline: services green, `aq-qa 0` at 164/0, local model 11/12 first warm baseline, wedged-slot/readiness guards live, and R1 certification observed but not fully enforced. First active slice is R1-E scorer enforcement and capture dedup in `scripts/ai/aq-local-training-loop`, with R5.1 trace auto-seeding and R7.1 git/worktree serialization safe to run in parallel. Operator-gated: R3.1 SMALL_RESIDENT rebuild; antigravity IDE inbox-watch.
