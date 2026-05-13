
# Implementation Plan: Layer-Aware Health Validation

**ID:** PLAN-2026-05-13-QA
**Objective:** Enhance `aq-qa` to support targeted OSI layer auditing.
**Dependencies:** ADR-007, OSI-LAYER-MAPPING.md

## 🎯 Phase 1: Check Discovery (Discovery)
- Audit existing health checks in `scripts/ai/aq-qa` or associated check scripts.
- Tag each check with its corresponding OSI layer (1-7).

## 🛠️ Phase 2: CLI Enhancement (Implementation)
- Add `--layer <N>` argument to the `aq-qa` interface.
- Implement filtering logic to only execute checks matching the requested tier.
- Ensure "Causality Mode" is supported: if checking Layer 5, automatically verify L1-L4 first or report "Degraded Confidence" if they aren't checked.

## 📊 Phase 3: Reporting (Observability)
- Update `aq-qa` JSON output to group results by layer.
- This structure will feed the Command Center Dashboard's "Layer Health" visualization.

## ✅ Validation Criteria
1. `aq-qa --layer 1` only runs NixOS/Hardware checks.
2. `aq-qa --layer 5` fails if Postgres or AIDB is unreachable.
3. Output format remains compatible with `aq-prime.py` health mapping.

## 📝 Rollback Plan
- Revert changes to `aq-qa` and its associated discovery libraries.

**Status:** PENDING
**Owner:** Implementer Agent
**Reviewer:** Orchestrator
