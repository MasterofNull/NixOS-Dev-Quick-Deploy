---
name: ai-service-management
description: Instructions and workflow for the ai-service-management skill.
---

# Skill Name: ai-service-management

## Description
Operate the AI stack in a **K3s-first** way using Kubernetes resources in the `ai-stack` namespace.

## K3s-First Policy
- Do **not** use legacy `podman-local-ai-*` workflows for normal operations.
- Treat podman-based flows as legacy/debug-only unless explicitly requested.

## When to Use
- Check AI stack readiness in K3s
- Roll out config/image changes safely
- Restart or scale AI services
- Troubleshoot failing pods, probes, and image pulls
- Verify service endpoints after deployment

## Prerequisites

## Core Workflow

### 1) Validate Cluster + Namespace
```bash
```

### 2) Deploy / Reconcile AI Stack
```bash
```

### 3) Observe Health
```bash
./scripts/ai-stack-health.sh
```

### 4) Troubleshoot
```bash
```

### 5) Restart / Rollout
```bash
```

## Service Endpoints (Typical)
- AIDB: `http://localhost:8091` (via service/port-forward)
- Qdrant: `http://localhost:6333` (cluster service)
- Llama.cpp/vLLM endpoints: per active deployment/service

## Common Recovery Actions
- Validate quotas/policies when pods are Pending

## Related Skills
- `nixos-deployment`
- `health-monitoring`
- `ai-model-management`
- `aidb-knowledge`

## Notes
- If local workstation services are needed outside K3s, document that as a separate explicit workflow.
- Keep this skill aligned with `docs/UNIFIED-AI-STACK.md` and K3s manifests.

## Maintenance
- Version: 1.0.0
- Keep this skill aligned with current repository workflows.
