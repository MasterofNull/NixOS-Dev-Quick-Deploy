# PROJECT-SOTA-MULTIDOMAIN-SWEEPER-RADAR-PRD.md
# Wave 9: SOTA Autonomous Multi-Domain Intelligence Sweeper & Frontier Radar Ingestion

**Status**: IN_PROGRESS
**Lead / Author**: Lead Orchestrator & Senior Engineering Council (MasterofNull)
**Target Release**: Wave 9 / AQ-OS v2.4
**Date**: 2026-10-26

---

## 1. Executive Summary & Objective

Close the architectural disconnection between background durable sweepers (`aq-durable-sweeper`) and frontier intelligence discovery (`aq-radar-ingest`).

Transform our background sweeper from a passive, single-file reader into a **proactive, full-spectrum engineering intelligence engine**. It autonomously harvests, filters, and ingests actionable developments across **all 5 operational engineering disciplines** of AQ-OS:
1. **Agentic Factory & Multi-Agent Architecture** (PRM, context pruning, speculative decoding, memory models).
2. **Declarative Systems, OS & Confinement** (NixOS developments, microVMs, Landlock, eBPF, AppArmor, CVEs).
3. **Frontend Design, Cockpit & Ergonomics** (OKLCH, telemetry HUDs, low-latency UI, canvas/D3).
4. **Quantitative & Stochastic Financial Engineering** (Market microstructure, state filtering, Kalman filters).
5. **Testing, Reliability & Verification** (Formal verification, invariant fuzzing, flake elimination).

---

## 2. Multi-Perspective Council Evaluation (Rule 8 PRD Gate)

1. **Systems Architecture**:
   - `aq-durable-sweeper` runs under `systemd.user.services.aq-durable-sweeper` on an hourly timer.
   - On each tick, it invokes `aq-radar-ingest scan --deep` across configured categories.
   - High-signal findings are automatically indexed into Qdrant (`skills-patterns`, `best-practices`, `error-solutions`) using BGE-M3 embeddings, and operational facts are written to MemoryBroker (`:8003/api/memory/facts`).
2. **Failure Modes & Resilience**:
   - Network timeouts on any single arXiv/RSS/GitHub feed must be caught and logged gracefully (fail-soft, non-fatal).
   - Rate-limiting (e.g. arXiv 3s delay or GitHub API limits) must be strictly respected.
   - The tick must complete within a bounded timeout (max 180s) to prevent systemd service hang.
3. **Security & Confinement**:
   - External text ingested from untrusted RSS/APIs is treated as untrusted data (OWASP LLM01: Prompt Injection protection).
   - Ingested files written to `.agent/research/papers/` and vector DB payloads are sanitized.
   - No shell evaluation or dynamic imports of external code during ingestion.
4. **NixOS Declarative State**:
   - The existing timer in `nix/modules/services/durable-sweeper.nix` executes the sweeper script declaratively.
   - State checkpoints remain strictly in `/var/lib/aq-durable-agent/sweeper-state.json` or fallback `~/.local/share/aq-durable-agent/`.
5. **Economical Execution & Token Efficiency**:
   - System 1 deterministic heuristics and keyword filtering first (cost: 0 tokens).
   - Only preprints/articles meeting a high relevance threshold (>0.75) undergo vector embedding or MemoryBroker ingestion.
6. **Observability**:
   - Ingestion counts and category distributions are stored in `sweeper-state.json`.
   - Exposed via existing `/api/aistack/durable/sweeper` and `/api/aistack/advanced/runtime-summary` to the Mission Cockpit HUD.
7. **Anti-Gaming**:
   - Ingestion metrics reflect actual hashes, valid arXiv IDs, and verifiable URLs. No simulated mock data.

---

## 3. Scope of Implementation

### Slice 9.1: Expand Radar Registry & Feed Parsers (`scripts/ai/aq-radar-ingest`)
- Add keyword sets for all 5 domains (Architecture, OS/Confinement, Frontend/UX, Quant/Finance, Verification).
- Implement multi-protocol parsing in `aq-radar-ingest`:
  - RSS/Atom for research papers (arXiv CoRR, Quant, Stats, Econ).
  - JSON API endpoints for Security Advisories & CVEs (`github-security-advisories`, `cisa-kev`, `osv-dev`).
- Add `--auto-embed` flag to `aq-radar-ingest` that automatically calls `scripts/data/seed-rag-knowledge.py` and MemoryBroker for high-signal discoveries.

### Slice 9.2: Wire Proactive Multi-Domain Sweeper (`scripts/ai/aq-durable-sweeper`)
- Upgrade `sweep_local_sources` to execute multi-domain live sweeps.
- Map discovered intelligence to domain categories in `sweeper-state.json`.
- Log discovery metrics to `.agent/collaboration/PULSE.log`.

### Slice 9.3: Verification & Integration Test Suite
- Add integration test `scripts/testing/test-multidomain-sweeper.py`.
- Verify end-to-end ingestion, classification, and vector indexing.
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` (all 71 checks green).
