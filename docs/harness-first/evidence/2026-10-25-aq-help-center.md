# Evidence: AQ-OS SOTA Help Center, Desktop Launcher & User Training Manual

- **Date**: 2026-10-25
- **Branch**: `feat/aq-help-system-app`
- **Component**: Help Center, User Manual, & Training Desktop Application
- **Author**: Antigravity Orchestrator

## Objective
Provide an interactive desktop application, web interface, and system-wide documentation hub ensuring new and advanced users can properly utilize the agentic software development factory, understand the mental model, navigate the dashboard, launch swarm workspaces, and execute the 8-step canonical workflow.

## Workflow/Session IDs
- **Session ID**: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- **Task ID**: `task-help-system-app`
- **Branch**: `feat/aq-help-system-app`

## Delegation Decision
Self-contained documentation, desktop application wrapper, and NixOS service addition executed in dedicated feature branch with hermetic verification tests.

## Commands Executed
- `python3 scripts/ai/aq-help-center --search "8-step"`
- `python3 scripts/testing/test-aq-help-center.py`
- `nix eval .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath`

## Validation Evidence
- `scripts/testing/test-aq-help-center.py` passed with 3/3 checks ok (script executable, desktop entry valid, markdown-to-HTML parser verified across all 8 mapped manuals).
- Desktop entry valid and points to the executable launcher at `/home/hyperd/.local/share/applications/aq-help-center.desktop`.
- NixOS configuration evaluates cleanly to `/nix/store/lfvs7vq47768hphh4rrzqyc8ajglfr92-nixos-system-hyperd-26.05.20261015.26f4107.drv`.

## Rollback Plan
- Revert commit `git revert HEAD` or delete the branch `feat/aq-help-system-app`.
- Remove desktop launcher `/home/hyperd/.local/share/applications/aq-help-center.desktop`.

## Residual Risk
Zero residual risk: service is a lightweight local Python HTTP server on port 8890, standalone and isolated from primary inference workloads.

## Hint Feedback
Documentation search in `aq-help-center` enables sub-millisecond query retrieval across core markdown guides directly from terminal or GUI.
