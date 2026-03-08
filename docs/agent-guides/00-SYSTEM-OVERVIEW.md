# System Overview

**Purpose**: Describe the current local AI stack, how it is deployed, and which services are authoritative for operators and agents.

## What This System Is

This repository runs a declarative NixOS AI stack with host-local `systemd` services, local model inference, retrieval infrastructure, and an operator-facing dashboard/API. The current runtime is not K3s-first and it is not a container-orchestrated control plane.

Core characteristics:

- NixOS modules define ports, service wiring, and environment injection.
- `systemd` units run the active AI stack on host-local ports.
- Local LLM inference is provided by `llama.cpp` and an embeddings service.
- Retrieval, memory, and coordination depend on Qdrant, PostgreSQL, and Redis.
- The dashboard API and shell QA scripts are the main operator health surface.

## Main Components

### Dashboard API and Health Surface

- `command-center-dashboard-api.service`
- Endpoint: `http://127.0.0.1:8889`
- Provides `/api/health`, `/api/health/aggregate`, and AI metrics endpoints.

### AIDB

- AIDB API endpoint: `http://127.0.0.1:8002`
- Used for local project knowledge and AI stack integration workflows.

### Hybrid Coordinator

- `ai-hybrid-coordinator.service`
- Endpoint: `http://127.0.0.1:8003`
- Handles hybrid orchestration, memory endpoints, and authenticated stats queries.

### Local Model Runtime

- `llama-cpp.service` on `127.0.0.1:8080`
- `llama-cpp-embed.service` on `127.0.0.1:8081`
- Exposes OpenAI-compatible local inference and embeddings endpoints.

### Data Services

- Qdrant on `127.0.0.1:6333`
- PostgreSQL on `127.0.0.1:5432`
- Redis on `127.0.0.1:6379`

### Automation

- `ai-prsi-orchestrator.service`
- `ai-prsi-orchestrator.timer`
- Runs periodic PRSI/optimizer automation and can be validated manually.

## Security Features

- Secrets are loaded from runtime secret providers such as `/run/secrets/*`, not hardcoded into docs, code, or service definitions.
- Sensitive hybrid routes require API-key authentication and should be checked with local secret-backed requests.
- Core operator endpoints are documented as host-local services on `127.0.0.1`, which is the current safe default exposure model.
- Port and endpoint values are intended to flow from Nix options and environment injection rather than scattered literals.
- Operator validation includes both health and auth smoke checks, not only process liveness.

## Current Runtime Model

```text
NixOS modules
  -> typed options in nix/modules/core/options.nix
  -> AI stack wiring in nix/modules/roles/ai-stack.nix
  -> service endpoints exported through config/service-endpoints.sh

systemd units
  -> dashboard API
  -> AIDB
  -> hybrid coordinator
  -> llama.cpp + embeddings
  -> postgres / redis / qdrant
  -> PRSI timer and one-shot automation
```

## Operator Workflow

Use these as the current source of operational truth:

- `README.md`
- `docs/operations/OPERATOR-RUNBOOK.md`
- `docs/operations/reference/QUICK-REFERENCE.md`
- `docs/operations/reference/QUICK-REFERENCE-CARD.md`

Use these commands for routine checks:

```bash
bash scripts/health/system-health-check.sh --detailed
bash scripts/ai/ai-stack-health.sh
aq-qa 0 --json
aq-qa 1 --json
python3 -m pytest tests/integration/test_mcp_contracts.py -v
```

## What Is No Longer Current

These are no longer the active operating model:

- K3s-first operator guidance
- pod or PVC-based runbook assumptions
- AIDB on port `8091`
- dashboard guidance that points to port `8888`
- MindsDB and Hugging Face TGI as current required runtime components

## Next Step

Read [01-QUICK-START.md](01-QUICK-START.md) for the task-oriented entry point.
