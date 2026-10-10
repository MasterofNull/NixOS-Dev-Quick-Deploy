# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-010

## Objective
- Complete Codex's sandbox slice (commit 728f8137, cherry-picked onto main as part of this PR, owner-directed): Nix declares the local shell tool PATH and a read-only repository mount for the local-agent jail; Codex's TOML is reconciled with a permissions-only projection; local shell tools and the MCP client projections are repaired. PRD: .agent/PROJECT-SANDBOX-TOOL-ACCESS-PRD.md. The workaround is registered in .agent/WORKAROUND-REGISTER.md.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f (completion); original implementer: Codex (owner's parallel session)

## Delegation Decision
- Codex implemented this. The Claude orchestrator rebased it off the main checkout (preserved branch codex/wip-sandbox-20261009), validated it and committed it via PR on owner instruction.

## Commands Executed
```bash
python3 scripts/testing/test-codex-config-reconcile.py      # PASS
python3 scripts/testing/test-local-shell-sandbox.py         # PASS (injection sequences still rejected)
python3 scripts/testing/test-agent-mcp-client-projection.py # PASS
nix-instantiate --parse nix/home/base.nix nix/modules/services/mcp-servers.nix   # ok
```

## Validation Evidence
- Codex's runtime evidence (ACTIVATION-AUDIT): nsjail 3.6 executes the corrected argv; git, temporary writes and the read-only repository boundary pass.

## Rollback Plan
- Revert the commit, then run hms/nrs.

## Residual Risk
- Activation needs the next hms/nrs plus a fresh agent client. As of 2026-10-10, nsjail was not on PATH (Home Manager gen 150), so live sandbox behaviour is unverified until then.

## Hint Feedback
- None.
