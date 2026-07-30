VERDICT: PASS

# Foundation C — C3b R4 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Opus (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C3B-R4-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C3b Stage R4 design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings & Constraints

- **Strict Perf Protocol compliance (R0 §8):** RESOLVED (§4). The measurement protocol is highly robust. Evicting the cache with `posix_fadvise(POSIX_FADV_DONTNEED)` and validating residency via `mincore` ensures cold cohorts are genuinely cold. Timing via `CLOCK_MONOTONIC_RAW` avoids NTP skew. p95 calculation is correctly pinned to nearest-rank rather than interpolated averages.
- **Revocation-Under-Load stressing (§5):** RESOLVED. The test actively targets the concurrent limit (1 or 2 active cells) rather than single idle runs, asserting zero post-revocation green states, clean tree termination, and that the runner remains responsive post-revocation.
- **Scope Integrity:** RESOLVED (§2, §6). R4 is entirely non-enforcement. It consists of offline performance harness code (`execution-cell-perf-harness.py`), report schemas, and a fast-executing self-test for CI validation. It modifies no runner or switchboard runtime paths.

---

## 2. Six Review Obligations Verification (§8)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Budget Hardness (§3)** | **CLOSED** | All latency, memory, and concurrency metrics are strict gates. Failure to meet any budget blocks progression. |
| **2. Protocol Fidelity (§4)** | **CLOSED** | Uses N>=40 cohorts, fadvise/mincore cache checks, raw monotonic timing, nearest-rank p95, and cgroup memory limits. |
| **3. Concurrent Revocation (§5)** | **CLOSED** | Mass teardown is tested under load at the concurrency cap, ensuring zero leaks or wedged states. |
| **4. Non-enforcement (§2, §6)** | **CLOSED** | Wires no live code, modifies no enforcement semantics, and activates no cells. |
| **5. Evidence Immutability (§4, §6)** | **CLOSED** | Outputs a structured, signed JSONL report containing host fingerprint, kernel, and build revision data. No sample is discarded. |
| **6. Harness Self-Test (§6)** | **CLOSED** | Features a separate, rapid offline test harness to validate the correctness of the measurement code in CI. |

---

## 3. Position on Execution Architecture

We confirm the separation of the **real acceptance run** (as an operator/deployment step targeting the actual APU environment) from the **CI self-test harness** (running mock fixtures with small N). This keeps CI runtime fast while ensuring empirical limits are verified in the target host environment before R5/R6 promotion.
