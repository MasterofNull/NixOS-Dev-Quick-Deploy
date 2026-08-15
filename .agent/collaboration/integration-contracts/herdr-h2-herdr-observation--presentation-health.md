---
doc_type: reference
id: herdr-h2-herdr-observation--presentation-health
title: Herdr H2 Observation to Presentation Health Integration Contract
status: draft
date: 2026-08-09
parent_prd: herdr-agent-operations
contract_number: 5
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
implementation_authority: false
runtime_authority: false
---

# Integration Contract #5: HERDR observation -> presentation health and drift

## Purpose and boundary

This contract defines `aq.herdr.presentation.v1`, the closed HERDR-runtime observation projection. It
answers whether the presentation layer is configured, reachable, compatible, fresh, and showing the
expected layout. It does not answer what canonical work state is and never mutates TaskRegistry, workflow,
review, lease, evidence, approval, or release state.

The projection flows only from bounded HERDR observation to web monitoring. Contract #5 owns the only
cross-projection comparator, `compare_operator_context_to_presentation_v1`, and its sole output
`aq.herdr.comparison.v1`; neither input projection computes cross-projection drift. This design grants no observer, CLI, socket, pane,
session, runtime, telemetry, web, deployment, commit, rebuild, or activation authority.

## Shared interface

### Inputs

Only already-bounded, read-only HERDR observation facts may enter:

- configured/effective state category;
- runtime/process reachability category, without PID or argv disclosure;
- socket presence/type/ownership/peer/protocol health categories, without raw sensitive paths;
- managed session inventory/health and bounded session reference tokens;
- HERDR version and expected-version compatibility category;
- protocol version and compatibility category;
- managed pane inventory/role/work reference, pane health, and freshness categories;
- expected-layout reference/digest and observed-layout reference/digest;
- last reconciliation result category, observation revision/digest, and reconciliation age bucket.

Raw terminal content, prompts, outputs, reasoning, command history, environment, credentials, provider IDs,
network identity, PIDs, argv, arbitrary paths, and unbounded session/pane/task identifiers are invalid.

### Output: `aq.herdr.presentation.v1` — normative profile

The required root fields, in canonical serialization order, are:

```text
schema_version
observation_revision
generated_at
freshness
source_health
source_digests
configured
runtime
socket
session
version
protocol
panes
layout
counts
reconciliation
coverage
policy
```

Every object boundary and array item is closed (`additionalProperties: false`). Required semantics:

- `schema_version`: constant `aq.herdr.presentation.v1`;
- `freshness`: explicit overall state and bounded observation/reconciliation age buckets;
- `source_health`/`source_digests`: per-observer validity, authorization, revision, and digest state;
- `configured`: declared/effective `enabled|disabled|unknown|unavailable|degraded` categories;
- `runtime`: `healthy|degraded|unavailable|unknown` plus bounded reason/evidence reference;
- `socket`: presence, node/type, ownership/permission, peer, and reachability/health categories; no raw path;
- `session`: expected/observed managed count states, bounded session refs, health, detach/reattach observation,
  and unknown/unmanaged categories;
- `version`: expected/observed bounded version token and `compatible|incompatible|unknown|unavailable`;
- `protocol`: expected/observed bounded protocol token and compatibility/handshake health;
- `panes[]`: bounded pane ref, managed role, bounded work ref, health, freshness, expected/observed state,
  and `observation_delta: match|mismatch|unknown` (only within the presentation projection);
- `layout`: expected and observed revision/digest, `observation_delta: match|mismatch|unknown`, bounded reason/evidence refs;
- `counts`: managed, unmanaged, orphaned, dark, stale, drifted, and unknown counts represented as
  `{state: known|unknown|unavailable, value}` so absence never becomes zero;
- `reconciliation`: last result, last verified revision/digest, age bucket, pending/failed/unknown state,
  and bounded evidence reference;
- `coverage`: observer/pane/layout known-vs-unknown coverage and overflow;
- `policy`: schema/observer/redaction revisions, bounds, age buckets, compatibility policy identifiers, and
  low-cardinality metric contract.

The following is the exact contract-level root/nesting profile. A later JSON Schema must encode it without
renaming, adding, omitting, or aliasing fields. `token` is a bounded opaque token, `digest` a SHA-256 string,
`ref` an `aqref:v1:` token, `state` one of `known|unknown|unavailable|stale|conflict`, `count_state` one
of `known|unknown|unavailable`, and every list max 64. `count_state` is used by every count object only;
it deliberately excludes `stale` and `conflict` so a count's value is either known, unknown, or unavailable.

```text
{schema_version:"aq.herdr.presentation.v1", observation_revision:token, generated_at:bucket,
 freshness:{state:"fresh|stale|unknown|unavailable", observation_age:bucket, reconciliation_age:bucket},
 source_health:[{observer:token, authorization:"authorized|unauthorized|unknown", state:state, reason:token}],
 source_digests:[{observer:token, revision:token, digest:digest}],
 configured:{state:"enabled|disabled|unknown|unavailable|degraded", reason:token},
 runtime:{state:"healthy|degraded|unavailable|unknown", reason:token, evidence_ref:ref|null},
 socket:{state:state, presence:"present|absent|unknown|unavailable", type:"expected|unexpected|unknown", permission:"ok|denied|unknown", peer:"reachable|unreachable|unknown", evidence_ref:ref|null},
 session:{expected_count:{state:count_state,value:uint|null}, observed_count:{state:count_state,value:uint|null}, refs:[{session_ref:ref,health:"healthy|degraded|unknown|unavailable",detach_state:"attached|detached|unknown"}]},
 version:{expected:token|null, observed:token|null, compatibility:"compatible|incompatible|unknown|unavailable"},
 protocol:{expected:token|null, observed:token|null, compatibility:"compatible|incompatible|unknown|unavailable"},
 panes:[{pane_ref:ref,role:token,work_ref:ref|null,health:"healthy|degraded|unknown|unavailable",freshness:"fresh|stale|unknown|unavailable",expected_state:token|null,observed_state:token|null,observation_delta:"match|mismatch|unknown"}],
 layout:{expected_revision:token|null,expected_digest:digest|null,observed_revision:token|null,observed_digest:digest|null,observation_delta:"match|mismatch|unknown",reason:token,evidence_ref:ref|null},
 counts:{managed:{state:count_state,value:uint|null},unmanaged:{state:count_state,value:uint|null},orphaned:{state:count_state,value:uint|null},dark:{state:count_state,value:uint|null},stale:{state:count_state,value:uint|null},drifted:{state:count_state,value:uint|null},unknown:{state:count_state,value:uint|null}},
 reconciliation:{state:"pending|succeeded|failed|unknown|unavailable",last_revision:token|null,last_digest:digest|null,age:bucket,evidence_ref:ref|null},
 coverage:{known:uint,unknown:uint,unavailable:uint,overflow:uint},
 policy:{schema_revision:token,observer_policy_revision:token,redaction_revision:token,bounds_revision:token,age_policy_revision:token,serializer_revision:token,digest_algorithm:"sha256"}}
```

The projection digest is the SHA-256 of canonical serialization of this exact object and therefore is not a
second root field. An unauthorized/missing observer is represented by its `source_health` entry and dependent
field states; no `expected`/`observed` wrapper or root authorization field exists.

### Direction and typed join

```text
bounded HERDR observation -> aq.herdr.presentation.v1 -> web monitor
aq.operator-context.v1 + aq.herdr.presentation.v1 -> `compare_operator_context_to_presentation_v1` -> aq.herdr.comparison.v1
```

`compare_operator_context_to_presentation_v1` accepts only exact schema-valid projection bytes and validates
both schema versions, revisions, and digests before comparison. Its closed output is
`{comparison_schema_version:"aq.herdr.comparison.v1", comparison_revision:token,
operator_context_digest:sha256, presentation_digest:sha256, join_state:"match|mismatch|unknown",
typed_mismatches:[{operator_path:bounded_path,presentation_path:bounded_path,reason:"missing|stale|conflict|incompatible|unauthorized|unavailable",evidence_refs:[aqref]}],digest:sha256}`;
all objects are closed and the mismatch list is max 64. It is the only producer of cross-projection drift.
It cannot update either input, reconcile a layout, create/kill a pane/session, or change canonical state.

## Error behaviour

- Observer unavailable/unauthorized: affected source and fields become unavailable/unknown; counts use
  unknown state, never zero.
- Socket/session/pane/version/protocol fact missing, malformed, stale, or conflicting: preserve the exact
  degraded/unknown dimension and make dependent health and the comparator join unknown or mismatch.
- Expected and observed layout disagree: emit presentation-only `observation_delta` with bounded evidence; do not reconcile.
- Canonical expectation unavailable: presentation health may remain observable, but the comparator join is unknown;
  presentation appearance cannot synthesize canonical truth.
- Version/protocol incompatibility: fail closed, mark observation unusable for dependent fields, and never
  apply compatibility defaults.
- Unsafe content/high-cardinality identity injection: reject/redact before serialization and metrics without
  echoing the input.
- Cached observation: explicitly stale with original observation revision/digest and age bucket; never fresh.
- Observer failure: no last-known observation is presented as current or healthy.

Unknown never becomes `0`, `false`, healthy, compatible, match, empty success, or blank `--`.

## Auth and trust requirements

- Observers are read-only, least-privilege, named, bounded, and unable to call HERDR mutation surfaces.
- `aq.herdr.presentation.v1` is presentation authority only; it is not canonical work, workflow, review,
  lease, evidence, approval, release, action, or reconciliation authority.
- Observation references and digests are authenticated/validated according to the future observer contract;
  terminal content and caller assertions are never trusted as state.
- Web consumers validate exact schema/revision/digest and keep this projection separate from
  `aq.operator-context.v1`.
- Metrics expose low-cardinality states/counts only; session/pane/work/provider identities are not labels.
- Raw prompt/output/terminal/path/socket identity data stays in explicitly authorized drill-in surfaces and
  is excluded from projection, normal logs, metrics, RAG, and remote transport.

## Acceptance vectors

1. Identical normalized observations produce byte-identical projection output and digest.
2. Every output leaf maps to a named observer fact or explicit deterministic derived rule.
3. Missing/malformed/stale/unreadable observations remain visible unknown/degraded; every unknown count is
   structurally distinct from known zero.
4. Pane/session/socket/version/protocol health dimensions fail independently and propagate only to their
   dependent fields.
5. Expected/observed layout mismatch yields `observation_delta` and never triggers reconciliation or canonical mutation.
6. A healthy-looking pane cannot turn canonical `needs_review`, blocked, unknown, or incomplete into done.
7. Unmanaged, orphaned, dark, stale, and drifted counts remain distinguishable, bounded, and evidence-linked.
8. Reconciliation age is explicit; missing or cached reconciliation cannot be presented fresh/successful.
9. Prompt/output/secret/path/identity/reasoning/terminal/argv/environment/provider/session injection cannot
   cross projection, web, logs, metrics, RAG, or remote boundaries.
10. Narrow viewport, keyboard-only, screen-reader, and reduced-motion summaries preserve presentation
    freshness, worst health dimension, compatibility, drift, unknown counts, and reconciliation age.

## Explicit exclusions

- Schema, observer, adapter, projection, telemetry collector, API/UI, or typed-join implementation;
- HERDR CLI/status/doctor/layout invocation, socket access, pane/session/process/runtime use;
- layout planning, execution, reconciliation, control, or canonical-state mutation;
- H1 baseline repair, acceptance, staging, commit, rebuild, or activation;
- H3 brokered agent PTYs and every agent launch/execution path.

## Sign-off

- [ ] Claude: PENDING — independent orchestrator review required.
- [x] Codex: AGREED — design only; presentation-to-web observation flow; no canonical mutation or runtime authority.
- [ ] Owner: PENDING — freeze required before any later implementation request.

PREPARED_ONLY; independent review required; implementation gated on accepted H1 + separate authorization.
