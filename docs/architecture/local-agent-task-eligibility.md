# Local Agent Bounded-Task Eligibility Contract

> Renamed from `qwen-task-eligibility.md` — now model-agnostic. Current deployment: Qwen3-35B via LOCAL-AGENT.md.

**Status:** Accepted — Phase 58A.5 (2026-05-18)
**Upstream authority:** `docs/architecture/role-matrix.md` (implementer role definition)
**Stability:** Frozen for Phase 58A. Promotion of new task classes requires a named eligibility-revision slice.

---

## Purpose

Define the task classes Qwen may take as implementer, the complexity bounds within which it operates without escalation, and the promotion path if a task proves larger than the bounded scope.

Qwen (Qwen3.6-35B, local llama.cpp, ~90–120 s/response, 27 GB RAM, 12 GPU layers) is the primary local inference engine. Its strengths are bounded file-scope work, compact summaries, template checks, and simple validation helpers. Its constraints are large-context synthesis, cross-file policy decisions, and tasks requiring extended multi-turn reasoning.

---

## Eligible task classes

### Tier A — fully autonomous (no review gate required before commit)

Qwen may complete these and propose a commit with validation evidence:

| Task class | Examples | Size bound |
|---|---|---|
| Single-file Python patch | fix a bug, add a function, adjust config read | ≤ 150 lines changed |
| Single-file Nix edit | add option, fix path, update port reference | ≤ 80 lines changed |
| Single-file shell/bash patch | fix a script, add a flag, adjust output format | ≤ 100 lines changed |
| Compact documentation edit | update a table, fix a factual error, add a code example | ≤ 60 lines changed |
| Test scaffolding | add test cases to an existing test file | ≤ 100 lines changed |
| Config value update | update a JSON/YAML key, fix a stale value | ≤ 20 lines changed |
| Bounded inventory | list files matching a pattern, grep for occurrences, count entries | read-only |
| Simple validation helper | run aq-qa, bash -n, py_compile, nix-instantiate --parse | read-only or one-command |

Even for Tier A, Qwen must: run all applicable tier-0 gates before proposing a commit; record PULSE.log pulses after each file write; stay within the declared slice scope.

### Tier B — bounded, review gate required

Qwen may implement these but the output must pass a review gate (Claude or Gemini reviewer) before integration:

| Task class | Examples | Gate requirement |
|---|---|---|
| Multi-file patch (≤ 4 files) | refactor across related files, align two modules | Claude or Gemini reviewer; PASS verdict before commit |
| New Python module (< 200 lines) | new utility, new helper class | Reviewer checks correctness and scope |
| New Nix module or service option | new `options.nix` block, new service | Reviewer checks NixOS constraints |
| New shell script | new automation helper | bash -n + reviewer check |
| Compact synthesis | summarize a phase, produce a brief from multiple docs | Reviewer checks factual accuracy |

### Tier C — ineligible (escalate to orchestrator)

Qwen must **not** attempt these. Surface them to the orchestrator instead:

| Task class | Reason |
|---|---|
| Open-ended architecture design | requires large-context synthesis across many files |
| Cross-file policy decisions | routing, trust, delegation policy affecting multiple surfaces |
| Multi-agent coordination | routing other agents, assigning slices, review verdicts |
| Final acceptance of its own work | implementer may not self-promote to reviewer |
| Destructive operations without explicit scope | deleting canonical surfaces, retiring modules |
| New kernel object proposals | must go through a named kernel-revision slice |
| Remote or external-account operations | push to remote, PR creation, API writes |
| Tasks requiring > 300 s inference time | use timeout; surface to orchestrator if Qwen times out |

---

## Complexity bounds

| Dimension | Limit | On breach |
|---|---|---|
| Files changed per slice | ≤ 4 (Tier A: 1, Tier B: ≤ 4) | Escalate to orchestrator for decomposition |
| Total lines changed | ≤ 200 (Tier A), ≤ 400 (Tier B) | Escalate |
| Inference timeout | 300 s per call | Surface timeout to orchestrator; do not retry silently |
| Context window | compact per profile card (local-tool-calling: 2400 tok input) | Use memory/context offload via `aq-context-bootstrap` early |
| Max tool calls per task | 30 (aq-agent-loop default) | Stop and surface partial result |

---

## Escalation protocol

When Qwen determines a task exceeds its eligibility:

1. **Stop.** Do not attempt the out-of-scope portion.
2. **Record.** Write to `.agent/collaboration/PULSE.log`: task, scope, reason for escalation.
3. **Preserve partial work.** If any Tier A sub-tasks were completed, commit those first with appropriate evidence.
4. **Surface.** Return the escalation note to the orchestrator for decomposition.

---

## Promotion path

If Qwen successfully completes a task class at Tier B multiple times with clean review verdicts, the orchestrator may note it as a promotion candidate. Promotion to Tier A requires:
- ≥ 3 clean PASS verdicts from a reviewer on equivalent tasks.
- Orchestrator decision recorded in a HANDOFF.md.
- Eligibility document updated in a named eligibility-revision slice.

---

## Review gate integration

Tasks in Tier B are subject to the Gemini review-gate contract (`docs/architecture/gemini-review-gate.md`) applied to Qwen's work:
- Reviewer may be Claude or Gemini (not Qwen itself).
- Qwen must produce the required artifact form: diff + validation evidence + acceptance criteria check + risk note.
- No self-acceptance: if no reviewer is available, mark `PENDING_REVIEW` in HANDOFF.md.

---

## Hardware and inference notes

- Qwen3.6-35B runs at `--n-gpu-layers 12` on Renoir APU. Full 41-layer offload causes `ErrorDeviceLost`.
- Inference: ~90–120 s/response. All callers must use 300 s+ timeout.
- `aq-agent-loop` provides the primary agentic interface: `aq-agent-loop --task "..." [--max-calls N]`.
- Delegation: `delegate-to-local --mode agent --prompt "..." [--wait]`.
