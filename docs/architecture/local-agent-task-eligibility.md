# Local Agent Bounded-Task Eligibility Contract

> Renamed from `qwen-task-eligibility.md` — now model-agnostic. Current deployment: Qwen3-35B via LOCAL-AGENT.md.

**Status:** Accepted — Phase 58A.5 (2026-05-18)
**Upstream authority:** `docs/architecture/role-matrix.md` (implementer role definition)
**Stability:** Frozen for Phase 58A. Promotion of new task classes requires a named eligibility-revision slice.

---

## Purpose

Define the task classes the active local model may take as implementer, the complexity bounds within
which it operates without escalation, and the promotion path if a task proves larger than the bounded
scope.

Qwen (Qwen3.6-35B, local llama.cpp, ~90–120 s/response, 27 GB RAM, 12 GPU layers) is the primary local inference engine. Its strengths are bounded file-scope work, compact summaries, template checks, and simple validation helpers. Its constraints are large-context synthesis, cross-file policy decisions, and tasks requiring extended multi-turn reasoning.

The local lane is not a lower-trust or second-class agent. It uses the same identity, role,
authorization, lifecycle, evidence, privacy, monitoring, and review contracts as remote lanes. It is
treated differently only where measured capability and physical constraints require different task
shaping, concurrency, context, timeout, generation, and tool budgets. Those constraints must be
declared in routing policy and telemetry; they must not be hidden in prompts or converted into a
claim that local reasoning is categorically ineligible.

Local execution has three distinct modalities:

| Modality | Canonical use | Contract distinction |
|---|---|---|
| `local-agent` / coding | bounded edits and tool loops | role injection, strict tool allowlist, task eligibility, progress phases, flagship review |
| local logic/direct | ballots, classification, bounded analysis, fixture generation | compact structured output, explicit token/time budget, no tool authority unless assigned |
| embedded | retrieval and similarity only | no role or instruction injection; vectors are evidence inputs, never review verdicts |

The router selects among these modalities; callers must not bypass it by constructing raw local
payloads. All llama.cpp generation must use `build_llama_payload()` and a named switchboard profile,
enforced by the payload-SSOT gate. This is a target invariant: known direct-path drift remains a C1
adoption blocker until static and live parity evidence proves convergence.

---

## Eligible task classes

### Tier A — autonomous implementation, flagship integration review required

The local agent may complete these without intermediate supervision and propose a candidate with
validation evidence. Integration still requires an independent risk-appropriate flagship review;
the lighter Tier-A distinction affects implementation autonomy, not acceptance authority.

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

Even for Tier A, the local agent must: run all applicable tier-0 gates before proposing a candidate;
record PULSE.log pulses after each file write; stay within the declared slice scope; and emit a typed
implementation receipt for flagship review. It does not commit directly.

### Tier B — bounded, review gate required

The local agent may implement these, but the output must pass an independent reviewer whose active
review policy resolves eligibility as `binding_flagship` before integration:

| Task class | Examples | Gate requirement |
|---|---|---|
| Multi-file patch (≤ 4 files) | refactor across related files, align two modules | Claude or Gemini reviewer; PASS verdict before commit |
| New Python module (< 200 lines) | new utility, new helper class | Reviewer checks correctness and scope |
| New Nix module or service option | new `options.nix` block, new service | Reviewer checks NixOS constraints |
| New shell script | new automation helper | bash -n + reviewer check |
| Compact synthesis | summarize a phase, produce a brief from multiple docs | Reviewer checks factual accuracy |

### Tier C — ineligible (escalate to orchestrator)

The local agent must **not** attempt these as binding implementation or acceptance authority. Surface
them to the orchestrator instead:

| Task class | Reason |
|---|---|
| Open-ended architecture design | requires large-context synthesis across many files |
| Cross-file policy decisions | routing, trust, delegation policy affecting multiple surfaces |
| Multi-agent coordination or binding review | routing agents, assigning slices, or final acceptance; bounded advisory review/dissent remains eligible |
| Final acceptance of its own work | implementer may not self-promote to reviewer |
| Destructive operations without explicit scope | deleting canonical surfaces, retiring modules |
| New kernel object proposals | must go through a named kernel-revision slice |
| Remote or external-account operations | push to remote, PR creation, API writes |
| Tasks whose measured phase budgets exceed the active hardware profile | park or surface with typed phase/timeout evidence; never apply a universal 300 s cutoff or retry silently |

---

## Complexity bounds

| Dimension | Limit | On breach |
|---|---|---|
| Files changed per slice | ≤ 4 (Tier A: 1, Tier B: ≤ 4) | Escalate to orchestrator for decomposition |
| Total lines changed | ≤ 200 (Tier A), ≤ 400 (Tier B) | Escalate |
| Inference timeout | phase-specific and profile-driven; never below the measured minimum viable budget | Park or surface the exact prefill/generation/tool phase; do not retry silently |
| Context window | compact per profile card (local-tool-calling: 2400 tok input) | Use memory/context offload via `aq-context-bootstrap` early |
| Max tool calls per task | 30 (aq-agent-loop default) | Stop and surface partial result |

---

## Escalation protocol

When the local agent determines a task exceeds its eligibility:

1. **Stop.** Do not attempt the out-of-scope portion.
2. **Record.** Write to `.agent/collaboration/PULSE.log`: task, scope, reason for escalation.
3. **Preserve partial work.** If Tier A sub-tasks were completed, submit them as a bounded candidate
   with evidence; do not commit or integrate them from the implementer role.
4. **Surface.** Return the escalation note to the orchestrator for decomposition.

---

## Promotion path

If the active local model successfully completes a task class at Tier B multiple times with clean
review verdicts, the orchestrator may note it as a promotion candidate. Promotion to Tier A requires:
- ≥ 3 clean PASS verdicts from a reviewer on equivalent tasks.
- Orchestrator decision recorded in a HANDOFF.md.
- Eligibility document updated in a named eligibility-revision slice.

---

## Review gate integration

All local implementation tiers are subject to the common flagship review receipt contract; Tier B
requires the more detailed multi-file/security checklist:
- Reviewer is selected from healthy eligible flagship lanes and cannot be the implementing identity.
- The local implementer must produce the required artifact form: diff + validation evidence + acceptance criteria check + risk note.
- No self-acceptance: if no reviewer is available, mark `PENDING_REVIEW` in HANDOFF.md.

## Recursive feedback and promotion

Every local timeout, truncation, malformed tool call, capability escalation, review defect, hardware
pressure event, and successful correction is recorded with the effective model artifact, profile,
modality, phase budgets, prompt/tool contract version, and subject hash. The feedback path is:

```text
typed finding -> issue/evidence -> reproducible fixture or eval case
-> candidate prompt/profile/tool/routing change -> shadow comparison
-> independent flagship review -> canary/soak -> promote or roll back
```

Feedback may improve the shared agent contract or a modality-specific projection. It must not
automatically train, rewrite prompts, expand tools, or promote task eligibility from a single result.
Repeated clean evidence may trigger the existing promotion path; failures remain visible after a
successful retry.

---

## Hardware and inference notes

These are a versioned deployment snapshot, not universal local-agent policy. Routing consumes the
active model/hardware capability record and measured telemetry; changing the local model or hardware
does not weaken the common authority, evidence, review, or feedback contract.

- Qwen3.6-35B runs at `--n-gpu-layers 12` on Renoir APU. Full 41-layer offload causes `ErrorDeviceLost`.
- Inference: ~90–120 s/response. All callers must use 300 s+ timeout.
- `aq-agent-loop` provides the primary agentic interface: `aq-agent-loop --task "..." [--max-calls N]`.
- Delegation: `delegate-to-local --mode agent --prompt "..." [--wait]`.
