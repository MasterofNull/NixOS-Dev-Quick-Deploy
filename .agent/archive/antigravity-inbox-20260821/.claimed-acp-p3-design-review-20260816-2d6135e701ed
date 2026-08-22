# A2A advisory task for Antigravity — ACP-P3 runbook automation engine design review

Dropped: 2026-08-16T12:31:00Z
output_file: .agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P3-DESIGN-ADVISORY-20260816.md

Respond by writing only `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P3-DESIGN-ADVISORY-20260816.md`.

SCOPE-STOP: independent ADVISORY security review only. Authorize nothing, change no code, touch no
service/key/secret/runtime, do not stage or commit. NON-GATING — orchestrator verifies every claim. This
review is a BUILD GATE (owner directive: Antigravity+local+orchestrator review completing authorizes the
build, Codex confirmatory-on-return). Be thorough; find real defects.

SUBJECT: `.agents/plans/approval-control-plane/ACP-P3-DESIGN-20260816.md` (runbook automation engine that
runs the multi-step crypto sequence one approval authorizes). Predecessors: P0 record + RUNBOOK_REGISTRY
`scripts/ai/lib/approval_request.py`; P1 signer `ACP-P1-DESIGN-20260816.md`.

Assess, findings-first: (1) is the idempotent/resumable model sufficient that a crash mid-runbook is
always recoverable WITHOUT double-apply; (2) can any step widen scope beyond the approved hashed
params/declared_effects, or inject params at runtime; (3) is the signer-gated-step model correct so no
atom ever exposes private key material to the engine, and does one approval authorize exactly one runbook
run (not replayable to a second run); (4) is fail-closed + operator intervention complete (no silent
partial success); (5) does declaration-coupling fully satisfy the NixOS-declarative rule for activate-*
runbooks; (6) any audit-integrity gap (could a step's outcome be forged so the engine believes an effect
succeeded when it didn't).
