# F2 Plan-Consensus Review — codex

## Verdict
PASS with targeted plan changes. The implementation plan faithfully realizes the ratified F2 design and the Phase-A / Phase-B split is fundamentally correct.

Phase A is properly rebuild-free because F2.1-F2.4 are pure Python library modules under `scripts/ai/lib/`, have no service wiring, no Nix declarations, no live inference calls, and can be validated with unit tests only. Phase B is correctly rebuild-gated because the fast-lane server, new port, resident model services, VRAM pool enforcement, dispatch integration, and any llama.cpp process topology changes affect deployed runtime state.

## Answers

1. Phase split: correct. Nothing in F2.1-F2.4 is inherently rebuild-dependent if the modules stay pure and unwired. Dispatch routing to `:8082`, service declarations, port option additions, model residency, and GPU layer allocation all belong in F2.5/F2.6. Keep any `dispatch.py` live routing out of Phase A.

2. F2.1 scheduler: directionally correct for the ratified 3-band MLFQ if tests assert deterministic ordering, aging promotion from P3/P2, starvation bounds, and P1-over-P3 preemption. The plan should make the no-starvation invariant concrete with a configurable max-wait bound instead of only "promote after N s".

3. F2.2 GBNF cache: `sha256(schema_json + zero_trust_state)` is the right key shape, but key stability requires canonical JSON serialization for both inputs and an explicit separator/version prefix to avoid ambiguous concatenation and future namespace drift. Sharing F3's zero-trust namespace is correct if `zero_trust_state` is treated as a namespaced canonical policy digest, not an arbitrary mutable blob.

4. F2.3 back-pressure: correct if `local-delayed` is a typed admissible lane state consumed by F1 quorum logic, not a failure/abstain/timeout. The implementation plan should require a small F1 integration contract test proving consensus cannot silently proceed while local is delayed.

5. F2.4 routing: yes, routing can remain pure/testable. It should accept a typed `task_class` enum or validated string and return a `Tier` with concurrency metadata, with unknown tasks defaulting conservatively to mid or large and never invoking real inference.

6. F2.5 biggest infra risk: VRAM residency thrash and accidental co-residency on the 4GB Renoir APU, especially 35B session load overlapping with resident 8B/small tiers or mmap/offload behavior that exceeds the intended pool. The 35B-on-CPU flip is correctly gated as F2.6 measure-before-adopt; do not assume CPU-only 35B is viable until A/B data covers latency, throughput, memory pressure, and cheap-lane availability.

## Top 3 Plan Changes

1. Add explicit Phase-A guardrails: F2.1-F2.4 must not modify `dispatch.py`, Nix modules, ports, services, or live llama.cpp request paths. Any live routing belongs to F2.5.

2. Tighten acceptance criteria for F2.1 and F2.3: define a configurable starvation bound for MLFQ aging, and add a quorum contract test showing `local-delayed` remains admissible and prevents never-skip-local regressions.

3. Specify canonical cache key construction for F2.2: `sha256("gbnf:v1\0" + canonical_schema_json + "\0zt:" + canonical_zero_trust_namespace_digest)`, or equivalent, so cache keys are stable, versioned, and unambiguous.

## Final Call
Proceed with Phase A as autonomous rebuild-free implementation after the three plan edits above. Hold Phase B behind review, dry-build, VRAM measurements, and explicit go-ahead before any service switch.
