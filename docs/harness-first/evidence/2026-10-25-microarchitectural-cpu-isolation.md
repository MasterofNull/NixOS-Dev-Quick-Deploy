# Harness-First Evidence: Microarchitectural CPU Cache Timing Isolation

**Date**: 2026-10-25
**Scope**: CPU Cache Timing Covert-Channel Mitigation Framework
**Reference**: Google Red Team Side-Channel Defense Framework & OWASP LLM08

## 1. Context & Threat Modeling
To prevent untrusted multi-agent code execution from communicating covertly via microarchitectural CPU cache latency (shared L2/L3 slices, SMT execution units), this framework provides physical core pinning, CFS scheduler stripping, and ephemeral cgroup scrubbing.

## 2. Implemented Components
1. `nix/modules/core/microarchitectural-isolation.nix`: Declarative NixOS module implementing `nosmt`, `isolcpus`, `nohz_full`, `rcu_nocbs`, `irqaffinity`, and libvirt cgroup controllers.
2. `config/libvirt/untrusted-agent-microvm.xml`: Reference XML tuning specification binding guest virtual CPUs statically to physical host cores 4-7.
3. `scripts/ai/orchestrate-sandbox.sh`: Shell automation lifecycle engine verifying kernel parameters, running bounded ephemeral containers, and executing teardown cache flushes.
4. `scripts/ai/agent_driver.py`: Python driver wrapper enforcing fail-closed invariant checks.
5. `scripts/testing/test-microarchitectural-isolation.py`: Regression test suite asserting contract validity.
6. `docs/operations/AQ-MICROARCHITECTURAL-ISOLATION-GUIDE.md`: Operational operator manual.

## 3. Verification & Results
- Unit test pass: `python3 scripts/testing/test-microarchitectural-isolation.py` -> 5/5 PASS.
- Pre-commit gate: `scripts/governance/tier0-validation-gate.sh --pre-commit` -> verified.
