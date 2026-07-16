# Flagship design review — Agent Connection Reliability C0

Review these exact artifacts:

- `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md` SHA-256
  `629ca89b714d691e305762366954070d492aa899d6c5e65a22102281f32ca17c`
- `.agents/plans/agent-connection-reliability/PROGRAM-PLAN.md` SHA-256
  `07a1e9f3fd346da46838d060d0f308be3b6aeeaae46f547a73f66df1ba1d09e1`
- `.agents/plans/agent-connection-reliability/C0-DESIGN-PACKET.md` SHA-256
  `f6b5acee94e254ef2a9fab332a4f50bfe6a0322142e234a35e892f26c18ddccb`

Evidence to verify: current wrappers use caller-owned background processes; managed caller teardown
killed two correctly routed Fable tasks before output; sandboxed user-systemd access was denied; raw
prompt/audit interpolation and outer `/dev/null` can hide supervisor failures. Review the architecture
for all Claude, Codex, local, Antigravity, and future adapters—not only Claude.

Adjudicate:

1. host-side socket-activated broker versus caller-owned `nohup`/in-process supervisor;
2. Unix peer/admission/security boundary and same-user residual threat;
3. reuse of the current registry as lifecycle spine without creating a second authority;
4. adapter contract, idempotency/CAS/fencing, restart uncertainty, cancellation ownership;
5. transient versus quota-parked versus hard failure and intended-lane resume;
6. monitoring-first TUI/web/aq-qa contract and service-coverage gates;
7. C0's pure eleven-file scope, golden vectors, and no-live-adoption boundary;
8. sequencing C1 fake adapter, C2 Claude canary, C3 other adapters, C4 park/resume, C5 cutover.

Return `PASS`, `REQUEST_REVISION`, or `FAIL` with exact blockers. If PASS, authorize preparation of a
hash-bound C0 contract-only grant—not implementation itself. C1–C5, M2B, R1–R4, new stores, Q8,
deployment, and live traffic remain unauthorized.

Write `.agents/plans/agent-connection-reliability/antigravity-c0-design-review.md`, then complete the
inbox item. Do not edit candidate/runtime files, stage, commit, deploy, invoke inference, or terminate
processes.
