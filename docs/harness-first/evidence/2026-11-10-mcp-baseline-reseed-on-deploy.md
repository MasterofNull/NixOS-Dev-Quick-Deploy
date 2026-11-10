# MCP integrity baseline audited reseed on verified deploy evidence

Date: 2026-11-10

Incident `rsi-ca0351661b7f40e08d42ab50` & owner decision (2026-11-10):
accepted MCP server merges left `/var/lib/nixos-ai-stack/mcp-source-baseline.sha256`
stale until manually refreshed, causing `ai-mcp-integrity-check.service` and
deploy QA check `0.1.2` to fail after every MCP code update.

Changes (`codex-20261110-092415-wyavom`):

1. PRD recorded at `.agents/plans/system-integrity-recovery/P0.6-mcp-baseline-reseed-on-deploy-20261110-PRD.md`.
2. `scripts/security/update-mcp-integrity-baseline.sh`: computes old-vs-new
   SHA-256 diff (`changed`, `added`, `removed`, `counts`) and appends a single
   `fsync`ed JSON record to `mcp-baseline-audit.jsonl` (or `MCP_INTEGRITY_AUDIT_LOG`)
   with UTC timestamp, actor (`SUDO_USER`/`USER`), and `MCP_BASELINE_GIT_REV`
   before installing the `0644` baseline. Preserves empty-directory refusal and
   existing baseline/audit on error.
3. `scripts/maintenance/aq-deploy-current`: adds Step 8b after Step 8 revision
   verification (`rc == 0` guard, before Step 9 live `aq-qa 0`), reading
   `MCP_SERVER_DIR` and `MCP_INTEGRITY_BASELINE` from `ai-mcp-integrity-check.service`
   via `shlex` (no shell eval), reseeding with `MCP_BASELINE_GIT_REV="$want"`,
   and running `sudo systemctl start ai-mcp-integrity-check.service`.
4. Added `scripts/testing/test-mcp-baseline-reseed.py` (6 tests covering first
   seed, changed/added/removed diff, empty refusal, audit failure preservation,
   escaped filenames, deploy guard ordering, and stubbed step-8b execution) and
   registered in `config/ci-checks.json` (`tests-misc-i-m`).

Validation:

- `bash -n scripts/security/update-mcp-integrity-baseline.sh scripts/maintenance/aq-deploy-current` — pass.
- `python3 scripts/testing/test-mcp-baseline-reseed.py` — 6 tests pass.
- `scripts/maintenance/aq-deploy-current --help` — exits 0.
- `python3 scripts/testing/test-ci-checks-manifest.py` — pass (8 checks).

Activation attestation (2026-11-10): wired into `aq-deploy-current` Step 8b and
`update-mcp-integrity-baseline.sh`; live execution deferred to owner's next
`aq-deploy-current` run (sudo boundary).
