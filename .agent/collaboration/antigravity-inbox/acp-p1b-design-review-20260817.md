# A2A advisory task for Antigravity — ACP-P1b lost-authenticator recovery design review

Dropped: 2026-08-17T00:00:00Z
output_file: .agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1b-DESIGN-ADVISORY-20260817.md

Respond by writing only `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1b-DESIGN-ADVISORY-20260817.md`.

SCOPE-STOP: independent ADVISORY security review only. Authorize nothing, change no code, touch no
service/key/secret/runtime, do not stage or commit. NON-GATING — orchestrator verifies every claim. This
is a BUILD GATE (owner directive: Antigravity review completing authorizes the build). Find real defects.

SUBJECT: `.agents/plans/approval-control-plane/ACP-P1b-DESIGN-20260816.md` (lost-authenticator recovery).
Predecessor: ACP-P1 signer `scripts/ai/lib/approval_signer.py` (multi-credential allowlist, single-use +
executed-id ledgers, verify_execution_authorization).

Assess, findings-first: (1) is multi-authenticator (primary+backup) enrollment + a CONSOLE-GATED
declarative recovery bootstrap genuinely free of an agent-forgeable path; (2) is "physical host root =
recovery factor" correctly un-spoofable over the signer UDS (an agent shares the primary UID); (3) does
the no-empty-allowlist rule fully prevent BOTH self-lockout AND a fail-open empty state; (4) any recovery
step that stores an agent-readable secret, or lets recovery yield a standing authorization / a signature
rather than only re-enrolling an authenticator; (5) any race between removing the last key and enrolling
a replacement.
