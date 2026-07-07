# claude — Plan-Consensus sign-off (Phase-0 keystone)

## 1. VERDICT
**APPROVE-WITH-CHANGES** — the plan is sound, correctly sequenced, and flag-gated; three
correctness/integration refinements must be in before coding P0.2.

## 2. Implementable? Yes. Required changes
- **PC1 — Monotonic (sticky-true) `zero_trust`.** Per-request re-eval is right, but the flag must
  be MONOTONIC within a task: once true, never flip back to false — even if the triggering message
  is later pruned from context (the pinned+sliding prune drops middle messages). A secret exposed
  once cannot be "unseen"; downgrading privilege back mid-task is a vuln. State it explicitly:
  `zero_trust = sticky_true OR scan(new_messages)`.
- **PC2 — Scan scope = ALL message content incl. TOOL RESULTS.** A sub-agent can read a secret
  from a file into a tool result mid-run; the derivation must scan tool-result messages, not just
  user/assistant text. (Ties to PRD "secret written to workspace mid-conversation".)
- **PC3 — Strip at BOTH catalog-build sites.** `_resolve_tool_lease` (~1100) is the lease-SWAP
  path; the INITIAL tool catalog is built elsewhere. If we only strip at the lease swap, a request
  that never calls `lease_tools` keeps the full privileged catalog. Verify + strip at the initial
  catalog construction AND the lease swap.

## 3. Risks
- **Performance (clean path):** scanning the FULL message array every turn is O(context) per turn;
  on large contexts + the single APU that adds up. Mitigation (pairs with PC1): scan only NEW
  messages since the last turn (cursor) and OR into the sticky state. Cheap + correct + monotonic.
- **Integration (routing coverage):** confirm `_route_target` (~2367) is the SINGLE chokepoint for
  BOTH streaming and non-streaming requests. If streaming resolves its target on a separate path,
  the remote block must cover it too — else a `zero_trust` streaming request could still route remote.
- **Correctness (fail-closed blast radius):** fail-closed is right, but if `a2a_guard` is
  permanently broken, EVERY request becomes `zero_trust` → all remote routing + privileged tools
  disabled fleet-wide. Add a loud alert (not just audit) when the guard fails to load, so a broken
  guard is fixed fast rather than silently degrading capability.

## 4. Test adequacy
Good core, add:
- **T-a** tool-RESULT secret (not just user message) → `zero_trust=true` (covers PC2).
- **T-b** sticky-true: secret in msg[2], then msg[2] pruned → still `zero_trust=true` (covers PC1).
- **T-c** performance: scan of a ~12k-char context stays under a stated budget (e.g. <5ms).
- **T-d** streaming path: a streaming `zero_trust` request is also remote-blocked (covers PC3/routing).
- Keep the existing keystone (secret→stripped+blocked), clean-path, and fail-closed tests.
