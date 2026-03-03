# Advanced Parity Tooling

This document lists the additional parity tooling for policy, regression gates, reliability, and cross-client compatibility.

## Entry point

```bash
./scripts/run-advanced-parity-suite.sh
```

## Components

- `scripts/evaluate-agent-policy.py`  
  Evaluate profile/task/tool decisions from `config/agent-routing-policy.json`.

- `scripts/route-reasoning-mode.py`  
  Classify query reasoning/retrieval mode and token budget.

- `scripts/run-harness-regression-gate.sh`  
  Golden eval gate (`data/harness-golden-evals.json`), supports `--offline` and `--online`.

- `scripts/chaos-harness-smoke.sh`  
  Failure-injection smoke checks for malformed payloads and invalid transitions.

- `scripts/check-boot-shutdown-integration.sh`  
  Detect systemd/journal warning patterns tied to boot/shutdown regressions.

- `scripts/check-api-auth-hardening.sh`  
  Verify API auth middleware/static exceptions and optional runtime auth behavior.

- `scripts/validate-ai-slo-runtime.sh`  
  Validate runtime metrics against `config/ai-slo-thresholds.json`.

- `scripts/smoke-cross-client-compat.sh`  
  Client matrix check across raw HTTP, JS RPC wrapper, and Python SDK.

## Signed skill registry

- `scripts/sign-skill-registry.sh`
- `scripts/verify-skill-registry.sh`

Use with:

```bash
./scripts/aqd skill sign-index dist/skills/index.json config/keys/skill-registry-private.pem
./scripts/aqd skill verify-index dist/skills/index.json config/keys/skill-registry-public.pem
./scripts/aqd skill bundle-install dist/skills/index.json skill-creator /tmp/skills \
  --signature dist/skills/index.json.sig --public-key config/keys/skill-registry-public.pem
```

## Provenance/SBOM

```bash
./scripts/generate-harness-sdk-provenance.sh
```

Outputs:
- `dist/harness-sdk-provenance/provenance.json`
