---
title: AI Capability Backlog
doc_type: prd
id: ai-capability-backlog
status: active
owner: codex
last_updated: 2026-06-29
---

# AI Capability Backlog PRD

## Problem

The harness has a working capability catalog and suggested repo queue, but broader capability ideas such as eval suites, observability platforms, training stacks, data stores, visualizations, and security hardening can still live only in chat. That makes them hard for agents to rediscover, compare, prioritize, and safely implement later.

## Goals

- Record high-value AI system capability areas in a machine-readable backlog.
- Preserve security, authority, observability, and validation requirements for each candidate domain.
- Define first safe repo-local implementation slices before any package import or service enablement.
- Wire the backlog into existing catalog and validation governance.

## Non-Goals

- Do not install, enable, clone, or run new third-party tools in this slice.
- Do not grant new network, filesystem, browser, token, or secrets authority.
- Do not promote any candidate beyond research/backlog status without `capability-intake`.

## Acceptance

- `config/ai-capability-implementation-backlog.json` records the requested capability areas.
- Backlog schema and focused validator enforce deny-by-default implementation metadata.
- System capability catalog links to the backlog.
- Validation registry runs the backlog validator.
- Focused validation and tier0 pre-commit pass before commit.
