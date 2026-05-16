# PROJECT-ACCELERATE-PRD — Phase B: ACCELERATE
**Objective**: High-performance inference and robust multi-agent orchestration.
**Status**: DRAFT | **Owner**: Claude (Strategist & Lead Architect)

---

## 1. Problem Statement
Phase A (Hardening) established a stable foundation for the AI stack. However, the current system faces performance bottlenecks on AMD hardware due to Vulkan translation layers, lacks a standardized durable execution model for long-running agentic workflows, and requires more robust workspace isolation for high-concurrency operations. To transition from a stable harness to a high-performance production-ready environment, we must optimize the hardware path and formalize the orchestration layer.

## 2. Strategic Goals
- **Performance**: Achieve native ROCm performance on AMD GPUs, bypassing Vulkan overhead.
- **Concurrency**: Enable safe, parallel execution of multiple agents via isolated git-based worktrees.
- **Durability**: Provide a reliable mechanism for agents to checkpoint, pause, and resume complex multi-step tasks.

## 3. Technical Requirements

### 3.1 Hardware Acceleration (GPU)
- **Native ROCm Integration**: Transition from Vulkan translation to native ROCm via `nixos-rocm` and `nixified-ai` flakes.
- **Flake-level Optimization**: Update `nix/modules/roles/ai-stack.nix` to support `nixified-ai` overlays for `llama-cpp`.
- **Hardware Profiles**: Extend `config/ai-stack-hardware-profiles.json` to include native ROCm specific tunables.

### 3.2 Workspace & Concurrency
- **Git Worktree Isolation**: Standardize on `GIT_WORKTREE` for concurrent agent execution.
- **Persistent Provisioning**: Move worktrees from `/tmp` to persistent storage at `/var/lib/nixos-ai-stack/worktrees/`.
- **Conflict Management**: Implement automated conflict detection and resolution strategies in `WorkspaceManager`.

### 3.3 Workflow DSL (Orchestration)
- **DSL Specification**: Define a YAML-based DSL inspired by LangGraph for durable agent execution.
- **State Management**: Implementation of a 'Checkpoint & Resume' system that persists agent state to AIDB/Postgres.
- **Graph Execution Engine**: A lightweight engine capable of executing DAGs and cyclic graphs with error recovery.

## 4. Security Requirements
- **Worktree Isolation**: Ensure worktrees are strictly isolated and do not expose parent `.git` configuration or secrets.
- **Resource Limits**: Implement cgroup-based resource capping for parallel agent workspaces.
- **Inference Sandbox**: Maintain and extend AppArmor confinement for native ROCm inference.

## 5. Acceptance Criteria
- [ ] **ROCm Performance**: Benchmarks show ≥15% improvement in token throughput vs Vulkan on same hardware.
- [ ] **Concurrency**: Successfully run 5 parallel agents on separate worktrees without file conflicts.
- [ ] **Durability**: An agent task can be manually killed and resumed from the last successful checkpoint without loss of state.
- [ ] **DSL Validation**: DSL schema is strictly validated, and a complex 3-step workflow is successfully executed.

## 6. Slices (Implementation Overview)
1. **Slice 1: Flake Integration** - Add `nixified-ai` and `nixos-rocm` to `flake.nix`.
2. **Slice 2: ROCm Native Support** - Update `ai-stack.nix` for native ROCm acceleration.
3. **Slice 3: Workspace Provisioning** - Move worktrees to `/var/lib/nixos-ai-stack/worktrees/`.
4. **Slice 4: Workflow DSL Spec** - Define YAML schema and validator.
5. **Slice 5: Checkpoint & Resume** - Implement state persistence layer.
6. **Slice 6: Graph Engine v1** - Deliver the execution engine and first durable workflow.
