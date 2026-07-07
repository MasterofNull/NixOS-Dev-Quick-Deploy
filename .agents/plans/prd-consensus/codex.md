1. VERDICT: APPROVE - The PRD is implementable as written: the per-task `zero_trust` flag is the right keystone, and the Slice 2/Slice 3 sequencing protects both runtime confinement and inference reliability.

2. REQUIRED CHANGES: none.

3. RISKS THE PRD MISSED:
- Sandbox failure observability needs to be first-class: bwrap denials, missing binds, network-denied attempts, resource kills, and catalog rejections should emit structured reason codes so failures are debuggable without weakening the sandbox.
- `zero_trust` derivation needs fail-closed behavior when `a2a_guard` results are absent, stale, malformed, or unavailable; otherwise degraded guard plumbing can silently restore privileged routing.
- Grammar-cache invalidation must include the final post-lease tool schema, tool names, argument schemas, and zero-trust filter state; stale grammar reuse could re-enable stripped tools or reject newly valid calls.
- Remote downgrade behavior needs a deterministic fallback path when a task is both large-context and zero-trust, because "block remote" alone can turn into an availability failure without a local chunking or refusal contract.

4. PASS-2 ANGLE CONTRIBUTION:
- Slice 2 operational/failure-recovery: set an explicit sandbox startup budget on the APU before implementation. My proposed gate is p95 startup overhead <= 750 ms for edit/yolo invocations and <= 1500 ms for eval-sandbox runs; if exceeded, keep bwrap but batch multiple safe tool steps inside one bounded invocation rather than disabling isolation.
- Slice 2 debuggability: require every sandbox exit to classify as `policy_denied`, `missing_bind`, `resource_limit`, `tool_catalog_denied`, `process_error`, or `timeout`, with the classification visible in logs/telemetry and the dashboard. Raw sandbox stderr is not enough.
- Slice 2 revocation/escape hatch: network should remain off by default. Legit network tasks should require an explicit time-bound capability lease scoped by destination class and task id, with revocation through the same dispatch/capability state used for the reduced tool catalog. No global "network allowed" profile.
- Slice 3 tokenomics/measurement: baseline before GBNF must report invalid tool-call rate, repair attempts per valid call, total tokens spent in repair, wall time to first valid call, and APU slot occupancy. Treat GBNF as accepted only if it removes at least 90% of repair attempts on the golden suite without exceeding the latency budget.
- Slice 3 grammar overhead: grammar generation should be cached by schema hash, and decode overhead should be budgeted separately from conversion overhead. My proposed gate is p95 grammar conversion <= 100 ms on cache miss, cache-hit overhead <= 10 ms, and end-to-end tool-call latency regression <= 8% for local 8B/35B paths.
- Slice 3 swap-latency budget: measure 35B session-load latency before wiring routing. If p95 swap/load exceeds 45 seconds on the APU, keep 35B as an explicit session mode only and prefer resident 8B plus chunked planning unless the task has architecture/high-risk labels.
- Slice 3 remote-worth-it threshold: remote routing is worth it only when expected local chunking plus repair cost exceeds remote round-trip plus review cost, or when context size materially exceeds local capacity. Under `zero_trust`, remote should downgrade to local chunking or a policy refusal unless a separate approved data-egress lease exists.
