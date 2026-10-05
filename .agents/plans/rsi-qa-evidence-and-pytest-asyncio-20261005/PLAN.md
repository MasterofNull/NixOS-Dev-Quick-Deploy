# RSI Plan: QA Evidence Systemd Mount Compatibility & Pytest-Asyncio Toolchain

Date: 2026-10-05
Author: Antigravity (Orchestrator) & Codex (Implementer)
Scope: Resolve recurring attention alert and missing pytest-asyncio plugin

## Objectives
1. **Slice D — Fix `qa_evidence_store` Systemd Mount Classification**:
   - In `scripts/ai/lib/qa_evidence_store.py`, `_assert_real_directory` failed on `ROOT_MOUNT_TARGET: /var/lib/ai-stack/hybrid/telemetry` when running inside systemd services with `ProtectSystem = "strict"` and `ReadWritePaths = [ ... "/var/lib/ai-stack/hybrid/telemetry" ]` (specifically `ai-stack-health-monitor.service`).
   - Systemd creates a namespace self-bind mount (`root_within_fs == mount_point` on the same physical filesystem) to permit writing under `ProtectSystem=strict`.
   - Update `mount_targets` in `qa_evidence_store.py` to identify redirected and pseudo-filesystem mount targets (tmpfs, ramfs, overlay, cross-directory binds) while accepting self-bind mounts of the exact canonical directory on durable block storage.
   - Add regression tests in `scripts/testing/test-telemetry-root-boundary.py`.
   - Clear recurring attention alert `attn-14dd7fb8` in `.agents/attention/ATTENTION.json`.

2. **Slice E — Declare `pytest-asyncio` in Developer Toolchain**:
   - `pytest.ini` configures `asyncio_mode = auto` and `asyncio_default_fixture_loop_scope = function`.
   - `nix/home/base.nix` included `pytest-cov` and `pytest-xdist` but omitted `pytest-asyncio`, generating `PytestConfigWarning: Unknown config option: asyncio_mode` on every test run.
   - Add `ps."pytest-asyncio"` to `nix/home/base.nix` and verify with `pytest`.
