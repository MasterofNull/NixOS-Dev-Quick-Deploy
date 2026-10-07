# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-011

## Objective
- Make the #390 JSONC normalization actually run during Home Manager activation (activation PATH has no python3; normalization was silently skipped).

## Workflow/Session IDs
- Workflow ID: wf-vscodium-jsonc-python-path-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Claude Opus 5.5 direct (Rule 17 exception: 3 one-line substitutions found during live verification of an owner switch).

## Commands Executed
```bash
nix build --no-link --print-out-paths .#homeConfigurations.hyperd.activationPackage
env -i PATH=/nonexistent <store-python3> scripts/ai/lib/jsonc_to_json.py <copy> out.json && jq empty out.json
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Owner switch after #390 still printed `jq: parse error` x3; built activate PATH confirmed to lack python3.
- New build: activate references /nix/store/…-python3-3.13.15/bin/python3; normalization works with empty PATH; jq accepts output.
- tier0 53/54 (QA phase 0 env-only rows in worktree + live catalog during owner rebuild).

## Rollback Plan
- Revert; home-manager switch.

## Residual Risk
- Final proof is the next owner `home-manager switch` showing no jq parse errors.

## Hint Feedback
- No aq-hints consulted.
