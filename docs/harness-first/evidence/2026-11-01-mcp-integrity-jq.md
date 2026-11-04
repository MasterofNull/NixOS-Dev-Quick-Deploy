# MCP integrity check: jq missing on alert path

## Objective

Let `ai-mcp-integrity-check` write its integrity alert. The unit (`nix/modules/services/mcp-servers.nix`) runs `scripts/testing/check-mcp-integrity.sh`, whose alert branch pipes through `jq`, but the unit declared no `path`, so `jq` was not on the service PATH.

Symptom: the unit exited 127 (`jq: command not found`) instead of writing the alert JSON, observed since 2026-11-01 11:03.

Cause: no `path` attribute on the unit. Its PATH lacked `pkgs.jq`, and `pkgs.coreutils` was not declared explicitly for the `sha256sum`, `cut`, `date`, `mkdir`, `cat`, and `dirname` calls.

Fix:
- `nix/modules/services/mcp-servers.nix`: `path = [pkgs.coreutils pkgs.jq];` on `systemd.services.ai-mcp-integrity-check`.
- `scripts/testing/test-mcp-integrity-unit-path.sh` (new, wired in `config/ci-checks.json`): fails if the unit block lacks `pkgs.jq` or `pkgs.coreutils`.

## Workflow/Session IDs

- Implementer: Claude Haiku (orchestrator claude-opus), 2026-11-01.
- Independent review: local Qwen `local-20261101-134514-vevwv1`, head `b4f7ba7a289012d38a7f180f4d416c00d74989c9`, PASS.

## Delegation Decision

Mechanical single-file Nix edit plus a static test: routed to Haiku (Rule 17); review routed to local Qwen (non-author lane).

## Commands Executed

- `nix-instantiate --parse nix/modules/services/mcp-servers.nix >/dev/null`
- `bash scripts/testing/test-mcp-integrity-unit-path.sh`
- Same test against the pre-fix module (`HEAD` before the change).

## Validation Evidence

- Parse succeeded.
- Test printed `PASS: ai-mcp-integrity-check unit declares pkgs.jq and pkgs.coreutils` (exit 0).
- Against the pre-fix module it printed `FAIL` for both `pkgs.jq` and `pkgs.coreutils` (exit 1).

## Rollback Plan

Revert the PR commit; the unit returns to its previous (broken) PATH. No state migration.

## Residual Risk

- Activation needs an owner rebuild (`aq-deploy-current`). Until then the running unit still lacks jq on PATH.
- Not yet validated live: after rebuild run `sudo systemctl start ai-mcp-integrity-check.service` and confirm exit 0 or a written alert JSON under `/var/lib/ai-mcp-integrity/alerts`.

## Hint Feedback

None.
