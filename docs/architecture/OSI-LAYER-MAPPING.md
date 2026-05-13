# AI Harness OSI Layer Mapping

This document maps the repository's directory structure and core libraries to the 7-Layer AI Harness Stack established in **ADR-007**.

## Layer 1: Infrastructure (Physical/Declarative)
- **Path**: `nix/`, `templates/`, `phases/`
- **Libraries**: `lib/l1-infra/dry-run.sh`
- **Ownership**: `nixos-systems-architect`
- **Scope**: System configuration, hardware tuning, flake inputs.

## Layer 2: Runtime (Execution)
- **Path**: `ai-stack/compose/`, `lib/l2-runtime/tools.sh`
- **Libraries**: `lib/flatpak.sh`
- **Scope**: Container lifecycle, Podman/KVM isolation, resource constraints.

## Layer 3: Connectivity (Network/Service)
- **Path**: `scripts/ai/mcp-bridge-hybrid.py`
- **Scope**: MCP bridges, service discovery, port registry, internal networking.

## Layer 4: Coordination (Transport/Routing)
- **Path**: `ai-stack/mcp-servers/hybrid-coordinator/`, `ai-stack/mcp-servers/ralph-wiggum/`
- **Libraries**: `lib/l4-coord/ai-optimizer.sh` (Routing components)
- **Ownership**: `codex-validator` (Orchestrator)
- **Scope**: Agent delegation, routing logic, intent normalization.

## Layer 5: Session & Persistence (State)
- **Path**: `ai-stack/database/`, `ai-stack/postgres/`, `scripts/data/`
- **Scope**: AIDB temporal facts (Layer 5), interaction history, telemetry storage.

## Layer 6: Cognitive/Semantic (Presentation/Context)
- **Path**: `ai-stack/aidb/`, `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`
- **Libraries**: `lib/ai-optimizer-hooks.sh`
- **Scope**: RAG pipeline, context synthesis, prompt presentation, hint injection.

## Layer 7: Interaction (Application/UX)
- **Path**: `scripts/ai/aq-*`, `dashboard/`
- **Libraries**: `lib/l7-interaction/progress.sh`, `lib/l7-interaction/logging.sh`
- **Scope**: User CLI tools, operator dashboard, agent personas.

---

## 📉 Causality Rules (Operational Logic)
1. **Downward Dependency**: A failure in Layer $N$ invalidates all layers $> N$. (e.g., if L2 Runtime is down, L4 Coordination is inherently offline).
2. **Upward Context**: Data flows upward for synthesis. Raw logs (L2) become semantic facts (L5) which become agent hints (L6).
3. **Validation Isolation**: Health checks for Layer $N$ should only verify $N$ and its direct dependencies ($N-1$) to ensure precise root-cause discovery.
4. **Recovery Priority**: System recovery must proceed from L1 to L7. Do not attempt to fix the Dashboard (L7) until the Database (L5) is stable.

## 📋 Integration Requirements
- All new `lib/` files **MUST** be placed in the appropriate tier directory.
- All `aq-*` CLI tools **MUST** report which layer they are operating on in their `--help` or verbose output.

---

## Domain Cross-Cutting
The following libraries provide utility across multiple layers:
- `lib/cross-cutting/error-handling.sh`
- `lib/cross-cutting/common.sh`
- `lib/cross-cutting/logging.sh` (Shared interface)

## Next Steps
- Enforce layer boundaries in `scripts/governance/repo-structure-lint.sh`.
- Update `aq-prime` logic to display layer context based on the task type.
