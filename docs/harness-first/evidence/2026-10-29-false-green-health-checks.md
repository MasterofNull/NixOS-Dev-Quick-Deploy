# False-green health checks: svc-security-audit and svc-mcp-integrity (2026-10-29)

Branch `fix/false-green-health-checks`. Uncommitted at time of writing.

## Symptoms (live journal)

ai-security-audit.service (21:31 boot, same at 16:26, 16:45):

    pip coverage: 0 files
    WARNING: zero pip-audit coverage (scanner missing or requirements unscannable)
    WARNING: pip-audit failed on 3 requirements files
    Security audit summary: blocking=0 status=ok
    ai-security-audit.service: Deactivated successfully.

`latest-security-audit.json`: `status: ok`, `summary.pip = {scanner_available: true, files_scanned: 0}`.

ai-mcp-integrity-check.service (hourly):

    [mcp-integrity] No baseline at /var/lib/nixos-ai-stack/mcp-source-baseline.sha256 - skipping check (run scripts/security/update-mcp-integrity-baseline.sh first)
    ai-mcp-integrity-check.service: Finished ...

## Root causes

A) The tool was NOT missing: pkgs.pip-audit was already on the unit PATH. pip-audit failed on all 3
requirements files (aidb, hybrid-coordinator, nixos-docs) with
`python3.13: No module named pip` ->
`CalledProcessError: ['.../python3-3.13.17/bin/python3.13', '-m', 'pip', '--version']`.
pip-audit's dependency pip-api shells out to `$PIPAPI_PYTHON_LOCATION` (default `sys.executable`, the bare
nixpkgs python3 which has no pip). Requirements were fine: with the variable pointed at
`python3.withPackages (ps: [ps.pip])`, `pip-audit -r ai-stack/mcp-servers/nixos-docs/requirements.txt`
succeeds (exit 0, full dependency list, no vulns).
Second producer defect: `overall_status` only considered vulns/dashboard/secrets errors, so zero coverage
and tool failures were warnings that left `status=ok` and exit 0 (only CI=true blocked).

B) check-mcp-integrity.sh treated a missing baseline as `exit 0` after a stderr line. The baseline was never
created (`/var/lib/nixos-ai-stack` is root:root 711), so the hourly check has verified nothing.

## Fixes

- nix/modules/services/mcp-servers.nix (ai-security-audit): `PIPAPI_PYTHON_LOCATION` -> python with pip,
  `XDG_CACHE_HOME=/tmp/pip-audit-cache` (ProtectSystem=strict + PrivateTmp), and
  `SECURITY_AUDIT_FAIL_ON_DEGRADED=1`.
- scripts/security/security-audit.sh: new `degraded` status (scanner missing, zero pip coverage, pip-audit
  or npm audit errors) with `degraded_reasons[]` in the report. A genuine vuln finding keeps
  `status=findings` (precedence) and blocking exit 1. With `SECURITY_AUDIT_FAIL_ON_DEGRADED=1` a degraded run
  exits 3, so the unit shows as failed. Without it (local/dev) exit stays 0, matching the existing tests.
- scripts/testing/check-mcp-integrity.sh: missing baseline -> writes
  `$ALERT_DIR/mcp-integrity-baseline-missing.json`, prints ERROR, exits 2. Never creates the baseline.
- dashboard/backend/api/routes/aistack.py: docstring lists `degraded` (route passes status through unchanged).

Alert path: failed units are already surfaced by `aq-health-spider` (`_failed_systemd_units`, systemctl
--failed) and `_aq-qa-bash` check 0.1.2 (failed `ai-*` units). The dashboard `/security/audit` route
returns `status` and now `degraded_reasons`.

## Tests

    $ bash scripts/testing/test-security-audit-gate.sh
    PASS: security-audit gate blocks on seeded finding, passes clean, flags no-coverage as degraded
    $ bash scripts/testing/test-mcp-integrity-baseline.sh
    PASS: mcp-integrity missing baseline is non-ok, tamper alerts, baseline never auto-created

Covers: pip-audit failing => degraded + exit 3 under FAIL_ON_DEGRADED; zero coverage => degraded;
pip-audit absent from PATH => non-ok with "scanner missing"; covered clean scan => ok; missing baseline =>
exit 2, no baseline created, alert file written; matching baseline => PASS; tamper => exit 1.
`shellcheck -S warning` clean on all four scripts; `nix-instantiate --parse mcp-servers.nix` OK.
Live fix verification of the pip fix: pip-audit with PIPAPI_PYTHON_LOCATION=python-with-pip ran exit 0 on nixos-docs.

## Activation after rebuild (owner acts; sudo)

1. Rebuild: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (no DB jobs running).
2. Create the initial MCP baseline ONCE (needs root: `/var/lib/nixos-ai-stack` is root:root 711):
   `sudo env MCP_SERVER_DIR=<repo>/ai-stack/mcp-servers bash <repo>/scripts/security/update-mcp-integrity-baseline.sh`
   Review that the tree is the intended deployed one first; this blesses what is installed. Until done the
   hourly unit now fails (by design).
3. `sudo systemctl start ai-security-audit.service`, then
   `jq '.status,.degraded_reasons,.summary.pip' /var/lib/ai-stack/security/latest-security-audit.json`
   Expect `ok` and files_scanned 3; a `degraded` result or failed unit is now the real signal.
4. `systemctl status ai-mcp-integrity-check.service` should be PASS after step 2.

Note: if the repo-structure lint requires registering the new test file, add
scripts/testing/test-mcp-integrity-baseline.sh to config/repo-structure-allowlist.txt.
