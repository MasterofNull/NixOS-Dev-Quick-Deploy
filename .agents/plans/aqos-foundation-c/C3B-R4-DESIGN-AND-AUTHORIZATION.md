---
title: "Foundation C C3b R4: Revocation-under-load + Measured APU Performance Gate — Design Packet"
slice: "C3b / R4"
status: "R4_REVIEWED_PASS"
review: "antigravity/gemini (independent, codex-substitution) PASS — 6/6 obligations CLOSED, no findings. Non-enforcement measurement gate. NOTE: light-model PASS — codex confirmatory (Aug-4) is the depth backstop."
revision: 1
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE (non-enforcement: measurement/validation harness — standing-auth class)"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R3 runner built + committed (ccbc0718), flag+enable OFF"
  - "R1 grant (f3a39f52), R2 clone (582113af)"
successors:
  - "C3b R5 default-OFF switchboard adapter (gated on R4 budgets met)"
---

# Foundation C — C3b R4: Revocation-under-load + Measured APU Performance Gate

## 0. Provenance & authority
Authored by Opus (codex-substitution; codex usage-limited to 2026-08-04, confirmatory queued).
Independent review → antigravity/gemini + codex-on-return. **DESIGN-ONLY.** R4 is
**NON-ENFORCEMENT**: it neither wires the runner into any live path nor turns anything on. It is a
**measurement + validation** slice that exercises the already-built, still-dormant R3 runner
(`ccbc0718`, flag+enable OFF) under a frozen protocol and emits a pass/fail acceptance verdict. R4
therefore is standing-auth class (like C0/C1/tests) — no single-use owner activation needed to
BUILD the harness; but its **result gates R5/R6** (a failing budget blocks activation).

## 1. Scope (R0 §5 R4 row — bounded)
Deliver: (a) a **runnable, reproducible APU performance harness** that measures the R3 runner's
cell lifecycle against the R0 §8 numeric budgets under the frozen protocol, emitting immutable
evidence + a typed acceptance verdict; and (b) **revocation-under-load validation** — prove the
epoch-bump→cgroup-whole-tree-kill→prove-absence path holds within budget while cells run
concurrently at the configured cap. **Out of scope:** any activation, flag/enable flip, switchboard
adoption (R5), network (C4), auto-merge, and any change to the R3 runner's enforcement code (R4
measures it; if a measurement reveals a real defect, that is a bounded R3 follow-up, not an R4 edit).

## 2. Why R4 is a gate, not new enforcement
R3 already ships the epoch watcher + cgroup kill + final fence (built + reviewed in `ccbc0718`).
R4 does not re-implement them; it **proves** they meet budget under realistic APU load, and it
pins the numbers so R5/R6 cannot be activated on an unmeasured or over-budget runner. "You cannot
manage what you cannot measure" — R4 is the measurement.

## 3. Frozen numeric budgets (from R0 §8 — the acceptance ceiling)
Measured at the configured concurrency cap (default 1; max 2). A miss BLOCKS R5/R6 — it may not be
explained away in prose (Rule: budgets are hard facts, not narrative).

| Metric | Acceptance limit |
|---|---:|
| p95 self-contained clone/snapshot latency | ≤ 3.0 s |
| p95 runner→bwrap spawn latency (after clone) | ≤ 250 ms |
| peak incremental RSS per running cell | ≤ 768 MiB |
| p95 teardown/revocation from observed epoch bump | ≤ 5.0 s |
| default concurrent cells | 1 |
| max configurable concurrent cells before new review | 2 |
| unaccounted process / untyped terminal receipt | 0 |

## 4. Frozen measurement protocol (R0 §8, made executable)
- **Command classes:** `noop`, `read-validate`, `single-file-write-validate` (matching R3's
  bounded descriptor vocabulary).
- **Cohorts:** cold-cache and warm-cache. **N ≥ 40 successful samples / cohort / command class**
  after 5 discarded setup iterations.
- **Cache validity:** cold — the dedicated trusted test-object source is evicted with
  `posix_fadvise(POSIX_FADV_DONTNEED)` and `mincore` confirms ≤ 5 % resident before each sample;
  warm — ≥ 95 % resident after an untimed priming run. A cohort that cannot prove its cache bound
  is INVALID (not silently accepted).
- **Host bounds:** no other cell runs; CPU governor + kernel/build revision recorded; zero swap
  activity during a sample; `MemAvailable` ≥ 8 GiB (a 6–8 GiB pressure cohort MAY be reported but
  cannot replace the acceptance cohorts).
- **Timing:** `CLOCK_MONOTONIC_RAW` where available, at runner receipt boundaries. p95 =
  nearest-rank `sorted[ceil(0.95*N)-1]` (no averaging of percentiles).
- **Memory:** max of cgroup-v2 `memory.current` over the cell lifetime minus the measured
  idle-runner baseline; `memory.peak` recorded when available.
- **Evidence:** immutable JSONL, one row per sample, schema
  `{schema_version, run_id, host_fingerprint, kernel, build_revision, command_class, cache_cohort,
  cache_residency_pct, sample_index, monotonic_start_ns, clone_done_ns, bwrap_started_ns,
  process_terminal_ns, tree_absent_ns, validation_done_ns, receipt_published_ns, cgroup_peak_bytes,
  idle_baseline_bytes, mem_available_bytes, swap_delta_bytes, outcome, denial_code}` + a content
  digest. **No failed/denied sample is discarded** — recorded and counted against the
  zero-untyped-outcome gate. No hidden pool/reuse or `git stash` fallback may be used to meet a limit.

## 5. Revocation-under-load validation
At the configured cap, with cells actively running the command classes: bump the authoritative
epoch (`config/capability-lease-epoch` via `resolve_current_epoch`) and measure epoch-bump →
tree-absent → typed rollback/quarantine receipt. Assert: (a) every affected cell is torn down
within the ≤ 5.0 s p95 budget; (b) zero cells publish GREEN after the bump (final-fence holds under
load); (c) zero unaccounted processes / untyped terminal receipts; (d) the runner remains
responsive to new deny-closed requests after mass teardown (no wedged state).

## 6. Harness surface (the R4 build — non-enforcement)
- NEW `scripts/testing/perf/execution-cell-perf-harness.py` — drives the R3 runner over a real UDS
  + throwaway bare mirror, runs the §4 protocol, writes the immutable JSONL, computes nearest-rank
  p95 / peak RSS, and emits a typed acceptance verdict {PASS, FAIL(metric, measured, limit),
  INVALID(cohort)}. Offline; consumes the R3 runner + R1/R2 as-is.
- NEW `scripts/testing/perf/execution-cell-perf-report.schema.json` — the evidence + verdict schema.
- NEW `scripts/testing/test-execution-cell-perf-harness.py` — a FAST self-test (tiny N, relaxed
  limits) proving the harness's own correctness offline in CI (nearest-rank math, cache-validity
  gating, zero-untyped-outcome gate, invalid-cohort rejection) — NOT the real acceptance run.
- The **real acceptance run** (full N≥40, on the actual APU, recording the host fingerprint) is an
  operator step whose evidence + verdict are committed as a dated report; it is not a CI unit.
The harness may NOT modify the R3 runner, R1/R2, or any enforcement code.

## 7. Acceptance bar (of R4 itself)
- The harness self-test passes offline (nearest-rank p95, cache-validity gating, invalid-cohort
  rejection, zero-untyped-outcome gate, revocation-under-load assertions all exercised on tiny fixtures).
- The harness, run for real, produces a signed dated report with all cohorts VALID and every §3
  metric within limit → the R4 GATE verdict is PASS and R5 may proceed; any metric over limit or any
  invalid cohort → R4 FAIL, which BLOCKS R5/R6 until the runner is revised (a new R3 follow-up) and
  re-measured.
- Revocation-under-load: all §5 assertions hold.

## 8. Review obligations
1. budgets (§3) are treated as hard gates; a miss blocks R5/R6 and cannot be narrated away.
2. protocol (§4) is faithful to R0 §8 (N≥40, cache validity via fadvise/mincore, monotonic timing,
   nearest-rank p95, cgroup memory, no discarded samples, no pool/stash shortcut).
3. revocation-under-load (§5) actually stresses the concurrent path, not a single idle cell.
4. R4 is non-enforcement — it touches no enforcement code, wires nothing live, activates nothing.
5. evidence is immutable + reproducible (host fingerprint, kernel/build recorded); verdict is typed.
6. the harness self-test proves the harness's OWN correctness without needing the full APU run.

## 9. Freeze criteria
Freeze pins: this document; the R3 runner predecessor hash; the budget table; the protocol; the
evidence + report schema. R4 harness code is a cheapest-eligible implementer slice (measurement
tooling — plausibly within local's envelope for the pure math parts; the runner-driving parts are
Claude-fast). R4 PASS/FAIL is a GATE input to R5, not an activation.

## 10. Deferred
- The real full-N APU acceptance run is an operator step (records host state) — its dated report
  is committed separately; do not fake it in CI.
- If a budget fails, the fix is an R3 runner follow-up (bounded, re-reviewed, re-measured) — never
  an R4 edit to make a failing number pass.

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against R4 scope + §8. No
review outcome authorizes activation; R4 is a measurement gate, not a live change.
