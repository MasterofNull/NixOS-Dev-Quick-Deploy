# Review Task — Canonical Local Inference Contract and aq-chat Parity

Role: independent architecture/product/reliability reviewer. Research and review only; not an implementer.

Read `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` and inspect the named existing code/config surfaces read-only.

Assess:

1. Whether `delegate-to-local` plus a reusable Python API is the correct canonical control plane.
2. Whether the request/resolved-plan/event/result contracts cover interactive and batch parity.
3. Missing requirements for streaming, cancellation, history, tools, authority, budgets, fallback, provenance, privacy, dashboard telemetry and rollback.
4. Risks for flagship, standard and budget remote callers.
5. Whether the delivery slices are independently testable and safely ordered.
6. Exact REQUEST_REVISION items and proposed acceptance tests.

Return `APPROVE`, `REQUEST_REVISION`, or `REJECT` with evidence and concise recommendations.

Do not edit, stage, commit, restore, archive, or run an implementation loop. Complete/archive this inbox task only after saving the review through the established Antigravity IDE/OAuth workflow.
