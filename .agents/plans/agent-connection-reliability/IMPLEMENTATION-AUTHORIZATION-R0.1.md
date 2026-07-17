# Implementation Authorization — Agent Connection Reliability R0.1

**Authorization ID:** `auth-agent-connection-reliability-r0.1-20260716`
**Status:** `ACTIVE — OWNER-DIRECTED RESUME (codex session window closed), INDEPENDENT DESIGN PASS`
**Idempotency key:** `acr-r01-legacy-registry-lookup-compat-20260716-single-use`
**Implementer lane:** Claude Sonnet (`balanced` tier via `config/model-coordinator.json`) — owner directed
implementation to lighter models; orchestrator: Fable 5 (this session).

## Frozen inputs

- Design packet: `.agents/plans/agent-connection-reliability/R0.1-LEGACY-REGISTRY-LOOKUP-COMPAT-DESIGN-PACKET.md`
  SHA-256 `41079079cce71ce83e834a7e24a2373813fc3b8311d09d0e9c91a6f591c67633`
  (verified identical to the PASS review subject hash in `R0.1-DESIGN-REVIEW.md`)
- Design review: `.agents/plans/agent-connection-reliability/R0.1-DESIGN-REVIEW.md` — VERDICT: PASS
- R0.1 design commit: `199a36bc`; C0.5B predecessor commit: `1e4826c0`
- Predecessor file hashes (must match at implementation start; mismatch is a hard stop):
  - `scripts/ai/lib/task_registry.py` `70cee61f1873d3e4a1960ce69f8bc4ee5c0e59cde31813962dfaf1ac7d485dba`
  - `scripts/ai/aq-delegation-registry` `06b2eb781afab996683926d418b0ff32fe55ee54901b9b0aa6d623be0c26355d`
  - `scripts/ai/lib/agent_ops_projection.py` `ced66abdcb8082e09ad46dbe2ad1d0e405f1f55667ed62049b11179748bb10ef`
  - `config/schemas/agent-ops-projection.schema.json` `490d9652e49579f4dc16e048604fa5ad6bd1e9a67b69dcb05209dd3e0d316c45`
  - `scripts/ai/aq-tui-dashboard` `926bc07a563f97844568f6f78350fb46a19e45989c489a6e43f35129967fd0ac`
  - `scripts/testing/test-agent-ops-projection.py` `e721108f09c64bd8bcb3f502435e6d476c383fa9e6717371e3c663ad86f1fbbd`
  - `scripts/testing/harness_qa/phases/phase0.py` `97d43f92c7638a6be261ea1ba5934caa8a8e178370b58f48820c54dcde3dc5c4`

## Exact seven-file implementation lease

1. `scripts/ai/lib/task_registry.py`
2. `scripts/ai/aq-delegation-registry`
3. `scripts/ai/lib/agent_ops_projection.py`
4. `config/schemas/agent-ops-projection.schema.json`
5. `scripts/ai/aq-tui-dashboard`
6. `scripts/testing/test-agent-ops-projection.py`
7. `scripts/testing/harness_qa/phases/phase0.py`

Any eighth file is a hard stop. The implementer may not edit the design packet, reviews, this
authorization, registry data (`.agents/delegation/registry.jsonl`), fixtures containing production
registry content, dashboard web backend, JavaScript, Nix modules, services, brokers, wrappers,
policies, prompts, skills, memory, lifecycle data, or routing.

## Binding contract

Implement exactly the accepted design: read-only `lookup_m2a_compatible()` with the frozen physical-line
scanner (§3.2), lookup algorithm (§3.3), closed `aq.registry-lookup-result.v1` CLI shape and frozen exit
codes 0/2/3/4/5/6, sanitized `aq.registry-compatibility-facts.v1` projection input, pure projector (no
I/O/clock/env/import of task_registry in `agent_ops_projection.py`), duplicate-key-rejecting decode at
every depth, 4096-byte strict bound unchanged, 65536-byte legacy containment bound, 50 MiB cumulative
source bound with initial+final fstat agreement, `O_RDONLY|O_CLOEXEC|O_NOFOLLOW`, scan-to-EOF duplicate
target detection, and the full §6 test contract. `show_m2a()`, `_m2a_read_records()`, all mutation
paths, and M2A.33–M2A.41 coverage remain strict and semantically unchanged.

## Non-authority

The implementer may validate (focused tests, Tier0 pre-commit on the exact staged inventory) but cannot
self-accept, stage, commit, deploy, delegate, or expand scope. Exact candidate hashes require
independent acceptance (Codex or Antigravity — not the implementer, not this orchestrator's own
authorship) before orchestrator commit. The nine-file R0.1 web-visibility amendment remains separately
unauthorized and sequences only after this foundation lands. C1–C5, M2B activation, registry migration,
and mutation-path changes remain unauthorized.

`RECORD: single-use grant. Consumed by the first completed implementation attempt against these hashes.`
