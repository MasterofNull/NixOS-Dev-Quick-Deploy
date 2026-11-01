# MCP integrity check: jq missing on alert path

## Scope

`ai-mcp-integrity-check` (`nix/modules/services/mcp-servers.nix`) runs `scripts/testing/check-mcp-integrity.sh`. Its alert branch pipes through `jq`, but the unit declared no `path`, so `jq` was not on the service PATH.

## Symptom

- The unit exited 127 (`jq: command not found`) instead of writing the integrity alert JSON.
- Observed since 2026-11-01 11:03.

## Cause

The systemd unit had no `path` attribute. Its PATH did not include `pkgs.jq`, and `pkgs.coreutils` was not declared explicitly for the `sha256sum`, `cut`, `date`, `mkdir`, `cat`, and `dirname` calls.

## Fix

- `nix/modules/services/mcp-servers.nix`: added `path = [pkgs.coreutils pkgs.jq];` to `systemd.services.ai-mcp-integrity-check`.
- `scripts/testing/test-mcp-integrity-unit-path.sh` (new): fails if the unit block lacks `pkgs.jq` or `pkgs.coreutils`.

## Evidence

- `nix-instantiate --parse nix/modules/services/mcp-servers.nix >/dev/null` succeeded.
- `bash scripts/testing/test-mcp-integrity-unit-path.sh` printed `PASS: ai-mcp-integrity-check unit declares pkgs.jq and pkgs.coreutils` (exit 0).
- Negative check: the same test run against the pre-fix module (`HEAD`) printed `FAIL` for both `pkgs.jq` and `pkgs.coreutils` (exit 1).

## Limits

- Activation needs an owner rebuild (`aq-deploy-current` or `sudo nixos-rebuild switch`). Until then the running unit still lacks jq on PATH.
- Not yet validated live: after rebuild, trigger the unit once (`systemctl start ai-mcp-integrity-check`) and confirm exit 0 or a written alert JSON under `/var/lib/ai-mcp-integrity/alerts`.
- No commit, PR, or tier0 run in this slice.
