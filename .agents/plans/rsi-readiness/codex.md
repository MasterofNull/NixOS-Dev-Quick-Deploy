# Codex Lane - RSI Readiness

Outcome: RATIFY-WITH-AMENDMENTS. The PRD correctly gates all future autonomy on R1 and keeps this cycle in shadow mode, but R1 needs stricter scorer-integrity acceptance before any downstream activation can be trusted.

## 1. Scores + Ratification

R1: 9/10 - Correctly identified as the global gate; acceptance should add adversarial scorer-gaming and concurrent-run invariance checks beyond same-model tolerance.
R2: 8/10 - Draft-only plus verified apply directly addresses unbacked local write claims in `scripts/ai/aq-agent-loop`, but dispatch enforcement must be contract-level, not convention-level.
R3: 8/10 - `scripts/ai/lib/model_budget.py` and `scripts/ai/lib/cascade.py` give a real implementation path for SMALL_RESIDENT and verifier-backed cascade, with Nix wiring still the main risk.
R4: 8/10 - Shadow-only efficacy measurement is the right boundary; it depends completely on R1 score integrity and sandbox reproducibility.
R5: 7/10 - `scripts/ai/lib/trace.py` has live trace primitives and optional OTLP hooks, but entrypoint coverage and dashboard diagnosability are not yet proven.
R6: 6/10 - A flagship self-improvement app can focus the system, but it risks becoming demo theater unless every claim is backed by R1/R4 measurements.
R7: 8/10 - Git/index serialization and event-bus completion are necessary coordination safety rails; acceptance should include contention tests, not only happy-path locks.

Verdict: RATIFY-WITH-AMENDMENTS - proceed with R1 first, keep no-autonomy as a hard boundary, and require each later slice to attest against the trustworthy eval harness before activation.

## 2. Top Amendments

1. Strengthen R1 acceptance: require golden, shadow, and canary tasks to prove scorer resistance to gaming, infra-noise abstention, and deterministic scoring under parallel contention; why: `scripts/ai/aq-local-training-loop` already showed a false 0/12 can masquerade as regression; workstream: R1.
2. Make no-autonomy executable: define SHADOW as a runtime mode that cannot write, commit, deploy, or enqueue verified-apply actions without an external gate; why: policy text alone will not stop accidental autonomy via orchestration glue; workstreams: R2/R4/R7.
3. Add activation-gate artifacts per workstream: each R-slice must produce a machine-readable attestation containing files touched, live path wired, test evidence, and rollback/deactivation knob; why: prevents green-check trust theater; workstreams: R1-R7.

## 3. Underweighted Risks

1. Scorer overfitting: a golden set without private canaries can reward prompt-shaped compliance instead of capability, especially for structured output and write-discipline.
2. Shadow-loop leakage: a proposal path that shares helpers with apply/commit code can accidentally perform side effects unless SHADOW is enforced at the tool boundary.
3. Observability theater: trace IDs and spans can exist while missing the decisive evidence needed to explain a failed eval, so R5 acceptance must require trace-only diagnosis of real failed runs.

## 4. Slice Claims + Wiring Plan

R1 harness: claim - touch `scripts/testing/`, `scripts/ai/aq-local-training-loop`; wire golden/canary evals; validate repeatability, broken-model delta, contention abstain.
R3 Nix+wiring: claim - touch `nix/modules/core/options.nix`, model service wiring, dispatch config; validate SMALL_RESIDENT route, tok/s bench, cascade verifier use.
R5 OTel/tracing: claim - touch CLI/loop entrypoints and `scripts/ai/lib/trace.py`; wire `AQ_TRACE_ID` propagation and OTLP hook; validate `/api/trace/{id}` diagnosis.
R7 git/worktree serialization: claim - touch agent orchestration/git helpers; wire lock around index/worktree mutation; validate concurrent write/commit contention tests.
R2 contract support: pass - Claude owns draft-only contract; Codex can provide typed guard hooks if dispatch schemas require structural enforcement.
R4 efficacy methodology: pass - Antigravity/Claude own measurement design; Codex can add sandbox harness plumbing after R1 lands.
R6 flagship app: pass - Claude owns integration/acceptance; Codex should only wire typed backend surfaces requested by the accepted slice.

## 5. Verdict + First Commit Target

First slice to land: R1 trustworthy eval harness, because every other workstream depends on a non-corruptible reward signal.

Commit target: `test(rsi-eval): add trustworthy eval harness integrity gates`
