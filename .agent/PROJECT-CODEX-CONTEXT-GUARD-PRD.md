# Codex native context guard

Owner authorization: 2026-09-27, implement protection against measured context replay.
Scope: enable Codex's supported native automatic compaction at 50,000 tokens;
persist it in Nix and active user/project configuration. Extend the existing
read-only diagnostic with explicit rollout verification: a compaction event alone
is insufficient; a subsequent request must be smaller and within the threshold.
Keep model choice, permissions, transcripts, and provider state unchanged.

Acceptance: config parses; native CLI accepts it; regression fixtures distinguish
missing measurements, oversized input, pending compaction, and verified reduction.
Report startup configuration separately from live reduction. Existing running
threads need supported compaction or a fresh client/session loading the new config.
No forced shutdown, transcript deletion, new daemon, or inference test just to
consume quota. Rollback: restore the previous two config values and Nix declaration.

## Resumed memory CLI slice — 2026-09-27

Repair the proven false-success behavior in aq-memory: `_save` swallows filesystem errors, allowing add/store/expire to claim persistence. Existing store is not writable by the session user. Propagate write errors to the CLI process, preserving storage location and permissions. Acceptance: failed writes exit nonzero without success output; successful writes reload correctly. Add focused regression tests. Ownership remediation, coordinator working-memory path, async receipts, and other-provider adapters remain separate pending work. No deployment or new dependencies.
# RSI failure capture implementation slice

Reuse the existing lifecycle recorder and PRSI queue. Persist bounded, redacted incidents under `.agent/collaboration`, deduplicate recurrence under a lock, and capture installed hook denials without changing their decision or replaying commands. PRSI consumes open incidents under existing budgets and authority. Closure requires root-cause, regression, and validation evidence. Acceptance: concurrent repeats retain counts; hook output/status are preserved; recorder faults are visible; no recursive dispatch. Installed hook activation and live PRSI readiness are separate from source/test completion.
