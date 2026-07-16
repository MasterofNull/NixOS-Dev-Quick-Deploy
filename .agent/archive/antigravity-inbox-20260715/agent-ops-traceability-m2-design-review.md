# Flagship design review — Agent Ops Traceability M2 dispatch enforcement

Review `.agents/plans/agent-ops-traceability-r0m/M2-DESIGN-PACKET.md` at SHA-256
`dea5417e11d2867592a2c2a4f2de31abca6a36e958df21bfe25396bdecee7b4a` as an independent flagship
architecture, security, SRE, and adversarial-concurrency reviewer.

Read the accepted parent PRD/plan, M0/M1 acceptance evidence, current `agent_ops_projection.py`,
`aq-delegation-registry`, `task_registry.py`, and all five `delegate-to-*` wrappers. This is a
design-only review. No M2 implementation is authorized.

Explicitly adjudicate:

1. Whether revising the R0M inventory to include the existing shared registry CLI/library is the
   correct boundary, or whether the proposed 17-file inventory is too broad or incomplete.
2. Stable lock inode, pre-lock truncation, atomic replacement/fsync, bounded lock acquisition,
   strict parsing, record revision/CAS, symlink/non-regular rejection, and concurrent lost-update
   threats.
3. Whether closed short-lived `queued` admission can be tracked before PID attachment without
   letting forged/legacy records assert authority; specify the grace/expiry evidence required.
4. PID plus start-time attachment, supervisor/child identity, PID namespaces, early exit, zero-output,
   signal, timeout, cancellation, and terminal idempotency behavior.
5. Role/lane normalization, raw-prompt removal, safe summary/digest handling, metric cardinality,
   stable reason codes, and machine-clean status/check/list output.
6. The retired `delegate-to-gemini` fail-closed boundary, and whether `aq-antigravity-agent`, internal
   platform subagents, collaboration rounds, or any other route must be in scope or explicitly
   blocked.
7. Whether existing Agent Ops TUI/JSON plus Phase-0/Bash/registry gates satisfy monitoring-first
   delivery without a web-dashboard edit.
8. Whether M2 can remain one bounded slice; if not, propose a safe M2A/M2B sequence with exact
   authorization boundaries.

Return `PASS`, `REQUEST_REVISION`, or `FAIL` with exact blocking/non-blocking findings and a recommended
inventory. Confirm M3, local reliability R1–R4, inference R1–R4, new lifecycle stores, and owner Q8
decisions remain unauthorized. Write
`.agents/plans/agent-ops-traceability-r0m/antigravity-m2-design-review.md`, then complete this inbox
item with `scripts/ai/aq-antigravity-inbox complete`. Do not edit candidate/runtime files, stage,
commit, deploy, invoke inference, or terminate processes.
