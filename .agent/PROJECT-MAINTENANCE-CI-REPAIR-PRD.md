# Maintenance CI repair

Owner authorization: proceed with remaining maintenance slices and coordinate Gemini (2026-11-17).

## Frozen scope

Repair the demonstrated stdio MCP child-exit race in sweep-lanes without changing protocol classification, leaking descendants, or reporting cleanup signals as natural exits. Preserve all unrelated main-checkout changes. Gemini owns its resumed entropy-path, reviewer-probe, persona-facts and safety-path slices; this branch owns only sweep-lanes and its regression/evidence.

## Design scrutiny

Architecture: reuse subprocess wait/poll and existing cleanup; no dependency or new service. Failure modes: stdout EOF can precede process termination, or a child may close stdout and remain alive; wait must be bounded and cleanup unconditional. UX: retain existing manifest fields and fail-closed checks. Security: retain stderr scrubbing and descendant cleanup; never infer an exit code from a signal sent by this probe. Independent Gemini diagnostic requested as gemini-20261117-162119-tqzfn9; pending, not claimed as approval. Scope frozen for independent review before landing.

## Slices and acceptance

1. Fix producer and deterministic regression. Prove regression fails against origin/main and passes with repair; cover closed stdout with a live child, preserve timeouts and descendant cleanup.
2. Independent review, full sweep-lanes tests, tier0 pre-commit and atomic commit; land through aq-land, inspect main CI.
3. Reconcile remaining checkout metadata with its owners, verify maintenance readiness and provide owner activation commands. No sudo, restart or rebuild performed by this slice.

Activation: repository CI path is live when merged and its checks run. System activation remains owner-controlled. No rollback or deletion authorized by this plan.

Coordination update: diagnostic dispatch gemini-20261117-162119-tqzfn9 exited during the interrupted session without a report. Relaunch was rejected permanently by the shell hook (delegate-to-gemini allowlist). Independent Codex review substitutes; no Gemini approval is claimed. Gemini's existing four branches remain separately owned. Editorial tracker: `.agents/plans/maintenance-ci-repair/tracker.json`.
