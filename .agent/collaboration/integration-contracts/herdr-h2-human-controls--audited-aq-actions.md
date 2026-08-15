---
doc_type: reference
id: herdr-h2-human-controls--audited-aq-actions
title: Herdr H2 Human Controls to Audited AQ Actions Integration Contract
status: draft
date: 2026-08-09
parent_prd: herdr-agent-operations
contract_number: 4
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
implementation_authority: false
runtime_authority: false
---

# Integration Contract #4: human controls -> audited AQ actions

## Purpose and boundary

This contract freezes H2's cardinal rule: every human action executes only through an existing audited AQ
command or API path, and every action re-enforces the current actor's authority at execution time.
`recommended_action`, `required_authority`, and `action_availability` are advisory labels. Neither
`aq.operator-context.v1`, `aq.herdr.presentation.v1`, a dashboard view model, nor a HERDR layout is a
mutation endpoint or authorization token.

This design grants no control implementation, new command/API, action routing, privilege, runtime,
deployment, commit, rebuild, or activation authority.

## Shared interface

### Inputs

- authenticated current actor identity and current authorization facts obtained by the existing audited AQ
  action path at execution time;
- a semantic operation category selected by the human, never an arbitrary command/URL/argv; it resolves
  unavailable unless a future exact allowlist row has been independently accepted;
- bounded canonical target/evidence reference tokens, resolved server-side against current canonical state;
- expected canonical revision/digest/fence where the existing action contract supports optimistic binding;
- optional advisory labels from `aq.operator-context.v1`, used only to explain the choice.

Projection digests, role labels, pane/session state, terminal text, browser state, recommendations, cached
authority, and caller-supplied claims are not authorization evidence.

### Output

The selected existing audited AQ path returns its native closed, redacted action receipt or explicit denial.
The H2 surface may project only:

- operation category and authoritative action-path identifier;
- accepted/denied/unavailable/unknown result category;
- current actor-authority decision category;
- canonical target revision/digest after the action, when the authoritative path returns one;
- bounded audit/evidence receipt reference and freshness;
- bounded denial/conflict/stale-authority reason;
- next required authority/gate category.

No surface may synthesize success, mutate a projection, execute a shell string, or bypass the native audit
receipt. A future eligible path may be a server-side audited AQ command/API owned by its canonical authority;
absence of the complete proof matrix means the action is `unavailable`, not permission to add one in H2.

### Frozen allowlist and closed receipt envelope

The H2 allowlist is deliberately **empty**. No currently inspected path is eligible for a H2 control.
In particular, `scripts/ai/aq-approve` is excluded: it has no current-actor authorization check and invokes
its executor before locked resolution/CAS, so it cannot safely provide authorization, fencing, idempotency,
or a trustworthy postcondition receipt. Consequently all H2 controls are rendered unavailable and no human
intent reaches a handler in this slice.

| operation | handler | current actor authorization | target fence/CAS | idempotency key | redacted receipt | H2 state |
|---|---|---|---|---|---|---|
| any operation category | none | none | none | none | none | `unavailable` |

Only a separately authorized amendment may add a row, and each row must bind exact handler path and function,
operation-specific server-side actor policy, target revision/digest fence checked before side effects,
server-owned idempotency key and duplicate result, postcondition read, and bounded receipt issuer/reference.
An example name is not a mapping; absent any one cell, the row is rejected and the control remains unavailable.

The only permitted UI/result object until such an amendment is:

```text
{schema_version:"aq.h2.action-result.v1", operation:"none", action_path:null,
 outcome:"unavailable", actor_decision:"not_evaluated", target_ref:aqref|null,
 expected_revision:null, idempotency_key:null, receipt_ref:null,
 reason:"no_eligible_audited_path", next_gate:"separate_authorized_allowlist_amendment"}
```

All fields are required and closed; the UI must not manufacture a confirmation, retry token, receipt, or
success state. This is an explicit security boundary, not a temporary fallback.

### Direction

```text
human intent -> existing audited AQ command/API -> current authority check -> canonical mutation/denial
                                  |
                                  +-> bounded audited receipt -> read-only surfaces
```

There is no `projection -> mutation` path.

## Error behaviour

- Missing/expired/ambiguous actor identity or authority: deny closed and emit bounded audit reason.
- Projection says available but current authority disagrees: current authoritative check wins; deny and mark
  advisory state stale/drifted.
- Target revision/digest/fence mismatch: deny conflict; never silently retarget current state.
- Missing existing audited operation mapping: unavailable; never fall back to shell, direct file write,
  browser-side request construction, HERDR CLI, or a generic action endpoint.
- Duplicate/retried action: unavailable under this frozen empty allowlist. A future eligible row must enforce
  idempotency and a pre-side-effect CAS/fence; H2 never infers success from a prior click or cached receipt.
- Native receipt missing/malformed: outcome is unknown/needs_review; never success, complete, or accepted.
- Unsafe target/content injection: reject without echoing raw input into command, path, URL, HTML, log,
  metric, RAG, terminal, or remote payload.
- Action service unavailable: show unavailable and preserve the current canonical state.

Unknown never becomes `0`, `false`, healthy, complete, accepted, successful, or blank `--`.

## Auth and trust requirements

- Authentication and authorization are performed by the existing audited action path for every invocation,
  immediately before mutation; UI disablement is not enforcement.
- Actor authority is least-privilege, operation-specific, target-bound, revision/fence-aware where supported,
  and never inherited from projected `role` or `required_authority` text.
- The current allowlist has zero entries. Any future allowlisted operation category maps server-side to one
  exact existing handler with the matrix proof above. User/model content cannot
  choose executable names, argv, paths, hosts, ports, or payload shapes.
- CSRF/replay/origin/audit controls remain those of the existing API/command authority and cannot be weakened
  by H2. A future implementation inventory must name the exact existing path per control.
- Every accepted or denied action emits a redacted bounded audit receipt/evidence reference.
- Canonical mutation truth comes only from the authoritative path's postcondition/receipt, never optimistic UI.

## Acceptance vectors

1. Every rendered control maps to one exact pre-existing audited AQ path; an unmapped control is unavailable.
2. Every click/invocation rechecks current actor authority server-side; cached projection/UI state cannot
   authorize.
3. A role/recommendation/pane label claiming elevated authority cannot increase permission.
4. Revision/digest/fence drift denies or requires refresh; it never silently acts on a different target.
5. Accepted and denied actions both yield bounded audit evidence; missing receipt stays unknown/needs_review.
6. Repeated/replayed input cannot duplicate a mutation beyond the existing path's idempotency/CAS contract.
7. `through_parent` work routes the human to the parent authority surface; it never enables direct child input.
8. Prompt/output/secret/path/identity/reasoning/terminal/argv/environment injection cannot become command,
   endpoint, payload, log, metric, RAG, or remote content.
9. Keyboard-only and screen-reader flows expose action label, why, evidence, required authority,
   availability, confirmation/denial, and post-action canonical truth.
10. Disagreement between advisory availability and current authority is visible drift and current authority
    wins without mutating the projection.

## Explicit exclusions

- New commands, APIs, generic mutation endpoints, dashboard/HERDR controls, or action adapters;
- projection, schema, resolver, consumer, authorization, receipt, or audit implementation;
- direct file edits, shell/argv construction, raw HERDR CLI/socket use, pane/session/process control;
- H1 baseline repair, acceptance, staging, commit, rebuild, or activation;
- H3 brokered agent PTYs and all agent launch/execution paths.

## Sign-off

- [ ] Claude: PENDING — independent orchestrator review required.
- [x] Codex: AGREED — design only; cardinal audited-path/current-authority rule frozen.
- [ ] Owner: PENDING — freeze required before any later implementation request.

PREPARED_ONLY; independent review required; implementation gated on accepted H1 + separate authorization.
