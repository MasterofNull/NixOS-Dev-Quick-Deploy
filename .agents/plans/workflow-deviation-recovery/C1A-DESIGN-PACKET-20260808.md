---
doc_type: plan
id: workflow-deviation-recovery-c1a
title: Workflow Deviation Recovery C1A Observation and Intake
status: active
owner: codex-orchestrator
date: 2026-08-08
parent_prd: workflow-deviation-recovery
---

# C1A design packet

C1A repairs the live autonomous-improvement false-green and adopts the C0
contract for one producer and PRSI shadow intake. It does not execute a repair,
alter prompts/routing, launch an agent, or activate external effects.

## Changes

1. Normalize the current `routing_decisions` SQLite schema while retaining a
   typed legacy `routing_log` reader; unknown schema raises.
2. Resolve the routing database through the env-contract/Nix SSOT.
3. On observation failure, append a closed deviation receipt and raise so
   systemd records failure. Healthy/no-trigger remains the only `None` result.
4. PRSI validates deviation records and queues eligible records as
   `shadow_queued`; it never sends them to `aq-optimizer` directly.
5. Focused tests prove current/legacy/unknown schemas, receipt durability,
   fail-closed exit semantics, deduplication, and no execution eligibility.

C1B will add the host broker required for sandboxed `aq-loop` and remote-agent
writers. Direct caller-owned registry/event writes remain prohibited.

