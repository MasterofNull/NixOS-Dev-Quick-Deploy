---
title: T3MP3ST Capability Intake
doc_type: prd
id: t3mp3st-capability-intake
status: active
owner: codex
last_updated: 2026-07-06
---

# T3MP3ST Capability Intake PRD

## Problem

T3MP3ST is a third-party offensive-security harness with CLI, War Room, API, MCP, and real network/security tooling. It may contain useful patterns for our AI harness, but direct enablement would expand agent authority into active scanning and exploit workflows before our scope, sandbox, audit, and dashboard gates exist.

## Goals

- Admit T3MP3ST through the existing deny-by-default capability-intake path.
- Fan out review across security, Nix packaging, MCP admission, harness integration, and QA/dashboard lanes.
- Preserve useful architecture and benchmark-verification patterns without granting offensive tool authority by default.
- Define a safe first integration milestone: review-only, pinned, quarantined, no active scanning, no secrets, no external target execution.

## Non-Goals

- Do not clone, install, run, or expose T3MP3ST tools in this PRD slice.
- Do not add network scanning, exploit, password, hash, or payload tools to agent allowlists.
- Do not start a War Room service, MCP server, or background daemon.
- Do not accept AGPL obligations implicitly without license review.

## Fan-Out Lanes

1. Security intake: audit upstream source, scripts, payload surfaces, MCP tools, dependencies, and license obligations.
2. Nix sandbox: design a pinned package or quarantine source fetch with restricted service user, loopback binding, and no default secrets.
3. MCP admission: enumerate tools and propose a denied-by-default allowlist with human approval gates.
4. Harness bridge: propose `aq-tempest` or equivalent wrappers that route through existing scope receipts and switchboard/local-agent controls.
5. QA and observability: add aq-qa checks, dashboard or aq-report visibility, audit events, and rollback.
6. Documentation and policy: update capability catalog, issue backlog, handoff, and operator rules of engagement.

## Acceptance

- `config/agent-capability-intake-candidates.json` contains a blocked T3MP3ST candidate.
- Multi-agent review drops exist for the review-only lanes and explicitly prohibit install or active scanning.
- `scripts/ai/aq-capability-intake audit t3mp3st --json` returns a review-required or blocked admission with visible risk flags.
- `python3 scripts/testing/test-capability-intake.py` passes.
- Tier0 pre-commit gate passes before any commit.

## Promotion Gates

- Pinned upstream commit and reproducible source hash.
- SBOM plus dependency vulnerability scan.
- AGPL compatibility decision.
- Scope receipt model for every target.
- Human approval gate for any active network or exploit tool.
- Loopback-only service defaults.
- MCP admission deny-by-default with explicit safe tool subset.
- Dashboard or aq-report status for enabled state, blocked actions, active missions, and audit log counts.
- Rollback path that removes package, service, MCP config, and tool allowlist entries.
