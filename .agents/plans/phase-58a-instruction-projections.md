# Phase 58A.3 — Instruction-Plane Projections

## Objective

Ensure all agent instruction surfaces project role and routing constraints from the canonical SSOTs (role-matrix.md, routing-profile-inventory.md) rather than maintaining independent prose definitions. Close the two open items left from 58A.1.

## Scope

**In scope:**
- Add role-matrix SSOT pointer to Qwen SESSION-RULES.md Sub-Agent Boundaries section
- Close role-matrix open items §1 (sub-orchestrator delegation form) and §2 (escalation time-bound)
- Add role-matrix and routing-inventory pointers to on-demand context tables where missing
- Verify sync-agent-instructions coverage

**Out of scope:**
- Full instruction compilation pipeline (long-term target, not Phase 58A)
- Codex first-class instruction surface (delegated slice, requires Codex availability)
- New instruction text beyond pointer/summary projection

## Changes made

| File | Change |
|---|---|
| `.qwen/SESSION-RULES.md` | Sub-Agent Boundaries section updated: role-matrix SSOT pointer, implementer role named, escalation time-bound rule added |
| `docs/architecture/role-matrix.md` | Open items §1 and §2 resolved and rewritten as "Resolved Items" with concrete rules |

## Remaining instruction drift (not yet addressed)

| Surface | Issue | Owner |
|---|---|---|
| Codex (`~/.aider.md`, Codex settings) | No harness-aware first-class instruction surface | Codex (when available) |
| `.gemini/context.md` | Auto-generated; role text comes from GEMINI.md projection already done in 58A.1 | — |
| `AGENTS.md` | No role text (uses workflow steps only); appropriate — no change needed | — |
| `docs/AGENTS.md` (full policy) | Should reference role-matrix.md; not done this slice | Follow-up |

## Acceptance criteria

1. `SESSION-RULES.md` cites role-matrix.md SSOT in Sub-Agent Boundaries section.
2. Role matrix open items §1 and §2 are closed with concrete, actionable rules.
3. No instruction surface relaxes a role-matrix constraint.

## Status

COMPLETE — 2026-05-18

### Evidence
- `SESSION-RULES.md` Sub-Agent Boundaries updated with pointer and escalation time-bound.
- `role-matrix.md` open items closed as "Resolved Items" with concrete delegation form and escalation time-bound rules.
- No behavior-affecting runtime changes made.
