---
doc_type: prd
id: osint-active-recon-gate-prd
title: OSINT Active Recon Runtime Gate PRD
status: active
owner: codex
phase: "OSINT Active Recon Gate"
priority: P1-high
evidence_required: osint_recon_status reports runtime state without execution; osint_recon fails closed without scope_ack and allow_active_recon; insecure Maigret/MOSAIC and provisioning-only BBOT remain blocked; tooling manifest routes OSINT prompts to passive evidence plus status gate; aq-qa and tier0 pass.
---

# OSINT Active Recon Runtime Gate PRD

## Problem

Passive OSINT research is active, but the active recon surface advertised tools whose runtimes are missing, provisioning-only, or held for insecure package review. Agents need machine-readable status and a fail-closed gate before any active recon can be considered.

## Goals

- Keep passive `osint_research_ingest` and `osint_research_query` as the default path.
- Add a machine-readable `osint_recon_status` tool for coordinator and local agents.
- Make `osint_recon` deny by default unless explicit target scope, caller acknowledgement, policy enablement, and an admitted runtime are present.
- Preserve Maigret, MOSAIC, and BBOT blocks until capability-intake and package/runtime work is complete.
- Route OSINT prompts through the passive store and status gate automatically.

## Non-Goals

- No new external installs.
- No live recon in tests.
- No authenticated scraping, evasion, exploit probing, or vulnerability scanning.
- No storage of raw unbounded recon output.

## Acceptance Criteria

- `osint_recon_status` appears in coordinator MCP tools and local-agent built-ins.
- `osint_recon` returns structured `blocked` responses for Maigret and missing scope acknowledgement.
- Tooling manifest selects `osint_recon_status` for OSINT recon prompts and does not auto-select active execution unless explicit authorized-active wording is present.
- Focused OSINT tests and tier0 pass.
