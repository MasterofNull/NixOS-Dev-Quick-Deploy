# Phase 31 — Universal Agent Workflow Parity

## Objective
Standardize all agents (Claude, Codex, Gemini, local Qwen via Continue/switchboard) on the
canonical 7-step workflow defined in `.agent/WORKFLOW-CANON.md`, incorporating OWASP Agentic
Top 10 security checks, context engineering discipline, and auditable slice-based commits.

## Scope Lock
- **In scope**: WORKFLOW-CANON.md, GEMINI.md, base.nix Continue rules, switchboard.nix
  harnessAwareBody, AGENTS.md, phase plan
- **Out of scope**: Model routing changes, new harness services, CLAUDE.md (benchmark, not target)
- **Constraints**: Profile cards ≤ 300 tokens; Continue rules are JSON strings; no new deps

## Workstreams

### 31.1 Canonical workflow reference (WORKFLOW-CANON.md)
- File: `.agent/WORKFLOW-CANON.md`
- Contents: 7-step workflow, security checklist, context engineering rules, commit format
- Acceptance: File exists, covers all 7 steps, OWASP Top 10 table present

### 31.2 Gemini alignment (GEMINI.md)
- File: `.agent/GEMINI.md`
- Changes: Add 7-step workflow replacing simplified version; add security checklist; add
  context engineering rules; add web-research step; add memory checkpoint before executing
- Acceptance: GEMINI.md references WORKFLOW-CANON; all 7 steps present

### 31.3 Continue config rules (base.nix)
- File: `nix/home/base.nix` (Continue config template in createContinueConfig hook)
- Changes: Add PRD gate rule, memory checkpoint rule, security validation rule, context
  engineering rule, dependency validation rule
- Acceptance: 5 new rules added; tests pass; version stays 34.0 (rules-only change)

### 31.4 Switchboard profile cards (switchboard.nix)
- File: `nix/modules/services/switchboard.nix`
- Changes: Extend harnessAwareBody with compact workflow summary + security awareness block
- Acceptance: harnessAwareBody ≤ 300 added tokens; profile cards render correctly

### 31.5 AGENTS.md canonical contract
- File: `AGENTS.md`
- Changes: Add "Canonical Workflow Contract" section pointing to WORKFLOW-CANON; add
  compact security checklist reference
- Acceptance: Section exists; WORKFLOW-CANON referenced; tier0 passes

## Validation
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
bash -n nix/home/base.nix 2>/dev/null || nix-instantiate --parse nix/home/base.nix
python3 scripts/testing/test-aq-qa-continue-config.py
python3 scripts/testing/verify-flake-first-roadmap-completion.sh 2>&1 | tail -3
aq-qa 0
```

## Rollback
- Remove WORKFLOW-CANON.md and PRD
- Revert GEMINI.md, AGENTS.md, switchboard.nix to previous commit
- Revert base.nix Continue config rules; version stays 34.0 unless rules require bump

## Evidence Targets
- All 5 agent instruction surfaces updated
- tier0 green after each slice
- Commits are atomic, one per slice
