# Antigravity Contribution — Round 'aqos-system1-selfcompact-v1'

**Agent:** Antigravity (Gemini 3.8 Flash via IDE OAuth Lane)  
**Date:** 2026-09-21  
**Target Round:** `aqos-system1-selfcompact-v1`  
**Reference Document:** `.agents/prompts/AQOS_UNIFIED_SYSTEM1_SELF_COMPACT_META_PROMPT.md`  
**Status:** Independent Expert-Team Review & PRD Amendment Contribution  

---

## 1. Verdict & Architectural Disposition

**VERDICT: RATIFIED WITH ARCHITECTURAL CONSTRAINTS.**

The unification of **System 1 Decision Models** (Jev / `wfzyx/von` / `rlcd-modernbert-151m`) with the **Autonomous Self-Compacting Agent Harness** (IndyDevDan paradigm) represents a necessary and timely evolution for AQ-OS. It directly resolves two core deficits documented in `.agent/PROJECT-AQOS-PRD.md`:
1. **Deficit D3 (File-Based A2A State & Compaction Fragility):** Replaces blunt, provider-enforced auto-compaction and file-clobbering with an autonomous, agent-controlled state rollover anchored to the Redis stream event spine.
2. **Deficits D1, D4 & D8 (God-Service Overload & Heuristic Latency):** Relieves `hybrid-coordinator` and `switchboard` from relying on brittle regex patterns or heavy autoregressive 35B LLM passes for routine, high-frequency operational judgments.

---

## 2. Challenging Assumptions & Grounded Reality Checks

Before committing this architecture to implementation slices, Antigravity identifies three critical operational assumptions that must be strictly bounded:

### A. Memory & Hardware Boundaries on the APU Host (Renoir Node)
- **The Risk:** An assumption that "small models are free."
- **The Ground Truth:** Our Renoir APU host has 27 GB system RAM, with Qwen3-35B GGUF occupying 22.5 GB + 1.0 GB KV-cache + 3.0 GB OS baseline = **23.5 GB committed**, leaving an operational buffer of only ~0.5 GB – 1.0 GB.
- **The Constraint:** 
  - `system1d` MUST NOT be loaded into APU shared VRAM. The 12 offload GPU layers remain reserved exclusively for `llama-server`.
  - The runtime MUST be configured CPU-only (ONNX Runtime with AVX2 or Rust/C++ native runtime) with a hard memory ceiling of **400 MB RSS**.
  - `rlcd-modernbert-151m` (151M params, ~250MB in INT8) is the preferred edge/background service; `wfzyx/von` (395M params, ~600MB–1.2GB) should only be selected if quantization benchmarks confirm RSS stays under the 800 MB safety margin.

### B. Calibration vs. Hallucination Guardrail in Security Gating
- **The Risk:** Treating System 1 probabilities as infallible security oracles for shell safety (`AUTONOMOUS-OPERATIONS-POLICY.md`).
- **The Ground Truth:** Even Brier-calibrated RLCD models have edge-case blind spots with unseen adversarial inputs or novel Unix command flags.
- **The Constraint:** Fail-closed design. System 1 serves as an **acceleration filter**, not a bypass of existing whitelist/blacklist safety filters:
  - If System 1 confidence $< 0.90$ on `is_destructive`: Default to existing Tier-0 / operator approval gate.
  - Regex blacklists for catastrophic commands (`rm -rf /`, `mkfs`, raw block device writes) remain hardcoded and non-bypassable regardless of model output.

### C. Context Threshold Tuning: Asymmetric Scaling for Local vs. Remote
- **The Risk:** Applying 200k token thresholds uniformly to 32k local models.
- **The Constraint:** The 3-tier threshold ladder must be strictly parameterized per model context window:
  - **Remote Models (Claude / Codex — 200k Context):**
    - Notice: 100k tokens (50%)
    - Warning: 150k tokens (75%)
    - Force Cutoff: 180k tokens (90%)
  - **Local Model (Qwen3-35B — 32k Context):**
    - Notice: 16k tokens (50%)
    - Warning: 24k tokens (75%) — *Critical operational buffer: provides 4k tokens to complete current micro-slice*
    - Force Cutoff: 28k tokens (87.5%) — *Locks tools, leaves 4k tokens to write `note_to_self`*

---

## 3. Concrete Workstream Amendments for `PROJECT-AQOS-PRD.md`

### Workstream 1: Kernel Split & Microservices
1. **`system1d.service` (NixOS Microservice):**
   - Packaged in `nix/modules/services/system1.nix`.
   - IPC: High-throughput UNIX Domain Socket at `/run/nixos-ai-stack/system1.sock` (`mode = "0660"`, `user = "ai-stack"`). Sub-millisecond IPC latency with zero TCP network stack overhead.
   - AppArmor Confinement: Read-only access to `/nix/store/` model weights; `deny network inet`, `deny network inet6`.
2. **Context Budget Controller (`ai-stack/mcp-servers/hybrid-coordinator/core/context_budget_controller.py`):**
   - Injects real-time token telemetry into every turn envelope in `switchboard :8085`.
   - Enforces Tier 3 (Force Cutoff) by intercepting non-compaction tool calls with a typed error response.
3. **`self_compact` First-Class Tool:**
   - Added to `config/first-party-tools.json` and registered in `tooling_manifest.py`.

### Workstream 2: Contracts & Schemas
- Versioned Pydantic models and JSON schemas in `contracts/schemas/`:
  - `contracts/schemas/system1/decision-v1.json`: Typed schema for `/v1/systemone` (`noul`, `choice`, `score`).
  - `contracts/schemas/agent-tools/self-compact-v1.json`: Formal schema requiring `note_to_self`, `active_hypotheses`, `completed_milestones`, and `next_exact_command`.
  - `contracts/schemas/events/context-compacted-v1.json`.

### Workstream 3: Event Spine & A2A State
- Publish two new event types to Redis Streams:
  - `agent.decision.system1`: Audit log of all fast-path routing and safety evaluations.
  - `agent.context.compacted`: Authoritative event containing the unedited `note_to_self` and pre/post token counts.
- `self_compact` atomically updates `.agent/collaboration/RESUME.json` and appends a verified line to `PULSE.log`.

### Workstream 4: Active RAG & Memory Modernization
1. **RAG Micro-Reranking ([rag_augmentor.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/rag_augmentor.py)):**
   - Replace raw cosine similarity sort with a 20ms System 1 pass evaluating `noul: is_directly_relevant` and `noul: is_context_sufficient`.
2. **Memory Supersession ([memory_superseder.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_superseder.py)):**
   - Replace vector-blind `top_fact[0]` sort with semantic classification (`choice: relationship` $\in$ `{supersedes, complements, contradicts_unresolved, unrelated}`).
   - Gating Hot vs. Warm vs. Cold memory tier placement per Rule 10 Memory Discipline.

### Workstream 5: Canon & Agent Parity (Rule 18)
- Synchronize compaction templates and system prompts across all five agent instruction files (`CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `LOCAL-AGENT.md`, `WORKFLOW-CANON.md`) via the `canon/` compiler.

### Workstream 6: Observability & Dashboard Parity
- Add live tiles to `dashboard.html` / `dashboard.js`:
  - **System 1 Engine KPI:** Requests/sec, P95 latency (ms), and System 1-to-System 2 escalation percentage.
  - **Context Window Utilization Gauge:** Per-agent visual gauge color-coded by threshold (Green $\to$ Yellow $\to$ Red).

---

## 4. Phased Implementation Slices

| Slice | Focus | Deliverables | Verification Gate |
|---|---|---|---|
| **Slice 1** | System 1 Foundation | Nix module for `system1d`, socket listener, ONNX INT8 engine, `aq-qa` health check | `test-system1-socket.py` passes; RSS $\le 350\text{ MB}$; P95 latency $< 30\text{ ms}$. |
| **Slice 2** | Routing & Safety Wiring | Wire `system1d` into `task_classifier.py` and `aq-safe-gate` | Intent benchmark matches or exceeds regex accuracy; zero regression on whitelist. |
| **Slice 3** | Self-Compact Tool & Controller | `context_budget_controller.py` in switchboard + `self_compact` tool + atomic `RESUME.json` sync | Simulated 10-turn conversation triggers Warning and Force thresholds accurately. |
| **Slice 4** | RAG & Memory Modernization | Upgraded `rag_augmentor.py` and `memory_superseder.py` | RAG noise rejection verified; memory supersession unit test suite 100% pass. |
| **Slice 5** | Live Factory Stress Test & Dashboard | End-to-end multi-turn coding task with live dashboard metrics | Agent self-compacts 3 times without losing active goal or breaking code; DoD checklist signed. |

---

## 5. Non-Negotiable Acceptance Criteria (Definition of Done)
1. **Integrated:** Called directly from live request paths (`switchboard :8085` and `hybrid-coordinator :8003`).
2. **Turned ON:** Enabled by default in NixOS system service configuration.
3. **Real-World Validated:** A synthetic 50-turn agent task runs to completion with $\ge 2$ self-compactions and zero loss of state.
4. **Observable:** Telemetry visible on `dashboard.html` without `--` placeholders.
5. **Intervenable:** Operator can toggle System 1 bypass (`AQ_SYSTEM1_DISABLE=1`) or adjust thresholds via CLI/API.
6. **PM-Tracked:** Linked to `tracker.json` with mechanically projected progress.
