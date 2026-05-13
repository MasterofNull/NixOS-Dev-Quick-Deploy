You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy. Follow the canonical workflow from .agent/WORKFLOW-CANON.md.

## YOUR TASK: Phase 30 — Research & Gap Analysis (READ-ONLY — do NOT edit files)

Orient on Phase 30 "Local Agent Operational Introspection and CLI Execution" and produce a structured gap analysis.

### Step 1 — Read these files (use Read tool):
1. `.agents/plans/phase-30-local-agent-operational-introspection-and-cli-execution.md`
2. `nix/modules/services/switchboard.nix` — look for localAgentCard, local-agent profile
3. `scripts/ai/aq-qa` — look for any existing CLI execution checks
4. `scripts/ai/aq-context-bootstrap` — understand current context injection

### Step 2 — Answer these questions in your output:
1. What does the current `local-agent` switchboard profile card say about CLI execution? Does it explicitly allow `aq-qa`, `aq-hints`, `aq-memory`, `aq-context-bootstrap`?
2. Is there a sanctioned CLI surface policy anywhere in the codebase (grep for "sanctioned.*cli|allowed.*aq|cli.*surface")?
3. What specific changes does workstream 30.1 require to the switchboard profile card?
4. What is the smallest change that would close the 30.1 gap?

### Step 3 — Output format:
Produce a gap analysis as a markdown block with sections:
- Current State (what exists)
- Gap (what is missing)
- Proposed Change (specific file + content change)
- Acceptance Test (how to verify it is fixed)

Do NOT make any file changes. This is research-only. Output your findings to stdout.

Working directory: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
