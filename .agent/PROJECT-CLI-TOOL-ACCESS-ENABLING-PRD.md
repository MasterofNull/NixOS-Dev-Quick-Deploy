# PROJECT-CLI-TOOL-ACCESS-ENABLING-PRD.md

## Problem
AI agents in the NixOS-Dev-Quick-Deploy harness are currently restricted from using powerful CLI tools like `aq-prime`, `agrep`, `als`, and others. This restriction is enforced by:
1. Explicit "NEVER call aq-prime" rules in the Continue extension configuration (`nix/home/base.nix`).
2. Labeling `aq-prime` as "human-run, not AI tool calls" in `AGENTS.md`.
3. General confusion in agent instructions regarding the availability of CLI vs MCP tools.

## Goal
Enable agents to use the full suite of system and agentic CLI tools (`aq-*`, `agrep`, `als`, `acat`, `asum`, etc.) via their shell/terminal tool calls, while still maintaining a preference for MCP tools when equivalent functionality exists.

## Scope
- Update `AGENTS.md` to remove human-only labels for CLI tools.
- Update `.agent/GEMINI.md` and `.agent/WORKFLOW-CANON.md` to clarify tool availability.
- Update `nix/home/base.nix` to allow `aq-prime` and other CLI tools in agent rules.
- Ensure consistency across all instruction sets.

## Constraints
- Must maintain security (no hardcoded secrets, etc.).
- Must not break the "Harness-First" or "Workflow-First" principles.
- Must remain compatible with NixOS declarative configuration.

## Acceptance Criteria
- Agents no longer claim they "cannot run aq-prime or other CLI tools".
- `AGENTS.md` reflects that CLI tools are for both humans and agents.
- `nix/home/base.nix` rules are updated and "NEVER call aq-prime" is removed.
- `aq-prime` orientation can be performed by the agent.

## Security Requirements
- Ensure `run_shell_command` usage follows existing safety guidelines (quoting, sanitization).
- No sensitive information is exposed during tool calls.
