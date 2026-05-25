# Phase: OSINT Domain Activation - Research & PRD

**Authors:** Gemini 2.0 Pro (Orchestrator)
**Date:** 2026-05-24
**Phase:** OSINT Domain Discovery & Capability Activation
**Status:** ⟳ PROPOSED (PRD Created)

---

## Executive Summary

Completed an exhaustive 36-pass research and discovery cycle to design a production-grade AI OSINT Agent. This phase established the theoretical and architectural foundation for the `osint-systems` domain, focusing on **Structural Truth**, **Agentic Browsing**, and the **Core Trinity** of OSINT engines.

---

## Key Research Findings

### 1. The Core Trinity
Identified three critical engines for autonomous reconnaissance:
- **BBOT:** Advanced infrastructure and recursive attack surface mapping.
- **Maigret:** High-fidelity identity and social media dossier generation.
- **MOSAIC:** Behavioral and psychological signal synthesis using local LLMs.

### 2. Resilience via Agentic Browsing
Pivoted from brittle static scrapers to **Playwright-based vision agents**. This allows the model to navigate dynamic social media feeds semantically via accessibility snapshots, bypassing CSS-based bot detection.

### 3. Anti-Hallucination: The Verbatim Ledger
Designed a **Verbatim Fact Ledger** pattern where agents only reason over discrete facts extracted from structured tool results and committed to the `osint-intelligence` AIDB namespace.

---

## Artifacts Created

| Artifact | Path | Description |
|---|---|---|
| **PRD** | `.agent/PROJECT-OSINT-SYSTEMS-PRD.md` | Comprehensive domain roadmap and architecture. |
| **Instructions** | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` | Domain-specific agent surface and safety guardrails. |

---

## Next Steps (Proposed Implementation)

1.  **Nix Overlay:** Write custom derivations for `bbot`, `maigret`, and `mosaic` in `flake.nix`.
2.  **MCP Integration:** Deploy a unified OSINT MCP server to bridge the Core Trinity to the models.
3.  **AIDB Schema:** Initialize the `osint-intelligence` namespace with STIX 2.1 support.
4.  **Verification:** Run the first end-to-end "pivoting" validation cycle.

---
*Reference: [Berkeley Protocol on Digital Open Source Investigations]*
