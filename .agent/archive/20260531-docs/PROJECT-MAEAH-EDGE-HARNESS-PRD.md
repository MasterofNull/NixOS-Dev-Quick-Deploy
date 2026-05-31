# PROJECT-MAEAH-EDGE-HARNESS-PRD

## Problem
The MAEAH edge harness needs Day-1 A2A peer identity controls, the canonical REST-shaped A2A task submission path, a CPU-only fallback queue-buffer sign-off, and a repeatable acceptance runner for the ten AM-C5 gates.

## Goal
Implement a bounded slice that preserves existing JSON-RPC A2A behavior while adding signed Agent Cards, `POST /a2a/tasks/send`, Q7 findings, and an executable acceptance harness.

## Scope
- Modify `ai-stack/mcp-servers/hybrid-coordinator/extensions/openai_a2a_handlers.py`.
- Create `scripts/testing/maeah-acceptance-tests.sh`.
- Write `.agents/plans/multi-agent-edge-harness/QWEN-ITEMS-CODEX-FINDINGS.md`.

## Out Of Scope
- Runtime peer-card verification and quarantine storage.
- Reworking model lifecycle APIs beyond the acceptance harness.
- Deploying or restarting system services.

## Acceptance Criteria
- Agent Card JSON includes an Ed25519 proof when a signing backend is available.
- Signing key path honors `A2A_SIGNING_KEY_PATH`, then `/run/secrets/a2a_signing_key`, then `/var/lib/ai-stack/hybrid/a2a_signing.key`.
- `POST /a2a/tasks/send` accepts the canonical request body and returns `{id,status,artifacts}`.
- Acceptance script prints PASS/FAIL per gate and exits 1 on any failed gate.
- Tier0 pre-commit validation is run after implementation.

## Security
- Private signing key is created with `0600` permissions.
- Agent Card signing canonicalizes JSON without the `proof` field.
- The new REST endpoint reuses the existing session/UAG task creation path and does not add shell execution or external calls.

## Rollback
Revert the modified A2A handler and remove the new acceptance/findings/PRD artifacts. No persistent service migration is introduced by this slice.
