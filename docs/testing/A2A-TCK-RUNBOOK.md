# A2A TCK Runbook

Use the upstream A2A Technology Compatibility Kit against the live hybrid
coordinator instead of relying only on local smoke tests.

Runner:

- `bash scripts/testing/run-a2a-tck.sh`

Defaults:

- category: `mandatory`
- SUT URL: `http://127.0.0.1:8003`
- auth: `X-API-Key` from `/run/secrets/hybrid_api_key` when available
- report path: `/tmp/a2a-tck-mandatory-report.json`

Examples:

```bash
bash scripts/testing/run-a2a-tck.sh
bash scripts/testing/run-a2a-tck.sh capabilities
A2A_TCK_CATEGORY=all A2A_TCK_REPORT_PATH=/tmp/a2a-tck-all.json \
  bash scripts/testing/run-a2a-tck.sh
```

Important boundary:

- The hybrid coordinator currently targets A2A v0.3.0 over JSON-RPC plus SSE.
- `pushNotifications=false` remains intentional.
- Mandatory TCK coverage is the minimum bar for claiming core compatibility.
- Capability, quality, and `all` runs are useful for parity tracking, but may
  expose optional gaps that are not part of the current runtime contract.

Evidence to capture after a run:

- category used
- report path
- pass/fail result
- any failing requirement IDs from the JSON report

Rollback:

- remove `scripts/testing/run-a2a-tck.sh`
- remove `docs/testing/A2A-TCK-RUNBOOK.md`
