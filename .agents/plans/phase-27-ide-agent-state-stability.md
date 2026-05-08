# Phase 27 — IDE Agent State Stability

## Objective
- Eliminate IDE-gating freezes caused by oversized editor-local agent state.
- Turn the current reactive repair work into bounded retention, visibility, and workflow discipline.

## Scope Lock
- In scope:
  - Continue session retention and compaction
  - Gemini/Qwen extension-state retention
  - Codex local state-db recovery path
  - VSCodium extension lifecycle drift and stale markers
  - Harness/editor workflow rules that drive state growth
  - Health/reporting for editor corpus size
- Out of scope:
  - Provider/model quality tuning
  - Replacing VSCodium
  - Removing core required editor integrations
- Constraints:
  - Preserve declarative-first config
  - Preserve required Continue config freeze items
  - Preserve OAuth/CLI bridge lanes for Claude and Codex
  - Archive before destructive cleanup where practical

## Context References
- Files to read first:
  - [nix/home/base.nix](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/home/base.nix)
  - [config/service-endpoints.sh](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/service-endpoints.sh)
  - [scripts/testing/test-vscodium-extension-runtime-guards.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/test-vscodium-extension-runtime-guards.py)
  - [scripts/ai/mcp-bridge-hybrid.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/mcp-bridge-hybrid.py)
- Docs to read first:
  - [docs/development/IDE-AGENT-STATE-STABILITY-PDR-2026-05-08.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/development/IDE-AGENT-STATE-STABILITY-PDR-2026-05-08.md)
  - [docs/operations/ai-harness-routing-and-editor-surfaces.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/operations/ai-harness-routing-and-editor-surfaces.md)
  - [docs/operations/CONTEXT-LIMIT-HANDLING.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/operations/CONTEXT-LIMIT-HANDLING.md)

## Steps
1. Productize editor-state budgets.
   - Add explicit thresholds for Continue sessions, Gemini/Qwen state, and stale marker counts.
   - Make thresholds discoverable in docs and test coverage.
2. Add editor corpus health reporting.
   - Extend `aq-report` and/or `aq-qa` to emit:
     - active Continue session size
     - archived Continue session count
     - Gemini/Qwen payload sizes
     - Codex state-db health
     - stale marker presence
3. Tighten workflow discipline.
   - Add a documented rule and harness helpers for checkpointing to memory at slice boundaries.
   - Reduce raw transcript replay in Continue/editor flows.
4. Reduce state growth at source.
   - Identify where repo maps, long logs, and repeated bootstrap content enter editor transcripts.
   - Replace them with summarized or referenced forms where possible.
5. Harden failure handling.
   - Add bounded retry guidance and automation for failed editor sessions.
   - Prefer fresh-session resume from harness memory after repeated failure.
6. Add operator recovery guidance.
   - Write an editor-state recovery runbook covering repair, archive paths, validation, and rollback.

## Validation
- Syntax:
  - `python3 -m py_compile scripts/testing/test-vscodium-extension-runtime-guards.py`
  - `bash -n config/service-endpoints.sh`
- Tests:
  - `python3 scripts/testing/test-vscodium-extension-runtime-guards.py`
  - focused tests for any new `aq-report` / `aq-qa` coverage
- Smoke:
  - real VSCodium relaunch after `home-manager switch`
  - `vscodium-repair`
  - verify no extension-host freeze on workspace open

## Evidence
- Files changed:
  - `nix/home/base.nix`
  - `config/service-endpoints.sh`
  - `scripts/testing/test-vscodium-extension-runtime-guards.py`
  - follow-up reporting/runbook files
- Commands run:
  - `aq-prime`
  - `aq-hints ...`
  - `aq-context-bootstrap ...`
  - `sqlite3 ~/.config/VSCodium/User/globalStorage/state.vscdb ...`
  - `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Output snippets:
  - Gemini state reduced from about `2388973` bytes to about `567051`
  - Continue active session corpus reduced from about `252 MB` to about `6.6 MB`
  - stale `.obsolete` entries cleared

## Rollback
- Restore archived Continue sessions from `~/.continue/sessions-backup-*`
- Restore Codex DB from `~/.codex/state_5.sqlite.pre-vscodium-repair-*`
- Revert repo changes with normal git rollback if a new retention rule is too aggressive
