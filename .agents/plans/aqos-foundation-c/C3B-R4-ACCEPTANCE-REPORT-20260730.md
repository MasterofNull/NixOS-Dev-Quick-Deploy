# Foundation C — C3b R4 Performance Acceptance Report (2026-07-30)

**Operator acceptance run** of the R4 harness (`8b033ba6`) against the real APU host — the full-N
measurement the R4 design (§6/§10) defers out of CI. **VERDICT: PASS** on every §3 budget.

## Host (immutable fingerprint)
- host `hyperd`, kernel `7.1.3`, `x86_64`, CPU governor `schedutil`, mem_total `29.24 GB`
  (MemAvailable ~11.9 GiB at run time; 14 GiB swap in use but zero swap-delta within valid samples).
- build_revision `8b033ba65a65a3130c39e2adedcbd85906d768b3`.
- bwrap 0.11.2; unprivileged userns permitted; `/var/tmp` (ext4, disk-backed) used for cache-eviction
  validity (`AQ_R4_PERF_TMPDIR=/var/tmp`).

## Main run (N=40/cohort/class, cap=1) — run_id aae31a92, 240 samples
- All **6 cohorts VALID** (cold+warm × noop/read-validate/single-file-write), 40/40 successful each.
- **240/240 GREEN** outcomes (zero untyped/failed → zero-untyped-outcome gate satisfied).
- Evidence: `r4-acceptance-20260730.jsonl` (sha256 `c589d507…`, 240 rows) + `.json`.

| Metric | Measured p95 | Budget | Result |
|---|---:|---:|:--|
| self-contained clone/snapshot | **0.098 s** (max 0.146) | ≤ 3.0 s | PASS (30×) |
| runner→bwrap spawn | **0.9 ms** (max 7.4) | ≤ 250 ms | PASS (~275×) |
| peak incremental RSS / cell | **0.2 MiB** (max 6.6) | ≤ 768 MiB | PASS |
| unaccounted / untyped outcome | **0** | 0 | PASS |

(cgroup_available=True; the trivial noop/read/write cell commands allocate little, hence the small RSS.)

## Revocation-under-load (cap=1) — PASS
- `all_assertions_passed: true`, failures `[]`, skipped `[]`.
- **teardown/revocation p95 = 1.68 ms** (budget ≤ 5.0 s) — epoch bump → cgroup whole-tree kill →
  prove-absence → typed rollback; **zero cells published GREEN after the bump**; runner remained
  responsive to new deny-closed requests. Evidence: `r4-acceptance-revocation-20260730-cap1.{json,jsonl}`.
- cap=2 (max-configurable, 2 concurrent cells) validation: **PASS** — `all_assertions_passed: true`,
  teardown p95 **2.4 ms** (≤ 5.0 s). Evidence: `r4-acceptance-revocation-20260730-cap2.{json,jsonl}`.

## Verdict
**R4 acceptance PASS** — every §3 budget met with large headroom; all cohorts valid; revocation
holds within budget under load. **The R4 performance gate for R5/R6 is SATISFIED.** (Assurance-side:
R5 remains held for codex's Aug-4 confirmatory per owner directive; the R4 gate is the *performance*
precondition, now green.)

## Honesty notes
- The strict per-stage boundary timestamps are obtained by the harness's runtime-only instrumentation
  (no runner-source change; R1/R2/R3 byte-unchanged). Numbers are the real host measurement.
- `metrics_unavailable` was empty on the revocation run (teardown measured); the main run listed
  `teardown_latency_p95_s` unavailable only because it wasn't a revocation run — now measured separately.
- This run exercised the R3 runner code directly over a real UDS (not the systemd unit, which is
  `enable=false`); cgroup control worked under the session. A future run against the deployed
  `Delegate=true` unit would additionally validate systemd socket-activation (the standing R6 skip).
