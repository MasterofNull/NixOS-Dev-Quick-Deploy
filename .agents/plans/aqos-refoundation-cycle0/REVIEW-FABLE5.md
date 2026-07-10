# Independent Model-Diverse Review — AQ-OS Refoundation Cycle 0 Package

**Reviewer lineage:** Claude Fable 5 (Anthropic family) — distinct model family from Codex (OpenAI).
**Execution principal:** Claude Code CLI session (distinct process/trust domain from the codex CLI).
**Attribution assurance:** `ORCHESTRATOR_ATTESTED` (operator-invoked session; no cryptographic identity).
**Review date:** 2026-07-10
**Independence:** no Codex-family output was used to form findings; all verified claims were
re-checked directly against source/live state by this reviewer.

## Subject binding

The advertised package root `a8d611b5…` (PACKAGE-ROOT.sha256, stamped 09:07) **does not describe the
current bytes**: PACKAGE-ROOT.json itself hashes to `82d1df05…` and 6 of 10 declared subjects were
edited after the freeze (see Finding F1). Per the package's own rule, that root is unreviewable.
This review is therefore pinned to review-time SHA-256 hashes of the exact bytes read, taken after
8+ minutes of observed writer quiescence:

**REVIEW_PIN_ROOT `1b75c03fe3c9d4f4fee5b51d7f96af4ee338a69914a37d233a01499662056694`**
(sha-256 over the sorted path→hash map of all 13 reviewed artifacts; full map in the appendix).

Any byte change to a pinned artifact invalidates this review, per the package's own semantics.

## Independent verification performed (not taken on trust)

- `round.json` re-read raw: `CONSENSUS_LOCKED` with `contributions: {}`, `aggregate_path: null`,
  all four lanes `status: "submitted"`, `landed_at: null` — the false-lock claim is **CONFIRMED**.
- `round_state.py` / `round_aggregate.py` read at source: `transition()` validates only the
  `ALLOWED_TRANSITIONS` graph; `aggregate()` transitions to `CONSENSUS_LOCKED` (line 78) with **no
  evidence invariant** — P0 gap #1 is **CONFIRMED at source**.
- Repo tracked-file count measured: **4793** (relevant to the C0.3 ≤5000 scan bound — F7).
- C0.1 permitted-edit surfaces exist as named (round_state/round_contribution/round_aggregate/
  aq-collab-round + four focused tests).
- Live QA at review time: 164 passed / 0 failed / 8 skipped (relevant to F6).

## Strengths (what this reviewer would not change)

1. **Refusal to derive authority from the invalid machine lock** — and converting it into the C0.1
   acceptance fixture — is exactly right, and rare discipline.
2. The **evidence algebra** (orthogonal `EvidenceCondition`/`ClaimAssessment`/`GateOutcome`,
   N/A-abuse prevention, optional-only composites `BLOCKED`, deterministic reason ordering) is
   sound and directly repairs the measured "green theater" failure class.
3. **Scope discipline is real, not rhetorical**: per-slice permitted-edit lists that match actual
   files, zero-model-call validation budgets, explicit stop conditions, rollback direction, and no
   new services/stores in Cycle 0.
4. The **strangler map with expiring dual paths** (2 clean cycles / 90 days) plus "retire ≠ delete"
   honors the repository's NO-DELETE/archive policy.
5. Honest evidence classes throughout (`verified_live`/`verified_source`/`inferred`/
   `research_required`), including honest self-assessment that codex-family internal reviews carry
   zero diversity weight.

## Findings

### F1 — CRITICAL (process): the package violates its own freeze discipline
PACKAGE-ROOT.sha256 was stamped 09:07; PACKAGE-ROOT.json and 6/10 subjects (PRD, CONSOLIDATED-PLAN,
STATE-CONTRACT, C0.2-SURFACE-INVENTORY, both EVIDENCE-MANIFESTs) were edited through 09:16. At review
time the advertised root described bytes that no longer exist. The package that mandates "a later
edit creates a new root and invalidates all reviews" was itself presented for review unfrozen.
**Required change:** the root descriptor must be emitted by tooling atomically with the final edit
(single command that hashes subjects → writes PACKAGE-ROOT.json → stamps .sha256), never
hand-maintained; a `verify` subcommand must be the first step of every review. This is a live
demonstration of the C0.2 mutable-`latest` failure class inside the planning workflow itself.

### F2 — HIGH (design): the proposed quorum policy deadlocks under current lane reality
STATE-CONTRACT requires **two independent model families AND two independent execution principals**,
and explicitly says an owner waiver "cannot reduce the two-family/two-principal minimum." Measured
lane reality: Codex (family 1) and Claude (family 2, this review) are the only reliably available
families. Local/Qwen wedges under contention (verified twice this week: 841s and 2233s silent
failures; F2.5 scheduler dormant) and Antigravity is unverified. If Claude is unavailable — or if a
future round needs a family *other than* the proposer's — ratification is mechanically impossible
and the policy hard-deadlocks with no degraded mode.
**Required change:** either (a) declare the local-lane repair (wedge guards + F2.5 activation) a
*governance prerequisite* rather than Cycle 3 work, or (b) add an owner-ratified bounded degraded
mode (e.g., one family + owner co-review, time-boxed, auto-expiring, recorded as degraded). The
current text inverts a real dependency: scheduler reliability is upstream of the consensus policy.

### F3 — MEDIUM (contract gap): `aq-canonical-json-v1` forbids floats but the evidence domain is full of them
Real evidence in this harness is float-shaped: pass_rate 0.917, ragas faithfulness 0.6, drift
percentages, thresholds, p95 latencies. The contract forbids floats without specifying the required
representation for measures. Every producer will invent its own convention (scaled integers?
decimal strings? milli-units?), which is precisely the drift class C0.2 exists to kill, and the
cross-language golden vectors will not cover real payloads.
**Required change:** the contract must specify one numeric-measure rule (recommend: decimal strings
with explicit `scale`/`unit` fields, or integer `numerator`/`denominator` pairs as already used in
the claim matrix) and include float-shaped golden vectors.

### F4 — MEDIUM (correctness): the QA pointer's exclusive-writer lock is only exclusive within one telemetry root
C0.2's compare-and-swap pointer protocol assumes all writers contend on one lock. This harness has a
**known dual telemetry root** (deployed `/var/lib/ai-stack/hybrid/telemetry/` vs repo
`.agents/telemetry/` — results files verifiably exist in both today). Two QA writers resolving
different roots never see each other's lock; the "exclusive writer" invariant silently fails and the
pointer race returns. The plan lists telemetry-root resolution as unresolved question #5 (a
ratification blocker); it is actually a **correctness precondition**.
**Required change:** state explicitly that lock, pointer, and artifacts MUST resolve to a single
root; make root resolution a C0.2 Intent-Lock precondition; add a fixture where two writers are
started with different env-resolved roots and the test FAILS unless they converge.

### F5 — MEDIUM (realism): the C0.1 local-review budget cannot review anything
"≤1,500 input tokens / ≤180 output tokens, one retry" for a local review of a state-machine change
is review theater. Measured local behavior in this harness needs 300s+ and ~1200-token budgets for
code tasks; 180 output tokens cannot express a substantive verdict with evidence anchors, and under
the package's own rules a non-substantive contribution has zero weight — so the budget guarantees
the local lane contributes nothing while appearing included.
**Required change:** either raise the local-review budget to the measured envelope (and accept the
latency), or remove the local-review step from C0.1 and record honestly that reviews are
remote-family-only until the local lane is repaired (consistent with F2).

### F6 — LOW (staleness): the PRD carries a stale live-evidence anchor
PRD §2 cites "currently visible 162/0/10" QA; live state at review time is 164/0/8. Trivial in
itself, but it is a `STALE` evidence condition inside the document that defines staleness blocking —
and it will bite when fixtures assert against the anchor.
**Recommended change:** replace point-in-time live numbers in durable artifacts with dated,
hash-referenced evidence records (the package's own EVIDENCE-MANIFEST mechanism).

### F7 — LOW (margin): the C0.3 scan bound has ~4% headroom
Measured tracked files: 4793 against the ≤5,000 bound. Growth of ~200 files (one busy cycle) trips
`scan_complete_within_bound` and blocks C0.3 ratification for a reason unrelated to authority truth.
**Recommended change:** state the measured baseline in the plan and either raise the bound to a
justified multiple (e.g., 8,000) or make truncation a `DEGRADED`-with-reason outcome rather than a
blocker, with owner sign-off.

## Answers to the plan's unresolved questions (reviewer's recommendation, owner decides)

- Q3 (proxy satisfying procedural review): yes, but only as *procedural* completion — never counted
  toward diversity, exactly as drafted. Keep it.
- Q7 (unreadable Codex state DB): resolved since drafting — it was a live-writer WAL lock; the
  monitoring read now opens `immutable=1` (commit c5ff4f02). Classify as *observer limitation,
  fixed*; not a degraded-confidence skip.
- Q9 (concurrent surface ownership): at review time, `scripts/ai/lib/round_contribution.py` was
  modified by the orchestrator thread (capture-dedup fix, commit d5eae85f) — C0.1's permitted-edit
  list overlaps this file. Ownership preflight must diff against d5eae85f or later, not the bytes
  codex last read.

## Verdict

`VERDICT: APPROVE_WITH_CHANGES — the product direction, three-slice Cycle 0 scope, evidence algebra,
and state contract are sound and executable; F1 (freeze tooling), F2 (quorum deadlock), F3 (numeric
representation), and F4 (single telemetry root) must be dispositioned in a new subject revision.
Under the package's own semantics this verdict approves nothing: it obligates a new revision whose
exact root must then receive fresh APPROVE reviews. This review supplies one independent
model-family lineage (Anthropic) and one independent execution principal toward the two-and-two
quorum; a second independent family (repaired local/Qwen or verified Antigravity) or an
owner-ratified degraded mode (F2) is still required.`

## Appendix — exact reviewed bytes (SHA-256)

| Artifact | sha256 |
|---|---|
| .agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md | 8e31d86eca71c63e7983360752ebbe09dee0c6eff8ceb0b960bd62f39e86d8e9 |
| CONSOLIDATED-PLAN.md | e7e498e86b45e874047f7555ee93b57d8629d0d282ec64543a5725c1c78ec634 |
| STATE-CONTRACT.md | d38ef59abc6eb037684969d77ae3e1c2f515facf5b3f92a7e9be1c4737f62052 |
| EVIDENCE-ALGEBRA.md | 389311e1e6d949560751c03061af9c0e411047f714a7004b1b3cd0e86cd1b266 |
| C0.2-SURFACE-INVENTORY.md | f195233fe80ebad07f3480fef27f61bb5ac9cb2b358b83818bf3169f378062ae |
| THREAT-REGISTER.md | 4c0a340f38f00cbe6fb2e20d834ce6b0a5442f2483d0c43639611c3ef80867c4 |
| DECISION-LOG.md | 82f9cbd0d7d5e6c00730896c1c612b48c548199952dc436f1aa46745c7ec8fdc |
| REFERENCE-AND-MIGRATION-COMPARISON.md | d28d027c821a900845e9866a610a7f3d63fcd538f7bf7185950a97b0a90f54b5 |
| EVIDENCE-MANIFEST.json | ca1b0935838ae8037c099fc642b3a6d13fbb193bad15fa6c6c383092eaae3248 |
| EVIDENCE-MANIFEST.md | a80fa5e088d2593df492dd5659aeb36ff1262f6a31c88a9282349167b76ac5be |
| PACKAGE-ROOT.json | 82d1df05a0575a89e1bf513275d6a634eb7f54b79b4a8ada25daa7941d105226 |
| AGGREGATE.md | 7c4b2cebf41f7e7aa56a7face174d25f7a142f090b733ef932f154169e7cc124 |
| REVIEW-FINDINGS.md | 4a10365978f4896b17c3e9c003f95dfcefafced77b5f120c1ff98946f98e8b6d |
