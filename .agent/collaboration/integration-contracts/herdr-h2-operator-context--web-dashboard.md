---
doc_type: reference
id: herdr-h2-operator-context--web-dashboard
title: Herdr H2 Operator Context to Web Dashboard Integration Contract
status: draft
date: 2026-08-09
parent_prd: herdr-agent-operations
contract_number: 3
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
implementation_authority: false
runtime_authority: false
---

# Integration Contract #3: operator context -> web dashboard API/UI

## Purpose and boundary

This contract defines how the web command center consumes canonical work semantics without creating a
second source of truth. It consumes `aq.operator-context.v1` for mission/work/attention/evidence/learning and
also consumes the separate `aq.herdr.presentation.v1` from contract #5 for HERDR presentation-health.
The two objects remain distinct; their typed join is explicit drift, not field merging or write-back.

This contract is design only and grants no API, UI, schema, resolver, control, runtime, deployment, commit,
rebuild, or activation authority.

## Shared interface

### Inputs

- required, schema-valid `aq.operator-context.v1` with source projection revision/digest;
- optional, independently schema-valid `aq.herdr.presentation.v1` with observation revision/digest;
- closed web presentation policy: visible budgets, supported versions, accessibility/reduced-motion settings,
  and low-cardinality refresh-age buckets;
- current authenticated actor context only when rendering action availability; actor context is never copied
  into either projection and does not authorize through this contract.

### Output

The API returns a closed read-only command-center envelope containing the two unmodified versioned
projections or explicit per-projection unavailability, plus a derived join summary:

- operator-context schema version, projection revision/digest, freshness, and source health;
- presentation schema version, observation revision/digest, freshness, and source health;
- bounded mission, work, attention, evidence, learning, and coverage view models preserving source refs;
- bounded presentation-health, layout-drift, pane-role coverage, unmanaged/orphaned/dark/stale/drifted state,
  and reconciliation-age view models;
- explicit join state `match|mismatch|unknown` keyed only by bounded reference tokens;
- stable attention priority, visible budget, overflow, and accessible summary;
- advisory action label/authority/availability only; no executable mutation payload.

The UI renders this envelope without reinterpreting canonical lifecycle or presentation health. It may link
to existing authoritative drill-in and audited action surfaces, subject to contract #4.

### Normative closed read envelope (`aq.web.operator-monitor.v1`)

The API/UI may serialize only this complete, closed envelope; it does not implement a second comparator.
`comparison` is the exact `aq.herdr.comparison.v1` artifact produced solely by contract #5's
`compare_operator_context_to_presentation_v1`, or it is `null` with `comparison_status:unavailable|unknown`.
Every object is `additionalProperties:false`; arrays max at 64 and reference values use `aqref:v1:`.

```text
{schema_version:"aq.web.operator-monitor.v1", envelope_revision:token,
 operator_context:{status:"available|unavailable|invalid", schema_version:"aq.operator-context.v1"|null, projection_revision:token|null, digest:sha256|null, freshness:"fresh|stale|unknown|unavailable", payload:object|null},
 herdr_presentation:{status:"available|unavailable|invalid", schema_version:"aq.herdr.presentation.v1"|null, observation_revision:token|null, digest:sha256|null, freshness:"fresh|stale|unknown|unavailable", payload:contract_5_exact_profile|null},
 comparison_status:"available|unavailable|unknown", comparison:{comparison_schema_version:"aq.herdr.comparison.v1", comparison_revision:token, operator_context_digest:sha256, presentation_digest:sha256, join_state:"match|mismatch|unknown", typed_mismatches:[{operator_path:bounded_path,presentation_path:bounded_path,reason:"missing|stale|conflict|incompatible|unauthorized|unavailable", evidence_refs:[aqref]}], digest:sha256}|null,
 view:{mission_ref:aqref|null, attention_refs:[aqref], visible_count:uint0..64, overflow_count:uint0..65535, accessibility:"standard|keyboard|screen_reader", motion:"full|reduced|unknown"}}
```

`herdr_presentation.payload` is the unchanged schema-valid **exact contract-#5 normative profile**:
`schema_version, observation_revision, generated_at, freshness, source_health, source_digests, configured,
runtime, socket, session, version, protocol, panes, layout, counts, reconciliation, coverage, policy` in
that canonical order and nesting. It is never a field subset, alias, browser-supplied object, or a projection
with a root digest; the outer `digest` binds its canonical bytes. `operator_context.payload` is likewise an
unchanged schema-valid projection object.
If either projection is missing/invalid, its payload and identity fields are null, the other stays visible,
and `comparison_status` cannot be `available`. No web code recomputes, filters, or reclassifies drift.

### Direction

```text
aq.operator-context.v1 ---------> web command-center monitor
aq.herdr.presentation.v1 ------> web command-center monitor
                                  (read-only typed drift join)
```

No dashboard API/UI event writes to either projection or to canonical AQ state through this interface.

## Error behaviour

- One projection missing or invalid: keep the other visible, mark the missing side unavailable/unknown, and
  make join/drift unknown; never copy fields across to manufacture parity.
- Schema/version/digest mismatch: reject only the incompatible object and show explicit degraded state; no
  compatibility defaults.
- Stale cache: display source revision/digest, stale provenance, and age bucket; never label cached data fresh.
- Conflicting work/presentation facts: show mismatch/drift with both bounded evidence references; canonical
  state remains authoritative.
- API/UI budget overflow: deterministic grouping and explicit overflow; safety, review/approval, freshness,
  authority, unknown, and drift cannot be hidden.
- Unsafe content/high-cardinality identifier injection: reject/redact at API serialization and DOM/text
  rendering; never interpolate as HTML, command, URL, path, metric label, log, RAG, or remote payload.
- Fetch/render failure: retain an explicit unavailable panel/card/badge, not a blank field or healthy zero.

Unknown never becomes `0`, `false`, healthy, complete, empty success, or blank `--`.

## Auth and trust requirements

- Both projections are read-only, independently validated, revision/digest bound, and never accepted from
  browser-supplied state.
- Canonical AQ remains lifecycle/review/lease/evidence/release authority; HERDR observation remains
  presentation-health authority only.
- The browser cannot raise authority through role labels, terminal content, pane state, recommendations, or
  client-side controls.
- Every eventual action uses contract #4 and revalidates current actor identity/authority server-side.
- Drill-ins use bounded opaque reference tokens mapped by an authorized server-side surface; raw paths,
  receipts, prompts, outputs, credentials, provider/session IDs, and reasoning are excluded.
- Metrics are low-cardinality and must not label task/provider/session identities.

## Acceptance vectors

1. HERDR, TUI, and web show the same operator-context schema version, revision/digest, priority order, and
   work/evidence reference semantics.
2. The web API preserves two separate projections and an explicit typed join; it never merges authority.
3. Missing presentation health does not erase canonical context, and missing canonical context does not make
   presentation health equivalent to work truth.
4. Missing/stale/malformed/conflicting data stays visible unknown/degraded/drifted, never healthy zero.
5. `done` without independent receipt renders `needs_review`/drift even if a pane appears complete.
6. A child-controlled session explains `through_parent` and links the bounded parent context.
7. Recommendations show why/evidence/required authority/availability but cannot execute through the
   projection endpoint.
8. Prompt/output/secret/path/identity/reasoning/terminal/argv/environment injection cannot cross API, DOM,
   logs, metrics, RAG, links, or remote transport.
9. Keyboard-only, narrow viewport, screen-reader, and reduced-motion modes preserve mission, highest
   attention, freshness, authority, unknown, and drift.
10. A live-card contract requires explicit presentation freshness/reconciliation age; blank `--` is a test
    failure, not a cosmetic fallback.

## Explicit exclusions

- API route, frontend, component, schema, resolver, cache, or browser-test implementation;
- dashboard actions or control implementation;
- HERDR inspection, runtime, socket, session, pane, layout, or reconciliation implementation;
- H1 baseline repair, acceptance, staging, commit, rebuild, or activation;
- H3 brokered agent PTYs and all agent launch/execution paths.

## Sign-off

- [ ] Claude: PENDING — independent orchestrator review required.
- [x] Codex: AGREED — design only; two-projection read-only web composition; no implementation/runtime authority.
- [ ] Owner: PENDING — freeze required before any later implementation request.

PREPARED_ONLY; independent review required; implementation gated on accepted H1 + separate authorization.
