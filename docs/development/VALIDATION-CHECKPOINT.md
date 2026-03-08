# Validation Checkpoint - Day 2 Infrastructure
Status: Historical
Owner: AI Stack Maintainers
Last Updated: 2026-03-08

This checkpoint document belongs to an older Podman and Kubernetes transition effort. It is retained only as historical validation context.

It should not be used as the current validation workflow.

Use these current validation paths instead:
- `aq-qa 0 --json`
- `aq-qa 1 --json`
- `bash scripts/health/system-health-check.sh --detailed`
- `bash scripts/ai/ai-stack-health.sh`
- `python3 -m pytest tests/integration/test_mcp_contracts.py -v`
