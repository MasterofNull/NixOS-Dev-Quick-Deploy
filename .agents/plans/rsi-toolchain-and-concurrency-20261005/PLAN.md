# RSI Plan: Baseline Toolchain Observability (psmisc) & Collab Pulse Staging Hardening

**Date**: 2026-10-05
**Orchestrator**: Antigravity
**Linage**: RSI Backlog / System Tooling Availability

## Objectives

1. **Toolchain Observability (`psmisc`)**:
   - Provide `pstree`, `fuser`, and `killall` on system/agent PATH by adding `pkgs.psmisc` to `baselinePackages` in `nix/modules/roles/agentic-toolchain.nix` and `basePackageNames` in `nix/modules/core/base.nix`.
   - Prevent agent friction when process inspection (`pstree`) or process termination (`killall`) is invoked in shell tools.
   - Register and close `WR-TOOLCHAIN-PSMISC-MISSING` in `.agent/WORKAROUND-REGISTER.md` and `.agent/memory/issues-backlog.md`.
   - Add regression tests in `scripts/testing/test-agentic-toolchain-baseline.py`.

2. **Concurrent Pulse & Staging Race Hardening (`WR-COLLAB-PULSE-TEMP-CONTENTION`)**:
   - Replace deterministic `.tmp` filenames in `scripts/ai/lib/resume_projector.py` and `scripts/ai/lib/span_projector.py` with unique secret/PID tokens (`.{name}.{pid}.{secret}.tmp`).
   - Eliminate `os.replace` race conditions and clobbering when concurrent agents emit events via `aq-event pulse` and `aq-event resume`.
   - Add concurrency test in `scripts/testing/test-event-bus-a2a.py`.
   - Mark `WR-COLLAB-PULSE-TEMP-CONTENTION` as FIXED in `.agent/WORKAROUND-REGISTER.md`.

## Decomposition & Slices

- **Slice A (Concurrency Hardening)**:
  - Edit `scripts/ai/lib/resume_projector.py`: `_atomic_write` uses unique filename in same parent directory.
  - Edit `scripts/ai/lib/span_projector.py`: `_atomic_write` uses unique filename in same parent directory.
  - Add concurrent write stress test in `scripts/testing/test-event-bus-a2a.py`.
  - Validate: `python3 scripts/testing/test-event-bus-a2a.py`.

- **Slice B (Toolchain psmisc Declarations)**:
  - Edit `nix/modules/roles/agentic-toolchain.nix`: Add `psmisc` to `baselinePackages`.
  - Edit `nix/modules/core/base.nix`: Add `"psmisc"` to `basePackageNames`.
  - Add `scripts/testing/test-agentic-toolchain-baseline.py` asserting `psmisc` is declared in both modules.
  - Validate: run tests and `scripts/governance/quick-deploy-lint.sh --mode fast`.

## Definition of Done (Rule 15)
- All unit/regression tests passing.
- 54/54 Tier-0 validation gates clean.
- Workaround register updated with root cause and fix evidence.
- Atomic commit with truthful trailers.
