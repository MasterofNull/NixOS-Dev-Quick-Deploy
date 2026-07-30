# A2A task for Antigravity — Codex C1A acceptance review

Dropped: 2026-07-29T05:30:00Z

Respond by writing only:
`.agents/plans/agent-model-config-parity/antigravity-c1a-acceptance.md`

## Role and stops

Independent flagship reviewer. Read only. Do not edit any candidate/shared file,
route agents, stage, commit, deploy, or call providers.

## Exact subject

Acceptance packet:
`.agents/plans/agent-model-config-parity/C1A-CANDIDATE-ACCEPTANCE.md`
SHA-256:
`d7a5570e16053d8c5d54bbff7c60e4e54b84b672eea63a948fe9004c7fa80e36`

Verify all hashes in the packet, the exact two-file candidate ceiling, and the
three frozen role layers. Review against current Codex custom-agent semantics:
every named role needs a description and relative config file; role layers must
retain the declared model, effort, sandbox, instructions, and disabled nested
delegation. Confirm adversarial tests reject missing roles, path escape,
description drift, writable reviewer/explorer, nested delegation, excess
concurrency, unsafe default model, deprecated hooks, and root trust.

Return evidence and:
`VERDICT: PASS | FAIL | REQUEST_REVISION`.

After writing the response, complete this inbox item with:
`scripts/ai/aq-antigravity-inbox complete agent-model-config-c1a-acceptance.md`
