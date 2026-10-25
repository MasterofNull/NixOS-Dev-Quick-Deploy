# PRD: AI Command Center Dashboard Revamp & SOTA Observability Cockpit

- **ID**: `PROJECT-DASHBOARD-COCKPIT-REVAMP`
- **Owner**: hyperd (System Owner)
- **Status**: Active / In-Development
- **Date**: 2026-10-25
- **References**:
  - Impeccable Design Intelligence (`.agent/skills/impeccable/SKILL.md`)
  - Durable Agents SOTA UI PRD (`.agent/PROJECT-DURABLE-AGENTS-SOTA-UI-PRD.md`)
  - Dashboard Route Catalog (`dashboard/backend/api/routes/aistack.py`)
  - Service Coverage Contract (`.agent/WORKFLOW-CANON.md`)

---

## 1. Executive Summary

The AI Command Center Dashboard (`dashboard.html` / `http://127.0.0.1:8889`) provides operator visibility and control over local models, hybrid coordinator, AIDB, memory broker, on-call daemons, and multi-agent execution lanes.

Recent system upgrades surfaced:
1. Python 3.13 dynamic import regressions in `dashboard/backend/api/routes/aistack.py` (missing `sys.modules` registration during dynamic module loading breaking `/aistack/advanced/runtime-summary`).
2. Legacy stale cards and missing live streams for frontier capabilities (Thought Stream, Human Intervention Dock, Durable Effect Sandwiches, SOTA Sweeper).
3. The need for an updated, intuitive operator UI matching top frontier lab standards (Cursor, Windsurf, Claude Artifacts).

---

## 2. Requirements & Work Slices

### Slice 1: Backend Route Resiliency & Dynamic Import Parity (CRITICAL)
- Fix all dynamic `spec.loader.exec_module` invocations in `aistack.py` to register into `sys.modules[spec.name]`.
- Restore 100% PASS across all 97 monitored dashboard endpoints in `scripts/testing/verify-dashboard-apis.py`.

### Slice 2: Live Cockpit Cards & Broken Display Cleanup
- Remove deprecated/stubbed displays and replace with live telemetry:
  - **Thought Stream Card**: Real-time agent intent and tool invocation metrics.
  - **Intervention Dock**: One-click operator steering controls.
  - **Durable Mesh & Triage Monitor**: Displaying P95 triage latency (<200ms) and active Effect Sandwich reconciliation states.
  - **SOTA Sweeper Intelligence Feed**: Displaying classified incoming signals (Hype vs. Fact vs. Signal).

### Slice 3: Impeccable UI Styling & Error Recovery
- Apply OKLCH color palettes, smooth responsive glassmorphism, and clear status indicators per `.agent/skills/impeccable/SKILL.md`.
- Graceful degradation: If a service is offline, render structured fallback badges rather than uncaught JS console errors or blank cards.
