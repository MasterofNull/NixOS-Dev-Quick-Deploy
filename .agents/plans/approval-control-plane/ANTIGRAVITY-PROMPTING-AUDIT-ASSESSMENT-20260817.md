---
doc_type: design-review
id: antigravity-prompting-audit-assessment-20260817
title: "Orchestrator assessment of Antigravity's agent-prompting comparison (verify-before-adopt)"
status: complete
parent_prd: approval-control-plane
reviewer: claude-opus-4-8
verdict: CONCERNS
owner: hyperd
date: 2026-08-17
---

# Assessment of ANTIGRAVITY-AGENT-PROMPTING-COMPARISON-20260817 (for all agents)

Antigravity is an untrusted advisory lane; every claim is verified against actual files before adoption.
Mixed result: one finding is INVALID (wrong file), one is VALID and worth acting on.

## Verified against actual files (2026-08-17)
| Antigravity claim | Reality | Verdict |
|---|---|---|
| CLAUDE.md is "14 lines / 728 chars, only lean-ctx table, lacks behavioral rules" | The **global** `~/.claude/CLAUDE.md` is 18 lines. The **project** `CLAUDE.md` is **22,797 B / 279 lines** — the 20 behavioral rules, Fable-parity, delegation, commit discipline | **Finding A INVALID** — audited the global config, missed the project one |
| LOCAL-AGENT.md "43KB" | 44,194 B / 670 lines | **VALID** |
| CODEX.md "27KB" | 27,330 B / 422 lines | **VALID** |
| ".cursorrules exists" | (verify presence before recommending edits) | unverified |

## ADOPT (valid, roll into a slice)
- **Trim LOCAL-AGENT.md (44KB) + CODEX.md (27KB) bloat.** Move verbose step-by-step prose to on-demand
  sections (read at the step, not session-start); keep active files to constraints + checklists + aliases.
  This is real context-window cost every session. Agent-parity (Rule 16): apply the trim across
  CLAUDE/CODEX/LOCAL/GEMINI + WORKFLOW-CANON consistently, not one file.
- **Interactive aliases (STR/ELI/FOCUS/REF)** — cheap, useful; add to a shared reference the surfaces + all
  agent files point to (once, not duplicated per file).

## EVALUATE WITH CARE (tension with existing invariants)
- **Structured payload reference points ([D-x]/[R-x]/[H-x]) in approval_request summaries.** Good for
  OPERATOR scannability/anti-fatigue, BUT the P0 privacy invariant + the beginner-friendly requirement make
  Layer-1 `summary` deliberately plain (no codes/jargon) — a beginner reads "Activate the scheduler
  service", not "[D-3]". Resolution: put reference points in **Layer-3 technical_trail** (for the operator's
  Details drill-in + agent scanning), keep Layer-1 plain. Do NOT compromise the beginner surface.

## REJECT / MOOT
- **"Append communication/tone/banned-phrase rules to CLAUDE.md"** — based on the wrong file; those rules
  already exist (project CLAUDE.md + AGENTS.md + `.agent/FABLE-PARITY-CONTRACT.md` govern tone, "lead with
  outcome", selective-then-clear, no-emojis, symbols-for-token-savings). Adding more is redundant bloat —
  ironic given the bloat finding.

## Cross-cutting note for all agents (the important one)
**Verify Antigravity before adopting.** It produced a confident, specific report that audited the wrong
CLAUDE.md — exactly the fabrication risk that makes it review-gated. Half its recommendations dissolve on a
2-minute file check. Ingest the VALID parts (bloat trim, aliases, Layer-3 reference points); discard
Finding A.

## Source: IndyDevDan video
The comparison references an IndyDevDan video (Opus 5 "senior vs smartass"). Its raw principles are not in
this repo — an agent adopting video-derived guidance should get the actual points from the owner, not from
Antigravity's paraphrase alone.
