# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-010

## Objective
- Home Manager activation patches (enforceVSCodiumTheme, migrateClaudeVscodeSettings, enforceCodexVscodeSettings) silently skipped because ~/.config/VSCodium/User/settings.json is JSONC (trailing commas, comments) and plain jq rejects it ("parse error line 5 col 3"). Normalize JSONC→JSON before jq.

## Workflow/Session IDs
- Workflow ID: wf-vscodium-jsonc-activation-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementer: Claude Haiku 4.5 (worktree, read-only on real settings). Reviewer: Claude Opus 5.5 (verified on a copy of the real file; ${repoPath}/scripts pattern already used 6x in base.nix).

## Commands Executed
```bash
python3 scripts/testing/test-jsonc-to-json.py
nix build --no-link .#homeConfigurations.hyperd.activationPackage
python3 scripts/ai/lib/jsonc_to_json.py <copy-of-settings.json> out.json && jq empty out.json
```

## Validation Evidence
- 15/15 tests (comments + trailing commas outside strings; "https://" and ",}" inside strings preserved; invalid → nonzero).
- HM activation package builds.
- Real settings copy: normalized output passes jq, 114 keys preserved.

## Rollback Plan
- Revert; home-manager switch.

## Residual Risk
- Normalization rewrites settings.json without comments (jq patch path already rewrote it); VSCodium may reintroduce JSONC, which is now tolerated.

## Hint Feedback
- No aq-hints consulted.
