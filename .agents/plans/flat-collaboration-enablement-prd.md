---
doc_type: prd
id: flat-collaboration-enablement-prd
title: Flat Collaboration Enablement PRD
status: active
owner: codex
phase: "Flat Collaboration Enablement"
priority: P1-high
evidence_required: aq-flat-prd-gate reports collaboration flags enabled; topic packages require proposals, cross-reviews, consensus artifacts, and reviewer separation; tooling manifest auto-selects flat_prd_gate for collaboration prompts; aq-qa phase 0 and tier0 pass.
---

# Flat Collaboration Enablement PRD

## Problem

Flat model-team collaboration was documented but not active. The local-agent and workflow automation config flags still disabled broad collaboration, while the existing guard only validated artifact shape and did not treat disabled rollout flags as a failure.

## Goals

- Enable collaboration flags in repo config.
- Keep proposal, cross-review, consensus, and reviewer-separation evidence mandatory.
- Let agents auto-select the flat PRD gate for collaboration and consensus planning prompts.
- Preserve the existing deny-by-default posture for external tools and unrelated MCP/plugin enablement.

## Acceptance Criteria

- `scripts/ai/aq-flat-prd-gate --machine` returns `ok: true` with both feature flags enabled.
- Disabled rollout flags fail focused regression tests.
- Same-author review artifacts fail topic validation.
- `workflow_tool_catalog()` selects `flat_prd_gate` for flat collaboration prompts.
- `aq-qa 0` and tier0 pass before commit.
