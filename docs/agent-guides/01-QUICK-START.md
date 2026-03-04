# Agent Quick Start

## Default Run Loop

1. Plan with harness:
```bash
curl -sS -X POST http://127.0.0.1:8003/workflow/plan \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  -d '{"query":"<objective>"}'
```
2. Start workflow run with intent contract:
```bash
curl -sS -X POST http://127.0.0.1:8003/workflow/run/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  -d '{"query":"<objective>","intent_contract":{"user_intent":"<intent>","definition_of_done":"<done>","depth_expectation":"standard","spirit_constraints":["declarative-first"],"no_early_exit_without":["validation_evidence"]}}'
```
3. Pull hints before edits:
```bash
curl -sS -H "X-API-Key: $(tr -d '[:space:]' </run/secrets/hybrid_coordinator_api_key)" \
  "http://127.0.0.1:8003/hints?q=<objective>&agent=codex"
```

## Required Verification

```bash
scripts/check-mcp-health.sh
scripts/quick-deploy-lint.sh --mode fast
scripts/validate-runtime-declarative.sh
scripts/check-prsi-phase7-program.sh
scripts/aq-report --since=7d --format=text
```

## Delegation Roles

- `gemini`: research and declarative tuning proposals.
- `qwen`: implementation-oriented patch proposals.
- `claude` (if enabled): architecture/risk synthesis.
- Orchestrator/reviewer: accepts or rejects every slice by evidence gate.
- Sub-agent rule: if you are the delegated worker, do not assume orchestrator authority; execute your slice only and return evidence/rollback notes.
