# PRD: Universal Agent Workflow Parity
**Date**: 2026-05-13
**Owner**: hyperd
**Status**: Active
**Phase plan**: `.agents/plans/phase-31-agent-workflow-parity.md`

---

## Problem Statement

The harness operates a multi-agent team (Claude, Codex, Gemini, local Qwen via Continue/switchboard) but
workflow quality is inconsistent. Claude and Codex consistently produce auditable, secure, slice-based
work. Other agents skip PRD creation, plan before context is gathered, commit large blobs, and miss
security validation. Research confirms AI-generated code contains **2.74× more vulnerabilities** than
human-written equivalents (Veracode 2025), making consistent pre-commit validation gates mandatory.

Additionally, OWASP Top 10 for Agentic Applications 2026 identifies prompt injection, hallucinated
dependencies, insufficient output validation, and privilege creep as the primary agent security risks.
Any agent performing code generation must have these checks built into its workflow.

---

## Goals

1. All agents (remote and local) follow the same 7-step canonical workflow for any non-trivial task
2. Every agent applies the security checklist before committing code
3. Context engineering replaces context-stuffing — agents retrieve what slice needs, not everything
4. Memory checkpoints make work resumable and auditable across sessions
5. Every commit is atomic (one slice), small, and has validation evidence

---

## Canonical Workflow (7 Steps)

```
ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE(slice) → VALIDATE → COMMIT
```

See `.agent/WORKFLOW-CANON.md` for the full contract with security checklist and examples.

---

## Scope

### In Scope
- `.agent/WORKFLOW-CANON.md` — single source of truth for the canonical workflow
- `.agent/GEMINI.md` — Gemini CLI and Code Assist instructions
- `nix/home/base.nix` — Continue config rules for local Qwen lanes
- `nix/modules/services/switchboard.nix` — `harnessAwareBody` shared system prompt
- `AGENTS.md` — harness-wide policy baseline

### Out of Scope
- Changing model routing logic, switchboard profiles, or inference configs
- Adding new harness services or ports
- Modifying CLAUDE.md (it is the benchmark, not a target)

---

## Constraints

- Switchboard profile cards are injected as system prompts: must stay compact (< 300 tokens)
- Continue config rules are JSON strings: no markdown headers, keep each rule ≤ 2 sentences
- Agent instruction files (GEMINI.md, AGENTS.md) may be longer but must stay scannable
- No new external dependencies — all workflow tooling already exists in `scripts/ai/`

---

## Acceptance Criteria

- [ ] `WORKFLOW-CANON.md` exists with 7-step workflow, security checklist, context rules, commit format
- [ ] `GEMINI.md` references WORKFLOW-CANON and implements all 7 steps
- [ ] Continue config rules include PRD gate, memory checkpoint, and security validation rule
- [ ] `harnessAwareBody` in switchboard.nix includes compact workflow + security summary
- [ ] `AGENTS.md` has a Canonical Workflow Contract section pointing to WORKFLOW-CANON
- [ ] All changes pass `tier0-validation-gate.sh --pre-commit`
- [ ] Each slice committed atomically with validation evidence in commit message

---

## Security Requirements (OWASP Agentic Top 10 — 2026)

Every agent MUST apply before committing any code change:
1. No hardcoded secrets, API keys, passwords, or tokens
2. Validate all external data / LLM outputs as untrusted — sanitize before use
3. Verify all library/package references exist before adding as dependencies
4. Check for injection patterns: SQL, shell, path traversal, XSS
5. Run syntax validation: `bash -n` for shell, `python3 -m py_compile` for Python
6. Privilege check: does this change require more permissions than it should?
7. Integration check: if auth/security middleware added, verify it is wired in

---

## References

- Canonical workflow: `.agent/WORKFLOW-CANON.md`
- Phase plan: `.agents/plans/phase-31-agent-workflow-parity.md`
- OWASP Top 10 Agentic 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- Addy Osmani LLM workflow: https://addyosmani.com/blog/ai-coding-workflow/
- Context engineering: https://sparkco.ai/blog/agent-context-windows-in-2026-how-to-stop-your-ai-from-forgetting-everything
