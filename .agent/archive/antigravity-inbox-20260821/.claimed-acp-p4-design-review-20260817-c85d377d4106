# A2A advisory task for Antigravity — ACP-P4 headless/rescue authorization design review

Dropped: 2026-08-17T00:01:00Z
output_file: .agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P4-DESIGN-ADVISORY-20260817.md

Respond by writing only `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P4-DESIGN-ADVISORY-20260817.md`.

SCOPE-STOP: independent ADVISORY security review only. Authorize nothing, change no code, touch no
service/key/secret/runtime, do not stage or commit. NON-GATING — orchestrator verifies every claim. BUILD
GATE (owner directive). Find real defects.

SUBJECT: `.agents/plans/approval-control-plane/ACP-P4-DESIGN-20260816.md` (headless aq-approve CLI — a
FIDO2 hardware ceremony from a terminal/rescue console, no browser). Predecessor: ACP-P1 signer
`scripts/ai/lib/approval_signer.py` (same challenge/single-use/executed-id semantics).

Assess, findings-first: (1) does the CLI truly reuse the IDENTICAL signer path so headless has the same
guarantees (WYSIWYS, single-use request_id-keyed, fail-closed) as the browser flow; (2) is there ANY
passphrase/key-file/offline path that would be an agent-forceable DOWNGRADE (the CLI must only transport a
hardware assertion, never substitute a secret); (3) is the rescue-console bring-up itself free of a
crypto-by-hand step; (4) can an agent running `aq-approve` ever obtain a signature (it lacks hardware
user-verification); (5) does the CLI keep the plain-language/privacy boundary (Layer-1 default, no crypto
dumped to the terminal); (6) any hidraw/udev permission gap that would either block the owner or over-expose the device.
