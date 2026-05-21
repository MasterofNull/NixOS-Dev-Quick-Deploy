# PROJECT PRD — Command Center Dashboard Revamp (Phase 60)

## 1. Problem Statement
The current Command Center Dashboard (`dashboard.html`) suffers from extreme information redundancy and a haphazard layout. Multiple top-level strips (`health-score`, `kpi-ribbon`, `operator-strip`, `command-deck`) compete for attention with overlapping metrics. The hardware overview is too sparse for the space it consumes, and there is no unified mechanism for adjusting system variables (e.g., toggling acceleration modes or changing active model tiers) without deep-diving into individual scripts or Nix files.

## 2. Goals
- **Consolidate**: Merge redundant status indicators into a single, high-density "Unified Operations Glass" header.
- **Layered Architecture**: Align the primary navigation with the Phase 58 "Layered Health" (L1-L7) model.
- **Interactive Controls**: Introduce a "System Variable Control Panel" for real-time adjustment of runtime parameters.
- **Dense Visualization**: Maximize data-to-pixel ratio using sparklines, mini-gauges, and consolidated "Functional Unit" cards.
- **Maintain Aesthetic**: Keep the existing cyberpunk/sci-fi theme and color palette (Orbitron, JetBrains Mono, Cyan/Magenta accents).

## 3. Proposed Information Architecture

### 3.1. Unified Operations Glass (The Header)
- **Top Row**: System Title, Global Health Score (Large), Live Heartbeat, and Hostname.
- **Middle Row (KPI Ribbon)**: High-density scrolling strip for: Local AI %, Cache Hit Rate, Eval Score, Queue Depth, Thermal Status, and DB Connections.
- **Bottom Row (Layer Rail)**: Interactive L1-L7 status tiles. Clicking a tile scrolls to and highlights the relevant functional card.

### 3.2. Functional Unit Cards
Instead of generic "System Overview" blocks, group information by stack layer:
- **L0: Hardware & OS**: Compact CPU/GPU/Mem sparklines + NixOS version + Uptime.
- **L1: Persistence**: Qdrant/Postgres/Redis health + Vector count + Cache size.
- **L2: Inference**: Llama-cpp/Embed status + Active Model + VRAM pressure + Controls (Restart/Swap).
- **L3: Orchestration**: Hybrid Coordinator/Ralph status + Active Sessions + Workflow DAG.
- **L4: Connectivity**: Switchboard status + Routing Aliases + Network throughput.

### 3.3. System Variable Control Panel (New)
A slide-out drawer or dedicated card with interactive controls:
- **Acceleration Mode**: (Auto | CUDA | Vulkan | CPU) - Triggers `aq-model-switch`.
- **Inference Tier**: (Standard | Reasoning | Ultra) - Adjusts Switchboard profiles.
- **Safety Mode**: (Strict | Permissive | Audit) - Toggles security gate policy.
- **Memory Pressure**: Sliders for cache eviction thresholds.

## 4. Visual Enhancements
- **SVG Spark-ribbons**: Replace large charts with high-density inline sparklines for historical trends (24h).
- **Mini-Gauges**: Use circular/semi-circular SVG gauges for resource utilization (CPU/GPU/RAM).
- **Interactive Workflow DAG**: Integrate the Mermaid/D3 logic flow into the L3 functional card.
- **Dynamic Backgrounds**: Subtle "pulse" effects on cards based on real-time activity/pressure.

## 5. Success Criteria
- [ ] Top-level redundant strips are merged into a single `<header>` + `<nav>` structure.
- [ ] "System Overview" card is reduced in size by 50% while maintaining the same signal.
- [ ] At least 3 system variables (Acceleration, Tier, Safety) are controllable via the UI.
- [ ] Navigation via the L1-L7 Layer Rail is functional.
- [ ] No information is repeated more than twice across the entire view.

## 6. Execution Strategy
1.  **Phase 1: Component Refactor**: Break down `dashboard.html` into manageable templates (or use JS components) to handle the 18k lines of logic.
2.  **Phase 2: Header Consolidation**: Implement the "Unified Operations Glass".
3.  **Phase 3: Functional Card Redesign**: Rewrite the L0-L7 cards for high density.
4.  **Phase 4: Control Panel Implementation**: Connect the UI to the backend `/api/actions` and `/api/config` endpoints.
5.  **Phase 5: Visual Polish**: Implement SVG sparklines and mini-gauges.

## 7. Safety and Governance Constraints

Interactive controls must be treated as operator action proposals, not direct browser-to-host mutations.

- UI controls must call existing authenticated action endpoints or a future typed action-proposal endpoint; they must not shell out directly from frontend code.
- Every mutating control must show blast radius, target service/config surface, rollback path, and validation command before execution.
- Acceleration/model/tier changes must respect `config/runtime-safety-policy.json`, switchboard profile contracts, and model catalog trust metadata.
- Safety-mode changes require explicit confirmation and audit logging; the dashboard must never silently loosen policy.
- Destructive or externally visible actions remain approval-gated per `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`.
- All UI-rendered API payloads, graph labels, and model-provided summaries are untrusted and must be escaped/sanitized before rendering.

## 8. Revised Control-Panel Acceptance Criteria

- [ ] Each control maps to a typed action with declared risk class and required approval state.
- [ ] Read-only preview mode is available for every control before mutation.
- [ ] Mutating controls emit audit events with actor, action, resource, decision, policy ID, and trace ID.
- [ ] Controls degrade safely when the backend action endpoint, API key, or safety gate is unavailable.
- [ ] Tests cover at least one allowed read-only preview, one approval-required mutation, and one denied unsafe mutation.
