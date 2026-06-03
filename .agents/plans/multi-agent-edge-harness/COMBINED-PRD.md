---
doc_type: prd
id: maeah-combined-prd
title: "Multi-Agent Edge Harness — Combined PRD"
status: active
owner: AI Stack Maintainers
last_updated: "2026-05-31"
---

# Multi-Agent Edge Harness — Combined PRD

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-31

## Vision

The Multi-Agent Edge Harness (MAEAH) provides the runtime substrate for all
collaborative agent operations on the NixOS AI stack. It defines the contracts
by which agents delegate, communicate, and maintain parity with the canonical
kernel declaration.

## Problem Statement

Multiple agents (Claude Code, Gemini CLI, Codex CLI, local Qwen3) operate
concurrently but lack a unified boundary contract. Without parity enforcement:
- Role confusion (implementer self-promoting to reviewer)
- Context leakage across agent turns
- Untracked delegation chains with no audit trail
- Silent divergence between agent-specific instruction files

## Goals

1. **Agent Identity**: Every dispatch carries source, role, and autonomy boundary.
2. **Delegation Traceability**: Full chain from orchestrator to leaf agent logged.
3. **Parity Enforcement**: Each agent's behavior is validated against the kernel declaration.
4. **Graceful Degradation**: Local model failure falls back to orchestrator, never silently drops.

## Non-Goals

- Replacing existing delegation scripts (aq-drop, delegate-to-gemini, etc.)
- Cross-host federation (single-node NixOS only)
- Real-time streaming parity checks

## Architecture

See `PARITY-INTEGRATION-PLAN.md` for execution slices.
See `docs/architecture/role-matrix.md` for role definitions.
See `docs/architecture/canonical-kernel-declaration.md` for kernel contracts.

## Success Criteria

- All agent dispatches carry identity envelope (Phase 73+)
- Delegation chain logged in `.agents/delegation/registry.jsonl`
- Parity-index updated on each role-matrix change
- Zero unauthenticated agent-to-agent calls

## API Surface Contract (AM-C1/AM-C2)

The harness exposes the following canonical HTTP surfaces. All surfaces must
be validated via `edgeai contracts check --json` before MAEAH readiness is
asserted.

### OpenAI-compatible responses endpoint

- `POST /v1/responses` — OpenAI Responses API shim. Routes through the
  coordinator's `chat/completions` path until native Responses support lands.
  Advertises `X-OpenAI-Responses-Compat` header to mark the compatibility
  boundary. Implemented in `extensions/openai_a2a_handlers.py`.

### Admin model lifecycle

- `/admin/v1/models` — Canonical model lifecycle prefix. Mounts alongside
  `/api` compatibility aliases. Mutating operations (POST, DELETE) require
  either `X-Dashboard-Internal` (loopback-only) or a valid API key. Unauthenticated
  mutations are rejected with 403.

### Runbook

See `LIVE-VALIDATION-RUNBOOK.md` for the step-by-step live validation sequence.

## References

- `docs/architecture/canonical-kernel-declaration.md`
- `docs/architecture/role-matrix.md`
- `docs/architecture/agent-behavior-parity-index.md`
- `.agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md`
- `.agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md`
