---
title: AQ Inference Benchmark Matrix
doc_type: prd
id: aq-inference-bench
status: active
owner: mlops-engineering
last_updated: 2026-06-29
---

# AQ Inference Benchmark Matrix

## Problem

Agents need a local, repeatable way to compare inference backends before routing work to them. Today the harness has service health checks and a llama.cpp benchmark, but no shared matrix that agents can query for TTFT proxy latency, tokens/sec, strict JSON reliability, memory pressure, and runtime eligibility across current and future local backends.

## Goals

- Add a repo-local `aq-inference-bench` CLI that all agents can run.
- Keep the first slice localhost-only and dry-run by default.
- Validate backend definitions before any live benchmark execution.
- Record the capability in the system catalog and validation registry.
- Provide tests that exercise config validation, dry-run behavior, local-only security gates, and live execution against a fake localhost endpoint.

## Non-Goals

- Enable external model servers.
- Install vLLM, SGLang, Ollama, MLX, or other runtimes.
- Replace `aq-llama-benchmark.py`.
- Persist benchmark results to the production metrics database in this slice.

## Requirements

- `scripts/ai/aq-inference-bench validate --json` reports policy and backend validity.
- `scripts/ai/aq-inference-bench list --json` exposes backend/case metadata.
- `scripts/ai/aq-inference-bench run --json` performs a dry-run without network calls.
- `scripts/ai/aq-inference-bench run --execute --backend <id> --json` only runs enabled localhost backends.
- Config lives in `config/aq-inference-benchmarks.json` with a JSON schema beside it.
- Catalog and validation registry reference the CLI, config, schema, and tests.

## Security

- Deny external runtime execution by default.
- Require `policy.localhost_only=true`.
- Reject non-localhost `base_url` values.
- Require `policy.activation_gate=capability-intake`.
- Keep planned runtimes in config as discoverable, non-executable entries until admitted.

## Acceptance

- `python3 scripts/testing/test-aq-inference-bench.py` passes.
- `python3 scripts/testing/test-system-capability-catalog.py` passes.
- `python3 scripts/ai/aq-capability-catalog check-doc` passes.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` passes or any unrelated existing failures are logged.
