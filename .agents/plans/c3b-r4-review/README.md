# Collaborative Round — c3b-r4-review

Opened: 2026-07-30T15:11:14Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C slice C3b R4 (revocation-under-load +
measured APU performance gate). Read-only. DESIGN review. Substitute for codex (down to Aug-4;
confirmatory on return). VERIFY claims against real code — don't approve prose.
READ: .agents/plans/aqos-foundation-c/C3B-R4-DESIGN-AND-AUTHORIZATION.md; the R3 runner it measures
(ai-stack/switchboard/execution_cell_runner.py, committed ccbc0718); R0 §8 (the perf protocol source,
in C3B-DESIGN-AND-AUTHORIZATION.md).
JUDGE (§8): 1. budgets (§3) are HARD gates that block R5/R6, not narratable. 2. protocol (§4)
faithful to R0 §8 (N>=40, cache validity via posix_fadvise/mincore, CLOCK_MONOTONIC_RAW, nearest-rank
p95, cgroup-v2 memory, NO discarded samples, NO pool/stash shortcut to hit a limit). 3.
revocation-under-load (§5) actually stresses the CONCURRENT path at the cap (not one idle cell) and
asserts no post-bump GREEN + budget teardown + no unaccounted procs. 4. R4 is NON-ENFORCEMENT —
touches no enforcement code, wires nothing live, activates nothing (is that truly the case?). 5.
evidence immutable+reproducible (host fingerprint/kernel/build); verdict typed. 6. the harness
self-test proves the harness's OWN correctness offline without the full APU run. Any NEW fail-open?
Any way a failing budget could be silently passed? Is the "real acceptance run is an operator step,
not CI" split honest and safe?
OUTPUT: `VERDICT: PASS`/`FAIL`/`REQUEST_REVISION` on line 1, then findings by severity (BLOCKING/
SHOULD-FIX/NICE-TO-HAVE) with §ref + concrete fix. No outcome authorizes activation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c3b-r4-review.md` and writes `antigravity.md`. No API keys.
