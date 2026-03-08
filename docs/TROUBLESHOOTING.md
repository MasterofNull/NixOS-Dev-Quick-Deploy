# Troubleshooting

Status: Active

This file is the required root troubleshooting entrypoint for repo structure and deploy-doc validation checks. The detailed current procedures live in:

- `docs/operations/OPERATOR-RUNBOOK.md`
- `docs/operations/reference/QUICK-REFERENCE.md`
- `docs/agent-guides/02-SERVICE-STATUS.md`
- `docs/archive/root-docs/KNOWN_ISSUES_TROUBLESHOOTING.md`

## Current First Checks

```bash
aq-qa 0 --json
aq-qa 1 --json
bash scripts/health/system-health-check.sh --detailed
bash scripts/ai/ai-stack-health.sh
python3 -m pytest tests/integration/test_mcp_contracts.py -v
```
