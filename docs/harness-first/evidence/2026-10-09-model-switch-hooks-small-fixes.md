# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-050

## Objective
- **Live incident 2026-10-09 08:52.** `sudo aq-model-switch` ran its post-switch hooks (training loop, training ingest) as ROOT. That left 43 root-owned 0600 repo files (the delegation registry, PENDING/HANDOFF, session logs) and a root-rewritten tracked config/harness-prompt-extensions.yaml. It broke the dashboard local-agent monitor (phase-0 0.12.8), and the hooks ran local inference during the owner's DB backfill.
- **Fixes.**
  - The hooks now run as SUDO_USER (or the non-root repo owner) via Popen user/group/extra_groups; they refuse to run as root, and AQ_POST_SWITCH_HOOKS=0 disables them. They announce that they use local inference.
  - NixOS now skips the /etc GPU drop-in (it is read-only and declared in Nix).
  - tool_discovery uses a stable sha1 point id.
  - The route-handler pytest patches now target core.route_handler.
  - The decayed hand-stubbed scripts/testing/test-route-handler-collection-policy.py is archived (Rule 12, archive/deprecated/20261009-tests/), and its roadmap pattern check is repointed to the live pytest suite.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- A Haiku implementer did 3 fixes. The orchestrator replaced its source-grep model-switch test with a behavioural one, added the root-hook fix, and archived the legacy test, which Haiku had misreported as passing.

## Commands Executed
```bash
python3 scripts/testing/test-aq-model-switch-nixos.py   # PASS; FAILS on the original script
python3 scripts/testing/test-tool-discovery-stable-hash.py   # PASS (PYTHONHASHSEED 1 vs 2 subprocess)
pytest tests/unit/test_route_handler_collection_policy.py   # 3 passed (failed on main before)
```

## Validation Evidence
- The behavioural test proves: euid 0 with SUDO_USER runs hooks as uid 1000; no SUDO_USER with a root-owned repo skips them; the env kill switch works; a non-root run is unchanged; NixOS dry-run prints the skip with no drop-in.

## Rollback Plan
- Revert the commit.

## Residual Risk
- Already-root-owned files need the one-time owner chown (given in the session).

## Hint Feedback
- None.
