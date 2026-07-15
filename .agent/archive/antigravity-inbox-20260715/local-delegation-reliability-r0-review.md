# Antigravity Review Task: Local Delegation Reliability R0

Role: flagship architecture, security, SRE, and eval reviewer. **Read only; do not implement.**

Review the latest bytes on disk. The first Codex flagship round requested revision; the package has
since been amended to a seven-new-file, fixture-only R0. Phase-0, validation registry, dashboard, and
all live wiring are deferred to R4.

Read:

1. `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md`
2. `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PLAN.md`
3. The cited current paths in `delegate-to-local`, `aq-agent-loop`, `dispatch.py`,
   `task_config.py`, `task_registry.py`, `agent_executor.py`, and `shared/llm_config.py`.

Independently verify D1–D11. Threat-model collision-safe identity, single-slot admission, writer
leases, budget propagation, queue/prefill/generation phase separation, progress renewal, malicious or
meaningless heartbeat renewal, infinite loops, context/OOM, cancellation/PID-reuse races, telemetry
truth, and rollback. Confirm the proposed R0 exact inventory is fixture-only and cannot alter live
delegation behavior.

Return:

- per-section score;
- blocking amendments;
- missing tests/metrics;
- `PASS`, `REQUEST_REVISION`, or `FAIL`;
- explicit answers: whether R0 may start, whether R1–R4 remain unauthorized, and whether L2B-A can
safely remain staged while R0 is developed.

Also verify that the switchboard remains the sole model-slot authority; execution epochs cannot be
self-renewed; queue arbitration prevents starvation; writer leases are descriptor-held and fenced;
registry/cancellation transitions are linearizable; PID reuse, OOM cleanup, and telemetry tampering
are covered; and the live-source manifest plus bidirectional adoption guard make R0 real evidence
without adopting it into production.

Write the review to `.agents/plans/local-delegation-reliability-r0/antigravity.md`, then process this
inbox item with `aq-antigravity-inbox complete`. Do not edit the PRD/plan or any implementation file.
