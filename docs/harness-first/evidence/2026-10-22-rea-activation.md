---
title: "Evidence: REA Sandboxed Integration & Activation Attestation (w1-s4)"
date: 2026-10-22
author: antigravity
status: completed
tags:
  - rea
  - sandboxing
  - activation
  - security
---

# REA Sandboxed Integration & Activation Attestation

## 1. Objective
Complete Slice W1-S4 in `.agents/plans/sota-rounding/DESIGN.md`: record activation attestation across the 6 DoD dimensions and establish the durable evidence record for the REA (Reverse Engineer Anything) capability.

## 2. Six-Dimension Activation Attestation (DoD)
- **Integrated**: Pinned sandboxed launcher `scripts/ai/mcp-rea-sandboxed` integrated with admission enforcement into `config/agent-capability-intake-candidates.json`, projected to client configuration files (`.claude/settings.json`, `.gemini/settings.json`, `.mcp.json`).
- **Turned ON**: Admitted and activated in `config/system-capability-catalog.json`.
- **Functionally Validated**: Verified end-to-end via `scripts/testing/test-rea-sandbox.py` and `scripts/testing/test-enabled-external-mcp-candidates.py`:
  - Network isolation (`bwrap --unshare-all`).
  - Secret protection: `/run/secrets` and `~/.ssh` inaccessible.
  - Immutability: target quarantine binary mounted read-only.
  - Fail-closed: refuses execution when candidate state != `enabled`.
- **Observable**: Invocations, sandbox denials, and target hashes tracked via `aq-report`.
- **Intervenable**: Immediate operator kill-switch supported via `aq-capability-intake disable rea-reverse-engineering` or declarative Nix option.
- **PM-Tracked**: Tracked under `.agents/plans/sota-rounding/tracker.json` (`w1-s1` through `w1-s4`).

## 3. Verification Commands & Evidence
- `python3 scripts/testing/test-rea-sandbox.py`: PASS.
- `python3 scripts/testing/test-enabled-external-mcp-candidates.py`: PASS.
- `python3 scripts/testing/test-capability-intake.py`: PASS.
