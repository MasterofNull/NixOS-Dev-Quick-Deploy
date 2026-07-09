# Round rsi-readiness — Orchestrator Aggregate (OPEN — folds local on land)

**Aggregated**: 2026-07-09 by claude-fable-5 · **Lanes landed**: 2/4 substantive (claude, codex); local running (fold on land); antigravity inbox-gated.
**Status**: PROVISIONAL RATIFY — round stays OPEN; local's contribution amended in when it lands (never-skip-local); antigravity folded if it responds.

## Verdict: RATIFY-WITH-AMENDMENTS (2/2 substantive lanes concur)

| Lane | Verdict | Substance |
|------|---------|-----------|
| claude (orchestrator) | RATIFY-WITH-AMENDMENTS | scores R1-R7, 4 amendments (inc. R8), slice claims |
| codex | RATIFY-WITH-AMENDMENTS | scores R1-R7, 3 amendments, slice claims, R1-first |
| local (Qwen) | pending (running) | fold on land; failures here are R2 training data |
| antigravity | pending (IDE inbox) | fold if it responds |

Both substantive lanes independently ratified-with-amendments, R1-first, no-autonomy affirmed. (Typed aggregator shows ABSTAIN×3 — known parser gap: it doesn't recognize `RATIFY-WITH-AMENDMENTS`; logged in issues-backlog. This human aggregate governs.)

## Score consensus (mean of claude + codex)
R1 **9.5** · R2 **8.5** · R3 **8** · R4 **8.5** · R5 **7** · R6 **7** · R7 **8.5** · R8 **(claude-proposed, codex pre-dates it — score on fold)**

Reading: R1 (eval-harness trust) is the near-unanimous top priority and global gate; R6 (flagship) lowest — both flag it risks "demo theater" unless every claim is R1/R4-backed.

## Adopted amendments (merged; fold into PRD)
1. **Strengthen R1 acceptance to prove scorer TRUST, not just stability** (both lanes): golden + shadow + canary tasks; must resist scorer-gaming, abstain on infra-noise, and score deterministically under parallel contention; a held-out adversarial set the scorer has never seen must rank known-good vs known-bad correctly. (R1.3)
2. **Make no-autonomy EXECUTABLE, not prose** (codex, adopted): define SHADOW as a *runtime mode* that physically cannot write/commit/deploy/enqueue verified-apply actions without an external gate — policy text won't stop accidental autonomy via orchestration glue. (R2/R4/R7)
3. **Per-workstream machine-readable activation attestation** (codex, adopted): every R-slice emits an attestation with files touched, live path wired, test evidence, and a rollback/deactivation knob — prevents green-check trust theater. (R1-R8)
4. **R2 gates on the golden set BEFORE any fine-tune ships** (claude): build the tool-use golden set, baseline, fine-tune, prove the delta on held-out cases; a strict train/eval split prevents overfit-to-golden. (R2.2/R1.3)
5. **R7 + R8 sequenced FIRST** (claude): coordination safety + rate-limit durability are the substrate protecting/sustaining all concurrent long-running slice work; R4's shadow loop will hit both concurrency and limits.
6. **R8 durable delegation queue** (claude, operator-raised, post-dispatch): park delegations on long rate-limit/session windows, auto-resume on the intended lane with event_id idempotency, round folds the resumed lane. Score on local fold.

## Slice ownership (ratified; R1/R5 overlap resolved)
- **codex**: R1 harness core (golden/canary evals in aq-local-training-loop), R3 Nix+wiring (options.nix, model service, dispatch), R5 OTel plumbing (AQ_TRACE_ID propagation + OTLP hook), R7.1 git/worktree serialization + contention tests, R8 queue/scheduler.
- **claude**: R1.3 integrity gates + adversarial held-out set + trustworthy-signal SIGN-OFF, R2.1 draft-only execution contract (dispatch-level, not convention), R5.1 entrypoint seeding, R6 flagship, R7.4 coordination contract (WORKFLOW-CANON), R8 round-integration.
- **antigravity** (if live): R1.1 golden-set design, R4 efficacy-measurement methodology, eval-trust research brief.
- **local (Qwen)**: bounded audits, R2 training-data curation; its own failures = R2 data.

## Sequencing (ratified)
R1 FIRST (global gate). R7 + R8 early (substrate). R2 + R3 parallel after R1 baseline. R5 anytime. R4 after R1 (+R7/R8). R6 last. R4 efficacy data gates any future autonomy PRD.

## Immediately dispatchable (no further ratification)
- **R5.1** (AQ_TRACE_ID auto-seeding) — claude, first commit target, zero dependency.
- **R1.1** (golden task sets) — antigravity design / codex build.
- **R7.1** (git serialization) — codex, protects all concurrent slice work.

## Next
Fold local on land (amend scores + slice audit). Amend the PRD with adopted amendments 1-6. Dispatch R5.1 as the first implementation slice. Operator-gated: R3.1 SMALL_RESIDENT rebuild; antigravity IDE inbox-watch.
