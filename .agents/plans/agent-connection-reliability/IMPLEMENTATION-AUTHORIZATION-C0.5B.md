# Implementation Authorization — Agent Connection Reliability C0.5B

**Authorization ID:** `auth-agent-connection-reliability-c0.5b-20260716`
**Status:** `ACTIVE — OWNER PREAUTHORIZED, SONNET DESIGN PASS`
**Idempotency key:** `acr-c05b-agent-ops-projection-20260716-single-use`

## Frozen inputs

- C0.5A commit: `9dfde8f8`
- M2A read-only-show commit: `297728db`
- Design packet: `ed53bb68cb09cf520768e874501ff8ae555d025f1c5c6fc336996c0c5f2c48e3`
- Schema predecessor: `c35b801005f08d15eea606c70ddda12f57c1e69667d6ac61e3a4b916478b6cf3`
- Module predecessor: `09473ddc1a6455294693fbbe42ad7d2eeff222fc081cd42dcb939b6558014bb6`
- Test predecessor: `51a5e7fcc229cd654d52cd1b80b0f58f6bf8dcbce5aa94ef54884e6c17a41970`

## Exact three-file implementation lease

1. `config/schemas/agent-ops-projection.schema.json`
2. `scripts/ai/lib/agent_ops_projection.py`
3. `scripts/testing/test-agent-ops-projection.py`

Any fourth implementation file or frozen-input mismatch is a hard stop. The implementer may not edit
the design/authorization, fixtures, TaskRegistry, collaboration models, TUI/dashboard, wrappers, Nix,
services, prompts, skills, memory, lifecycle data, or routing.

Implement the design's pure injected-facts v2 projection, safe absent defaults, bounded lane summaries,
low-cardinality metrics, health derivation, schema closure, and all 27 vector families. Preserve
M2A.33–41 semantically unchanged. Do not import/call TaskRegistry or `show_m2a`; perform no I/O, process,
network, environment, clock, randomness, provider, telemetry-write, or lifecycle action.

The implementer may validate but cannot self-accept, stage, commit, deploy, delegate, or expand scope.
Exact candidate hashes require independent Sonnet or Antigravity acceptance before orchestrator commit.
C1 remains unauthorized.
