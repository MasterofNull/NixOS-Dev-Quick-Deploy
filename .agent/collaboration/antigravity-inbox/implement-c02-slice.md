# A2A task for antigravity — IMPLEMENT slice C0.2 (owner-reassigned from codex)

Dropped: 2026-07-11T05:15:00Z
Requested by: fable-5 orchestrator (owner directive: codex quota-blocked twice, slice reassigned to you)

You are AUTHORIZED under .agents/plans/aqos-refoundation-cycle0/IMPLEMENTATION-AUTHORIZATION-C0.2.md
(auth-c0.2-20260710, key 9ec8fd14-dd62-441f-9abe-e551bdd63d0e, expires 2026-07-17, reassignment
recorded). Read that record FIRST, then CONSOLIDATED-PLAN.md section C0.2, C0.2-SURFACE-INVENTORY.md
(your frozen edit list — the ONLY files you may modify, plus the two new tests), and
EVIDENCE-ALGEBRA.md (the contract to implement).

MANDATORY FIRST ACTS (Intent Lock — before ANY edit):
1. Single telemetry root: ONE canonical resolver — deployed /var/lib/ai-stack/hybrid/telemetry/
   authoritative, repo .agents/telemetry/ dev fallback; repo/deployed mismatch fails
   TELEMETRY_ROOT_DIVERGENCE before writing. Lock, pointer and artifacts all resolve through it.
2. Baselines BEFORE edits (ratified protocol): 5 cold + 20 warm samples, idle, p50/p95 monotonic
   duration + /usr/bin/time -v max RSS, for (a) scripts/ai/aq-report runtime and (b) the
   /api/aistack/effectiveness/scorecard endpoint. Write results to
   .agents/plans/aqos-refoundation-cycle0/C0.2-BASELINES.md.
3. Test filenames frozen: scripts/testing/test-qa-evidence-store.py, scripts/testing/test-evidence-algebra.py.

IMPLEMENT (plan text governs over this summary):
- The EvidenceCondition/ClaimAssessment/GateOutcome algebra, deterministic rules 1-12 of
  EVIDENCE-ALGEBRA.md: non-valid evidence -> UNKNOWN never PASS; zero denominator ->
  UNKNOWN/NO_DENOMINATOR; required FAIL -> FAIL; required UNKNOWN -> BLOCKED; required WARN ->
  DEGRADED; stable sorted reason codes with remediation; proxies never silently substitute.
- Immutable QA evidence: every QA invocation writes immutable canonical payload bytes (run ID,
  monotonic start sequence, times, commit/dirty state, phase results, bounded env fingerprint);
  sha256 lives in the pointer sidecar, never inside the hashed payload. latest-qa-results.json
  becomes a versioned atomic pointer: exclusive writer lock + compare-and-swap selecting the highest
  lock-protected start sequence; temp file + fsync + atomic replace + parent-dir fsync. Consumers
  verify pointer AND artifact hash.
- Retention: 7 days / 64 artifacts soft, 64 MiB hard cap; never prune the pointer target; record
  deletion evidence; oversized referenced artifact -> ARTIFACT_TOO_LARGE, quarantine, previous
  verified pointer stays.
- aq-report --machine = the canonical serialized scorecard; dashboard synthesis RETIRED —
  dashboard/backend/api/routes/aistack.py consumes the canonical output and projects
  status/dimensions/reasons/provenance/age/hash-verification; identical semantics CLI vs API.
- scripts/ai/lib/agent_run_events.py rejects invalid producer envelopes at emission.
- Fixtures (in the two new test files): all-valid, missing, malformed, stale, insufficient sample,
  failed validation, missing review, conflicting evidence, rejected producer; TWO CONCURRENT WRITERS
  in an ISOLATED temp telemetry root (both artifacts survive, pointer selects highest sequence);
  corrupt pointer/artifact; interrupted write; retention/GC; dual-env root-divergence fail-closed;
  CLI and dashboard consuming identical injected fixtures. Register Phase-0 check 0.10.28.
- Budgets: ZERO model/APU calls in validation; aq-report <=10% runtime regression and <=60s
  absolute; scorecard endpoint p95 <=250ms local; incremental RSS <=64MiB; artifact <=2MiB /
  pointer <=4KiB / retained total <=64MiB.

HARD CONSTRAINTS:
- ONLY the frozen surface list + the two new tests. Undeclared production consumer discovered ->
  STOP and report; the plan amends; never silently expand.
- No destructive concurrency against production telemetry — isolated roots only.
- Live validation only after acquiring the same exclusive writer lock (proves no other writer).
- STOP if: required unknown can pass, CLI/dashboard disagree, evidence lost, GC can delete the
  pointer target, live state clobbered, any budget fails.
- DO NOT COMMIT and DO NOT push — stage the work and STOP. The independent reviewer is the
  Anthropic lane (you are now the implementer, so Gemini cannot review its own slice). The
  orchestrator reviews, reruns Tier 0, and commits.
- Respond by writing .agents/plans/aqos-refoundation-cycle0/C0.2-IMPLEMENTATION-REPORT.md:
  files touched, fixture results, baseline vs post-change numbers, deviations, open questions.
