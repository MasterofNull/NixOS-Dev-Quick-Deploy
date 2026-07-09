# Lane: claude (orchestrator) — rsi-readiness ratification

## 1. Scores + verdict
- R1 (eval harness) **10** — the load-bearing wall; a corruptible reward signal makes every downstream automation actively dangerous. Highest priority, correctly gates all.
- R2 (local write-reliability) **9** — the specific measured blocker to autonomy (unbacked-write caught twice); draft-only contract is shippable now, fine-tune is the real fix.
- R3 (SMALL_RESIDENT + verifier) **8** — high leverage (parallelism + cascade verifier) but operator-gated on a rebuild; don't let it block R1/R2.
- R4 (shadow loop efficacy) **9** — this is the *actual research question* ("do proposals improve anything?"); answering it with data is the whole point.
- R5 (trace seeding) **7** — additive, compounds observability; low risk, do it early.
- R6 (flagship) **8** — the integration proof; only meaningful once R1-R5 exist.
- R7 (coordination safety) **9** — under-weighted elsewhere: self-improvement = more concurrent agents; the git-clobber we hit today becomes catastrophic at scale.

**Verdict: RATIFY-WITH-AMENDMENTS** — direction is right and evidence-grounded; three amendments sharpen where "trust" could become theater.

## 2. Top 3 amendments
1. **R1 acceptance must include a HELD-OUT adversarial set, not just tolerance bounds** (R1.3). A scorer that's stable AND wrong is the worst case. Add: a curated set of known-good and known-bad outputs the scorer has never seen; it must rank them correctly. Trust = discriminates good from bad, not just repeatable.
2. **R2 must gate on the golden set BEFORE any fine-tune ships** (R2.2). Order matters: build the tool-use golden set (R1.1) first, measure the baseline, then fine-tune, then prove the delta on held-out cases. A fine-tune "felt better" is exactly the anti-pattern.
3. **R7 sequenced FIRST, not "anytime"** (sequencing). It protects every other concurrent slice; landing it late means the slice work itself races. Promote R7.1 (git serialization) to the immediate-dispatch list.

**AMENDMENT 4 (new workstream R8 — added post-dispatch, operator-raised): durable delegation queue with rate-limit/session-window park-and-resume.** Today's resilience is partial — retry_with_backoff handles short 429s, circuit breakers fail-fast but DROP the failed delegation, 429→local fallback silently degrades. Missing: parking a delegation that hits a long session/quota window and auto-resuming it on the INTENDED lane when the window clears. This is what crashes multi-agent collabs under sustained limits (self-improvement = long, concurrent, remote-heavy). R8 (in the PRD): classify transient-vs-window-vs-hard; durable park queue on the event bus surviving session restarts; resume scheduler with event_id idempotency (no double-execution); collab-round folds the resumed lane (extends never-skip-local to never-drop-rate-limited). Sequence early with R7 — R4's shadow loop WILL hit limits. Lanes: score R8 in aggregation; codex owns the queue/scheduler, claude the round integration.

## 3. Risks the PRD underweights
- **Eval overfit to the golden sets**: if R2's fine-tune trains toward R1's exact cases, scores rise while true capability doesn't. Mitigation: strict train/eval split + a rotating held-out set the training pipeline never sees (fold into R1.3).
- **Shadow≠live gap**: R4 measures proposals in a sandbox; a proposal that improves sandbox evals may regress the live system (side effects, integration). R4's efficacy number is necessary but not sufficient for autonomy — state that explicitly so it isn't over-read.
- **Human-gate fatigue**: R4+R6 route everything through the operator; if the volume outpaces review, the gate becomes a rubber stamp (worse than no gate). R7's coordination + a triaged approvals queue (WS6 view) must keep gate load reviewable.

## 4. Slice claims + wiring plan
- R1.3 (integrity gates + held-out adversarial set): **claim** — files: new `ai-stack/local-agents/eval_integrity.py` + a `data/golden/*` tree; wiring: aq-local-training-loop consults it; validation: adversarial set ranks correctly + inter-run variance test; I sign off the signal is trustworthy (orchestrator acceptance).
- R2.1 (draft-only contract): **claim** — files: `scripts/ai/lib/dispatch.py` + generalize the unbacked-write guard into an enforced execution contract; wiring: local execution routes through cascade/verified-apply; validation: contract test + live.
- R5.1 (AQ_TRACE_ID auto-seeding): **claim** — files: `aq` router + aq-loop entrypoints; wiring: seed trace id in middleware; validation: every dispatch carries a trace id (live /api/trace).
- R6.1 (flagship): **claim** — orchestration/integration/acceptance.
- R7.4 (coordination contract in WORKFLOW-CANON): **claim** — plus review of codex's R7.1 lock/worktree impl.
- R3.1 Nix+model deploy: **pass** — operator-gated rebuild + codex wiring.
- R1.1/R1.2 harness core, R3 wiring, R5.2 OTel, R7.1 git-lock: **pass** to codex.

## 5. Verdict + first commit target
RATIFY-WITH-AMENDMENTS. **First slice to land: R5.1 (AQ_TRACE_ID auto-seeding)** — additive, unblocks trace-diagnosis of every subsequent slice, zero ratification dependency. Commit: `feat(trace): auto-seed AQ_TRACE_ID at every entrypoint (RSI-Readiness R5.1)`.
