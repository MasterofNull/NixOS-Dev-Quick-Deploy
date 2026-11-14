# DESIGN: SOTA Agentic Operating System (`AQ-OS`), Co-Evolving System 1 / System 2 Collective & Verified Software Factory (`frugal-sota-leadership-20261113` — Rev 2)

- **Plan ID**: `frugal-sota-leadership-20261113`
- **PRD Reference**: `.agent/PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md`
- **Status**: `ROUND 1 REVISED (Folded Simurg@gemini + Simurg@claude Round 1 Debate; Simurg@local in-flight; Codex unavailable: session window closed, recorded not substituted)`
- **Author**: `Simurg@gemini/gemini-4-argon#05b9c7ce`
- **Independent Reviewers**:
  - `Simurg@claude/claude-sonnet-5-5#claude-20261113-184611-57y8dl` (`.agents/plans/frugal-sota-leadership-20261113/claude.md` — all 7 Round 1 findings folded into Rev 2 below)
  - `Simurg@local#local-20261113-184559-utr1pk` (running on local `llama.cpp`)
- **Date**: 2026-11-13

---

## 1. Objective & Five-Pillar Leadership Architecture

Establish and maintain a verifiable SOTA lead across five interlocking pillars within our sovereign operating envelope (27 GB RAM / 12 GPU-layer laptop + pooled basic cloud subscriptions with zero API overages):
1. **Declarative Agentic Operating System (`AQ-OS` on NixOS)**: Kernel/systemd/AppArmor containment, compiled Rust trust/state gates (`aq-state` L1–L5), generation-fenced self-healing (`ai-stack-health-monitor` + `attention_queue`), and hardware/thermal-aware lifecycle (`aq-keep-awake` + `aq-llama-resume-gate`).
2. **Co-Evolving Local "System 1" Models Inside `AQ-OS`**: Fast local reflexes (sub-20ms CPU statistical/feature routers with `<90°C` emergency thermal ceiling, `AIDB` embeddings/rerankers, and bounded `Qwen`/`llama.cpp` specialists) continuously distilled and calibrated from compiler-and-reviewer-verified **System 2** trajectories (`Claude`, `Codex`, `Gemini`).
3. **Deterministic Compiler, Verifier, Test & Gate Phalanx**: Sub-second CPU verification (`tier0.d`, `aq-qa` phases 0–N, Rust `aq-state`, `basedpyright` + `ruff` ratchets, tree-sitter AST checks, call-graph contract checks, fault-injection & real-JS DOM harnesses) that catches defects locally for `$0.00` before any cloud review turn is spent.
4. **Multi-Model Collaborative Environment (`Simurg` Collective)**: Cross-family independent review (`aq-land` — never self-review), provenance-signed memory collapse with CLI-direct owner conflict resolution (`Persona P3` rev 3 — KISS), and pooled subscription quota arbitrage + `AGENT-CATCHUP-QUEUE.md`.
5. **Ecosystem Leverage & Reciprocity**: Quarantined intake of external SOTA research/swarms (`osint-systems` + `capability-intake`), explicit citation ledger (`ECOSYSTEM-RECIPROCITY.md`, NEW), and owner-decided in the CLI ("Propose-Not-Push"; the current agent asks, no aq-approve/human_gate) upstream contribution packets (`aq-rsi reciprocity-packet`).

---

## 2. Round 1 Debate Dispositions (Folding `Simurg@claude` `57y8dl`)

| # | Round 1 Finding (`Simurg@claude#57y8dl`) | Resolution in Rev 2 (`DESIGN.md` & Prototypes) |
|---|---|---|
| **D1** | **Q1 — Exemplar budget must be inside the `2,500` total, not additive (`2,900`)** | Enforced in `aq-context-packet` (NEW): `exemplar_budget = 400` is subtracted from `max_tokens = 2500` (`code_budget = max_tokens - exemplar_budget - header_overhead`), keeping total packet tokens strictly `<= 2,500`. |
| **D2** | **Q1 — Log every AST signature degradation event** | `aq-context-packet` records `"degraded_to_signatures": true|false` and `"degraded_files": [...]` in its telemetry/JSON output so context starvation is observable. |
| **D3** | **Q1 — Exemplar selection must be CPU-only (no neural embedding step)** | Exemplar matching in `aq-context-packet` uses deterministic CPU-only lexical + path-prefix + AST-symbol overlap over the last 200 verified rows in `trajectories.jsonl` (`0` neural tokens, `<10ms`). |
| **D4** | **Q2 — 1-min `0.70 * cpu_count` loadavg flaps on indexing bursts; use hysteresis or 5-min average** | `system1_router.py` (NEW) uses **5-minute load average (`os.getloadavg()[1] / cpu_count`) with hysteresis**: enters pause at `> 0.70` and exits pause only when `load5_ratio <= 0.55`. |
| **D5** | **Q2 — CPU routers need an own-cost cap and thermal ceiling** | `system1_router.py` (NEW) enforces a `<20ms` execution budget and an emergency thermal ceiling (`max_temp_c >= 90.0°C` skips local evaluation and immediately offloads/defers). |
| **D6** | **Q2 — Define explicit disposition for gated neural tasks (never drop silently)** | When `is_neural_system1_eligible` returns `False`: (a) background jobs (`is_background_job=True`) return `disposition = "defer_cooldown"`, and (b) active slice tasks return `disposition = "substitute_remote"` and route to the cheapest healthy Tier-2 subscription lane. |
| **D7** | **Q3 — `redact_secrets` alone misses novel secret shapes; add fail-closed post-redaction scan across all 4 fields** | `collect-verified-trajectories.py` (NEW) runs `redact_secrets` + path normalization across `context_packet`, `rejected_attempts`, `verified_diff`, and `review_receipt`, followed by `post_redaction_quarantine_scan()` (private-key headers, `/run/secrets/`, bearer tokens, and Shannon entropy `>= 4.3` mixed-case 32+ char tokens). Any residual hit returns `status = "quarantined"` and refuses to write. |

---

## 3. Five Execution Slices (`F1`–`F5`)

### Slice F1 — SOTA Software Factory Engine: `aq-context-packet` & Pre-Review Compiler Wall
- **Owned Paths**: `scripts/ai/aq-context-packet` (NEW), `scripts/ai/aq-land`, `scripts/testing/test-aq-context-packet.py`
- **Prototype**: `.agents/delegation/outputs/frugal-sota-leadership/aq-context-packet-prototype.py`

### Slice F2 — `AQ-OS` & `Simurg` Collaborative Fabric: Quota Arbitrage, 5-Min Hysteresis Thermal/Load Guard & `VW/kT`
- **Owned Paths**: `scripts/ai/lib/outcome_receipt.py` (NEW), `scripts/ai/aq-keep-awake`, `scripts/ai/delegate-to-local`, `config/model-coordinator.json`, `scripts/testing/test-subscription-arbitrage.py`
- **Prototype**: `.agents/delegation/outputs/frugal-sota-leadership/system1_router_prototype.py`

### Slice F3 — Co-Evolving Local "System 1" Distillation Pipeline, Quarantine Scanner & Calibration Harness
- **Owned Paths**: `scripts/data/collect-verified-trajectories.py` (NEW), `scripts/ai/lib/system1_router.py` (NEW), `scripts/testing/test-system1-calibration.py`
- **Prototype**: `.agents/delegation/outputs/frugal-sota-leadership/collect_verified_trajectories_prototype.py`

### Slice F4 — Ecosystem Leverage & Reciprocity Engine: Citation Ledger & `aq-rsi reciprocity-packet`
- **Owned Paths**: `docs/architecture/ECOSYSTEM-RECIPROCITY.md` (NEW), `scripts/ai/aq-rsi`, `scripts/data/seed-rag-knowledge.py`, `scripts/testing/test-ecosystem-reciprocity.py`

### Slice F5 — SOTA Leadership Scoreboard & Glass-Box Factory Showcase
- **Owned Paths**: `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`, `scripts/testing/harness_qa/phases/phase0.py`, `scripts/testing/test-dashboard-frugal-scoreboard.py`
