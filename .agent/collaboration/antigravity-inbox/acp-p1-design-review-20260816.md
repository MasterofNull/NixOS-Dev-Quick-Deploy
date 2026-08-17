# A2A advisory task for Antigravity — ACP-P1 WebAuthn signing service design review

Dropped: 2026-08-16T11:52:00Z
output_file: .agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1-DESIGN-ADVISORY-20260816.md

Respond by writing only `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1-DESIGN-ADVISORY-20260816.md`.

SCOPE-STOP: independent ADVISORY security/architecture review only. Authorize nothing, change no code,
touch no service/key/secret/runtime, do not stage or commit. NON-GATING — orchestrator verifies every
claim before use (this untrusted lane's output is advisory and orchestrator-owned).

SUBJECT: `.agents/plans/approval-control-plane/ACP-P1-DESIGN-20260816.md` (WebAuthn-gated signing
service). Predecessor: ACP-P0 record lib `scripts/ai/lib/approval_request.py` (committed dee72d38).

Assess: (1) does fetch-by-request_id + recompute fully close what-you-see-is-what-you-sign, or can a
caller still influence the signed bytes; (2) is the challenge-from-canonical_hash + request_id-keyed
single-use ledger sound against replay AND the content-hash-collision note (two distinct requests with
identical content share a content hash); (3) is the confinement model enough that a compromised agent
user cannot reach the owner key or forge an assertion; (4) any downgrade/fallback path an agent could
force to bypass WebAuthn; (5) is authorization-by-signature (not status) correctly specified; (6) is the
python-fido2 software-authenticator test strategy a faithful hermetic proof. Terse, findings-first.
