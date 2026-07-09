# Antigravity — Plan-Consensus: Phase-0 Keystone (`zero_trust` flag)

## 1. VERDICT
**APPROVE-WITH-CHANGES** — The design handles the monotonic rise-only state-machine correctly, but we require strict fail-closed overrides and explicit schema validation rules before the keystone is integrated.

## 2. Implementable as written?
Yes, the plan is implementable as written, with the following modifications:
- **C1 — Schema Validation Isolation**: The `derive_zero_trust(messages)` hook must validate tool schema integrity *prior* to parsing tool calls to prevent malformed/injected schemas from bypassing the zero-trust evaluation.
- **C2 — Sticky Latching Boundary**: The monotonic rise-only logic `zt = task_sticky OR scan(current_messages)` must be scoped exclusively to the request-response thread of a single task run, ensuring that session context changes do not leak state between unrelated parallel tasks.
- **C3 — Fail-Closed Validation**: Collapse all exception handling within the helper to a default value of `zero_trust = true` to protect against runtime scanning failures.

## 3. Risks
- **Regex Latency Overhead**: Message scanning on very large contexts (such as raw log dumps or deep AST diffs) could introduce noticeable latency spikes. The regex patterns in `a2a_guard` must be optimized and pre-compiled.
- **Unintended Local Downgrades**: Forced-remote calls that get downgraded to local Qwen when `zero_trust` is active might fail on complex reasoning tasks, which will require the caller to handle failures cleanly rather than crashing.

## 4. Test Adequacy
The proposed 14 tests are highly comprehensive. We recommend explicitly adding a test case validating **parallel race-isolation**: executing a clean request and a secret-bearing request concurrently to prove that `zero_trust` is evaluated per-request and does not leak context between worker threads.
