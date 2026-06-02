# Slice 93.15: Agent Observability Dashboard UI

Status: Active
Owner: Gemini Code Assist (Orchestrator)
Last Updated: 2026-06-01
Supersedes: none

## 1. Objective
Finish the frontend implementation of the Agent Observability dashboard panel. The HTML cards exist in `dashboard.html` but require the JavaScript fetching and rendering logic to display the telemetry generated in Phase 93 (useful tokens, effectiveness scorecard, swimlanes, and race comparisons).

## 2. Scope Lock
- **In scope**: Modifying `assets/dashboard.js` (or equivalent frontend asset) to implement `loadAgentReplay()`, `sendControl()`, and the auto-refresh polling for the `#panel-observe` cards.
- **Out of scope**: Backend API modifications (already complete). Modifying the existing HTML structure heavily (it is already well-scaffolded).
- **Constraints**: UI elements must handle `no_data` gracefully without throwing console errors. D3/Mermaid must be utilized where appropriate for timelines and graphs.

## 3. Active Authority Links
- `.agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md` (Phase 93 PRD)
- `dashboard.html` (DOM targets)

## 4. Steps
1. **Read-Before-Edit**: Extract the current contents of the JS asset responsible for the dashboard frontend (`assets/dashboard.js`).
2. **Implement Fetch Logic**: Map the backend endpoints (`/api/aistack/effectiveness/scorecard`, `/api/aistack/agent-runs/race`, `/api/aistack/agent-runs/swimlane`, `/api/aistack/agent-runs/{id}`) to DOM updater functions.
3. **Implement Visualization**: Use D3 (already loaded in `dashboard.html`) to render the swimlane and race comparison timelines.
4. **Wire Human Controls**: Ensure `sendControl()` issues the correct POST requests to `/api/aistack/agent-runs/{id}/control`.

## 5. Validation Commands
```bash
grep "loadAgentReplay" assets/dashboard.js
scripts/testing/run-focused-ci-checks.sh --target dashboard
```

## 6. Rollback Notes
Revert `assets/dashboard.js` to previous commit.
