# False-green health checks: svc-security-audit and svc-mcp-integrity (2026-10-29)

Branch `fix/false-green-health-checks`. Uncommitted at time of writing.

## Objective
Stop svc-security-audit and svc-mcp-integrity from reporting green when they verified nothing (zero pip-audit coverage; missing MCP integrity baseline).

## Workflow/Session IDs
- Branch: `fix/false-green-health-checks`
- No review run id recorded in this doc at time of writing.

## Delegation Decision
Implemented by Claude Sonnet (Rule 17 cheapest eligible), orchestrated by Claude Opus; review by local Qwen.

## Commands Executed
- `bash scripts/testing/test-security-audit-gate.sh`
- `bash scripts/testing/test-mcp-integrity-baseline.sh`
- `shellcheck -S warning` on the four scripts
- `nix-instantiate --parse` on `nix/modules/services/mcp-servers.nix`
- `pip-audit -r ai-stack/mcp-servers/nixos-docs/requirements.txt` with `PIPAPI_PYTHON_LOCATION` set to a python with pip
- Post-rebuild commands for the owner are listed under Activation after rebuild.

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
  An empty or malformed baseline (no valid record actually verified, or any malformed record) writes
  `mcp-integrity-baseline-invalid.json` and exits 2 as well; tamper (exit 1) keeps precedence.
- scripts/security/security-audit.sh (review follow-up): npm absent with npm projects needing a scan now
  counts them as npm errors and adds the degraded reason "npm scanner missing (N npm projects unscanned)".
  The exit-3 decision uses a `coverage_incomplete` flag (any degraded reason, including dashboard or secrets
  scan errors) instead of `status=degraded`, so dashboard/secrets errors (status `findings`) cannot bypass
  it; real findings still exit 1 first.
- dashboard/backend/api/routes/aistack.py: docstring lists `degraded` (route passes status through unchanged).

Alert path: failed units are already surfaced by `aq-health-spider` (`_failed_systemd_units`, systemctl
--failed) and `_aq-qa-bash` check 0.1.2 (failed `ai-*` units). The dashboard `/security/audit` route
returns `status` and now `degraded_reasons`.

## Validation Evidence

    $ bash scripts/testing/test-security-audit-gate.sh
    PASS: security-audit gate blocks on seeded finding, passes clean, flags no-coverage as degraded
    $ bash scripts/testing/test-mcp-integrity-baseline.sh
    PASS: mcp-integrity missing baseline is non-ok, tamper alerts, baseline never auto-created

Third review follow-up (fix the class): scripts/security/security-audit.sh routes every scanner result (pip-audit,
npm audit, dashboard scan, secrets rotation plan) through one helper, `validate_scanner_report`. A report is
accepted only if the file exists, is non-empty, parses as a JSON object, has the scanner's required keys with the
right types, and its status is in an explicit allowlist (pip/npm: no `error` key; dashboard: `ok|degraded`;
secrets: `ready|planning_required`). Otherwise the degraded reason is "<name> report invalid: <why>" and the run
is `coverage_incomplete`. Scanner x failure mode, with the resulting status and exit under
`SECURITY_AUDIT_FAIL_ON_DEGRADED=1` (every cell is a test case in scripts/testing/test-security-audit-gate.sh):

| Scanner | missing tool/script | nonzero exit | empty output | malformed JSON | `{}` | unknown status/shape |
|---|---|---|---|---|---|---|
| pip-audit | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 |
| npm audit | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 |
| dashboard scan | degraded, 3 | findings, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 |
| secrets rotation | degraded, 3 | findings, 3 | degraded, 3 | degraded, 3 | degraded, 3 | degraded, 3 |

Fourth review follow-up (valid-but-no-coverage). A report that passes the helper must also carry explicit coverage
evidence; nothing is defaulted:

- pip: every dependency has a `vulns` array or a `skip_reason`; a requirements file with >=1 requirement line must
  list >=1 non-skipped dependency (`{"dependencies":[]}` and all-skipped reports are incomplete).
- npm: numeric `info,low,moderate,high,critical` must all be present (`{"metadata":{"vulnerabilities":{}}}`, string or
  missing counters are incomplete).
- dashboard: all three check statuses are present, and `ok` requires every check `ok`; `degraded` is itself a
  degraded reason ("dashboard scan reported degraded"). A bare `{"status":"ok"}` is invalid.
- secrets: `core_ready` boolean and `summary.total_managed_secrets` >= 1 are required. `planning_required` with full
  evidence means the plan ran and rotation prerequisites are unmet: a state finding, deliberately informational
  (status ok, exit 0), not a coverage gap.
- Dashboard and secrets report files are truncated before each run, so a stale report from a previous run cannot
  satisfy a scanner that exits 0 without writing.

Extended table, result under the flag (columns are the modes above plus valid-but-no-coverage; all fail with exit 3):

| Scanner | valid-but-no-coverage inputs (all degraded, 3) |
|---|---|
| pip-audit | `{"dependencies":[]}`; all deps skipped; dep with neither `vulns` nor `skip_reason` |
| npm audit | `{}` counters; string counter; only high/critical/total |
| dashboard | no `checks`; status ok with a non-ok check; status `degraded`; stale prior report with no-op scanner |
| secrets | no `core_ready`/summary; 0 managed secrets; empty summary; stale prior report with no-op scanner |

Known residual, not changed: an npm project with `package.json` but no `package-lock.json` is skipped silently (it
cannot be audited); degrading on it could permanently fail the live unit and needs an owner decision.

Dashboard and secrets scanner execution errors keep the presentation status `findings` (existing behavior) but
still fail the unit via `coverage_incomplete`. A healthy baseline (all four scanners valid) stays `ok`, exit 0.

Second review follow-up: npm output that is empty or lacks a `metadata.vulnerabilities` object (even with exit 0) is
counted as an npm audit error; a missing or non-executable dashboard or secrets scan script is a degraded reason
("<check> scanner unavailable") and sets `coverage_incomplete`. Tests: empty-output npm => degraded, exit 3 under
the flag; nonexistent dashboard scanner with clean pip/npm => degraded, exit 3 under the flag.

Review follow-up cases: empty, malformed and blank baselines => exit 2 with the invalid alert; npm missing
with an npm project and clean pip => degraded and exit 3 under the flag; pip error plus dashboard error with
no vulns => exit 3 under the flag (exit 0 without it).

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

## Rollback Plan
Revert the commit and rebuild. Emergency: unset `SECURITY_AUDIT_FAIL_ON_DEGRADED` so a degraded audit exits 0 again.

## Residual Risk
- Not verified live: the rebuild, the one-time MCP baseline creation and the post-rebuild audit run are owner acts (sudo) and have not been done.
- Until the baseline is created, the hourly ai-mcp-integrity-check unit fails by design.
- A degraded audit now fails the unit; pip-audit coverage after rebuild is expected to be 3 files but is unconfirmed.
- The new test file may need registering in `config/repo-structure-allowlist.txt`.

## Hint Feedback
No aq-hints used for this slice.
