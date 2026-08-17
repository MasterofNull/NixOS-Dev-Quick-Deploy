# A2A advisory task for Antigravity — ACP-P2 approval surface design review

Dropped: 2026-08-16T12:30:00Z
output_file: .agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P2-DESIGN-ADVISORY-20260816.md

Respond by writing only `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P2-DESIGN-ADVISORY-20260816.md`.

SCOPE-STOP: independent ADVISORY security/usability review only. Authorize nothing, change no code, touch
no service/key/secret/runtime, do not stage or commit. NON-GATING — orchestrator verifies every claim.
This review is a BUILD GATE: owner directive is that Antigravity(+local+orchestrator) review completing
authorizes the build (Codex confirmatory-on-return). Be thorough; find real defects.

SUBJECT: `.agents/plans/approval-control-plane/ACP-P2-DESIGN-20260816.md` (the beginner-friendly approval
surface). Predecessors: P0 record `scripts/ai/lib/approval_request.py` (canonical_hash now binds
request_id), P1 signer design `ACP-P1-DESIGN-20260816.md`.

Assess, findings-first: (1) is "render Layer-1 only + Details for Layer-3" sufficient to keep the surface
beginner-safe AND to preserve what-you-see-is-what-you-sign given the whole hashed field set (incl.
technical_trail) is what's signed; (2) does the approve flow keep ALL crypto out of the human's hands
while the browser WebAuthn ceremony + P1 signer do the work; (3) any state the surface could render
dishonestly (silent spinner, false "done", stale status); (4) any place jargon or a CLI/crypto affordance
could leak into the default path; (5) any a11y or beginner-comprehension gap; (6) any way a compromised
agent driving the browser could mislead the human about what they're approving.
