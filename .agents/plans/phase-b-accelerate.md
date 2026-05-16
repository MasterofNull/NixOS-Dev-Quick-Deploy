# Implementation Plan: Phase B (ACCELERATE)
**Objective**: Transition to native ROCm, isolated worktrees, and durable DSL-based workflows.
**Owner**: Claude | **Duration**: 3 Weeks

---

## 1. Scope Lock
- **IN SCOPE**: ROCm integration, Git worktree isolation improvements, Workflow DSL, Checkpoint/Resume logic.
- **OUT OF SCOPE**: Multi-node orchestration, Hardware other than AMD/NVIDIA, UI/UX changes for the dashboard.

## 2. Workstreams

### WS1: GPU Acceleration & Performance (Week 1)
Focus on native ROCm support and `nixified-ai` integration.
- Integration of `nixos-rocm` and `nixified-ai`.
- Optimization of `llama-cpp` build flags.

### WS2: Orchestration & Isolation (Week 2)
Focus on `WorkspaceManager` and worktree persistence.
- Provisioning worktrees in `/var/lib/nixos-ai-stack/worktrees/`.
- Conflict detection and resolution logic.

### WS3: Workflow DSL & Durability (Week 3)
Focus on the LangGraph-inspired DSL and durability.
- DSL Specification and validation.
- Checkpoint & Resume implementation.
- Graph Execution Engine.

---

## 3. Actionable Slices

### Slice 1: Flake Integration
- **Goal**: Add high-performance AI flakes to the system.
- **Files**: `flake.nix`
- **Validation**: `nix flake check`

### Slice 2: ROCm Native Support
- **Goal**: Enable native ROCm acceleration in `ai-stack.nix`.
- **Files**: `nix/modules/roles/ai-stack.nix`, `config/ai-stack-hardware-profiles.json`
- **Validation**: `systemctl restart llama-cpp && journalctl -u llama-cpp | grep "ROCm"`

### Slice 3: Workspace Provisioning
- **Goal**: Move worktrees to persistent storage and update manager.
- **Files**: `ai-stack/orchestration/workspace_isolation.py`, `nix/modules/roles/ai-stack.nix` (tmpfiles)
- **Validation**: `python3 -m pytest tests/unit/test_workspace_isolation.py`

### Slice 4: DSL Specification & Schema
- **Goal**: Define the YAML-based workflow DSL.
- **Files**: `ai-stack/orchestration/workflow_dsl.py`, `config/schemas/workflow-dsl.schema.json`
- **Validation**: `aq-workflow validate examples/standard-task.yaml`

### Slice 5: Checkpoint & Resume (State Layer)
- **Goal**: Implement durability for long-running tasks.
- **Files**: `ai-stack/orchestration/state_manager.py`, `ai-stack/database/migrations/003_workflow_state.sql`
- **Validation**: `python3 -m pytest tests/integration/test_durability.py`

### Slice 6: Graph Execution Engine v1
- **Goal**: Execute multi-step agent graphs with error recovery.
- **Files**: `ai-stack/orchestration/graph_engine.py`, `scripts/ai/aq-workflow`
- **Validation**: `aq-workflow run examples/multi-step-research.yaml`

---

## 4. Rollback Plan
- **GPU**: Revert `flake.nix` and `ai-stack.nix` to use Vulkan.
- **Workspaces**: Revert `WorkspaceManager` to use `/tmp` and clean up `/var/lib/nixos-ai-stack/worktrees/`.
- **DSL**: Keep legacy `workflow_isolation.py` functional while iterating on DSL.
