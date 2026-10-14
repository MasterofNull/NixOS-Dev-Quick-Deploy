# DP4 truthful guidance status

Objective: correct the reviewed false success signal in DP4 guidance. The endpoint only writes a spool file and an audit event; no agent consumer exists.

Scope: report recorded/pending delivery without claiming injection, surface persistence failures, make the corresponding Pi dashboard message truthful, and exercise successful persistence plus failure in focused tests. Close test-owned pooled HTTP clients. Reuse existing patterns; no dependencies or new runtime consumer.

Acceptance: successful file persistence is distinct from agent delivery, failures do not return delivery success, UI reflects the actual response, focused regression tests pass without leaked HTTP sessions, independent review and Tier0 pass.

Activation: live steering remains deferred as of 2026-10-14 pending a designed consumer/acknowledgment contract and end-to-end evidence. Repo changes ship through PR; no service restart.
