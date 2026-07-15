# Local Inference Contract L2B-A — Shadow Transport Kernel Plan

**Status:** APPROVED — independent plan review passed
**Owner:** Codex orchestrator
**Parent:** `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
**Prerequisite:** L2A commit `499e5a26`
**Boundary:** shadow fixtures only; no live transport, lifecycle, writer, or traffic adoption

## Decision and phase split

L2B is split because payload normalization and production adoption have different failure domains.

- **L2B-A (this slice):** strict transport policy/schema, injected canonical payload-builder adapter,
  bounded incremental JSON/SSE observation decoder, deterministic evidence, Phase-0 coverage, and
  fixture-only dashboard health. New modules are not imported by live inference paths.
- **L2B-B (fresh authorization):** outbound-header hardening, behavior-preserving live payload/parser
  adoption, and removal of `dispatch.py`'s production inline builder fallback.
- **L3:** delegation lifecycle adoption. C0.3 lifecycle ratification is required first.
- **L4:** `aq-chat` thin-client migration. L2B-A does not replace its fast path.

Descriptor-bound path enforcement is not a prerequisite for no-tool L2B-A. It remains mandatory
before any write-capable L3/L4 adoption.

## Retained declarations and current facts

- `local-orchestrator` remains the kernel-declared front door.
- The per-authority consolidation direction remains retained but unratified.
- `build_llama_payload()` in `ai-stack/mcp-servers/shared/llm_config.py` is the payload SSOT.
- Caller profile/model/role/priority/run headers and body fields are untrusted claims.
- The switchboard currently forwards overly broad inbound headers, can default unknown profiles, and
  mutates payloads. These are L2B-B blockers, not behavior to reproduce as authoritative.
- Existing stream parsers silently skip malformed JSON and decode split UTF-8 with replacement.
- Ralph is explicitly unavailable in L2B-A: `dispatch.py` calls nonexistent synchronous `/task`, while
  the service exposes authenticated queued `POST /tasks` and `/tasks/{task_id}`.
- The v1 inference event schema has no content-delta event type, and the v1 result requires observed
  usage/timing. L2B-A therefore emits internal transport observations. It creates a v1 terminal
  candidate only when all required lifecycle metadata is injected; it never fabricates zeros.

## Exact implementation inventory

Only these 14 implementation files are authorized after plan approval:

1. `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
2. `.agent/PROJECT-LOCAL-INFERENCE-L2B-A-PLAN.md`
3. `config/schemas/local-inference-transport.schema.json`
4. `config/schemas/local-inference-transport-policy.schema.json`
5. `config/local-inference-transport-policy.json`
6. `scripts/ai/lib/local_inference_transport.py`
7. `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`
8. `scripts/testing/fixtures/local-inference-l2b-stream-golden.json`
9. `scripts/testing/test-local-inference-l2b.py`
10. `scripts/testing/harness_qa/phases/phase0.py`
11. `scripts/ai/_aq-qa-bash`
12. `config/validation-check-registry.json`
13. `dashboard/backend/api/routes/aistack.py`
14. `assets/dashboard.js`

Operational collaboration projections (`PENDING.json`, `RESUME.json`, `PULSE.log`, `HANDOFF.md`) may
be updated but are not implementation inventory.

No edit or live import is authorized in `aq-chat`, `delegate-to-local`, `dispatch.py`,
`shared/llm_config.py`, coordinator, local runtime, switchboard, Ralph, Nix, environment/port
contracts, lifecycle stores, telemetry writers, service units, or deployment files.

Inventory item 1 is limited to changing the parent PRD delivery section from one broad L2B to the
L2B-A/L2B-B split and recording the internal-observation/non-authoritative-candidate boundary. It may
not change the system intent, retained declarations, L3/L4 ownership, or acceptance requirements.

## Required behavior

### Strict transport policy

- A committed, schema-validated policy freezes adapter/digest versions, supported shadow targets,
  target-specific outbound header allowlists, body-field allowlists, and byte/event/stream limits.
- The policy contains no model ID, endpoint URL, secret, credential, port, runtime profile cap, or
  lifecycle state. Profile/model/capability facts are injected immutable snapshots.
- Target status is explicit: direct llama, switchboard, coordinator, and local-runtime observations
  are registered; Ralph is `unavailable_route_contract`; unknown targets fail typed.
- Header allowlists are exact per target. Untrusted ingress headers are represented as an ordered
  array of `{name,value}` pairs, never a mapping, so duplicates remain observable before validation.
- Every header name must be a nonempty ASCII HTTP token. Reject case-insensitive duplicates and any
  forbidden or non-allowlisted header; do not silently strip it. Canonical output headers are a
  lowercase-name sorted array generated only from resolved/injected facts.

### Injected canonical payload adapter

- Accept separately: the L2A resolved plan/context, trusted profile/model/revision/capability facts,
  transport policy, and an injected `build_llama_payload` callable.
- Reject mismatched profile/model/revision, unknown fields, unavailable profiles, forged model/role,
  caller-controlled routing/priority/run headers, and conflicts between request and trusted facts.
- Call the injected builder exactly once. Reject builder output containing fields outside the policy
  allowlist or values that widen budgets, tools, cache behavior, thinking configuration, streaming,
  or target capabilities.
- Freeze the exact builder call: deep-copied L2A prepared messages plus explicit `max_tokens`,
  `temperature`, `stream`, `role`, and `task_type`; only policy-enumerated `stop`, `tools`,
  `tool_choice`, `frequency_penalty`, `model`, and `response_format` extras may be supplied. Caller
  dictionaries are never expanded into `**extra`.
- Trusted facts include the expected canonical-builder revision and SHA-256 of
  `shared/llm_config.py`; mismatch fails before invocation. Treat the builder and its return as
  untrusted: prove it was called once, did not mutate any input, and returned exactly allowed values,
  not merely allowed field names.
- Actual-SSOT golden tests run in a subprocess with a minimal declared environment and explicit
  values for every payload-affecting variable, including `FABLE_PARITY` and `LLAMA_MAX_TOKENS`.
  Vectors freeze both approved parity-injection states where relevant. Ambient host environment may
  not change canonical bytes; an undeclared payload-affecting variable is a fixture failure.
- Emit `response_format={"type":"json_object"}` only when the artifact is JSON and trusted transport
  capability says supported. Exact-parse final JSON remains mandatory.
- Local outbound headers are built from an allowlist and never include inbound Authorization,
  cookies, API keys, proxy credentials, or arbitrary `X-*` headers. L2B-A never mints remote auth.
- Bind profile/model to the injected snapshot revision. A response model is observed metadata only.
- Produce domain-separated, versioned SHA-256 semantic and exact canonical-wire digests. Digests are
  provenance, never authorization, identity, or lifecycle idempotency.

### Explicit buffered JSON and incremental SSE decoder modes

- Decoder mode is mandatory and enum-closed: `buffered_json` or `openai_sse`; never sniff content.
- `buffered_json` consumes at most the inclusive `max_total_bytes`, decodes strict UTF-8 at EOF, and
  accepts exactly one JSON document with only JSON whitespace around it. It rejects prose, fences,
  trailing data, duplicate keys, non-finite numbers, empty input, and any `[DONE]` marker. Successful
  EOF is its terminal framing; it does not require or synthesize `[DONE]`.
- `openai_sse` consumes bytes incrementally with one strict incremental UTF-8 decoder. Line endings
  `CR`, `LF`, and `CRLF` are recognized across chunk boundaries. Empty lines dispatch an event;
  `:` comment lines are ignored semantically but count toward byte/line limits. Only `data:` fields
  are accepted; consecutive data fields in one event join with `\n`. Unknown SSE fields, data-less
  non-comment field blocks, malformed field syntax, or invalid UTF-8 fail typed. A comment-only
  heartbeat block and its blank separator are ignored and do not increment the JSON-event count,
  while all of their bytes and lines still count toward limits. Multiple frames per feed are allowed.
- The SSE terminal marker is an event whose joined data is exactly `[DONE]`. Exactly one is required
  for a success stream; the upstream-error exception is defined below. EOF before a required marker,
  a duplicate marker, or any bytes after its terminating blank line fail typed. The marker may be
  split arbitrarily across input chunks.
- `max_line_bytes`, `max_event_bytes`, `max_events`, and `max_total_bytes` are inclusive byte limits,
  measured before UTF-8 decoding and checked before buffer growth. Code-point counts are never used
  for transport limits. Unknown upstream JSON fields are rejected unless explicitly present in the
  closed observation schema.
- Both modes support usage-only `choices=[]`, fragmented tool-call arguments, and finish reasons.
- Never use replacement decoding, silently skip malformed JSON, accept prose/fences as JSON, or hide
  a malformed event. Emit stable typed errors for invalid UTF-8, malformed JSON, truncated EOF,
  missing/duplicate `[DONE]`, duplicate/conflicting usage, oversized input, post-terminal bytes, and
  invalid tool-call fragments.
- Normalize only internal observations: `content`, `usage`, `tool_call`, `finish`, `upstream_error`,
  `done`,
  and `cancelled`. Observations use monotonic sequence and exact request/run/trace identity injected
  by the fixture; they do not claim lifecycle ownership or write events.
- An upstream OpenAI error object becomes a bounded `upstream_error` observation. Decoder/framing/
  schema faults raise a typed parser fault and never synthesize an observation or lifecycle event.
- Usage is one terminal cumulative snapshot, not a delta. One usage observation is allowed; even an
  identical duplicate rejects. It must not precede content/tool data and no content/tool/finish may
  follow it. Missing usage remains unknown.
- Every tool-call fragment requires a stable nonnegative numeric index. The first fragment for an
  index establishes nonempty ID, type, and function name; later continuation fragments may contain
  only index plus function arguments, but any repeated identity field must match exactly. Arguments
  concatenate in arrival order and must exact-parse as one JSON object before finish. Emit exactly one
  completed tool observation per index, ordered by numeric index regardless of interleaving. Identity
  drift, duplicate completion, incomplete arguments, or fragments after finish fail typed.
- Exactly one finish reason is allowed and it follows all content/tool fragments. `done` follows
  finish and optional usage according to the mode framing; no observation follows `done`.
- Success and upstream-error are disjoint terminal states. In `buffered_json`, an OpenAI error object
  emits exactly one `upstream_error` at successful EOF and permits no content, tool, usage, finish,
  done, or terminal candidate. In `openai_sse`, an error data event emits one terminal
  `upstream_error`; afterward only its blank separator, comments, and either immediate EOF or one
  `[DONE]` framing event are accepted. An error stream does not emit `done`, does not require
  `[DONE]`, and cannot emit finish/usage/content/tool or a terminal candidate. Success SSE still
  requires exactly one `[DONE]`. Any later conflicting data or second error is a typed parser fault.
- Streamed and buffered decoding reconstruct byte-equivalent content, tool arguments, observed usage,
  finish reason, and output digest. Missing usage remains `unknown`, never estimated or zero.
- Cancellation is idempotent before terminal: the first call emits exactly one `cancelled`
  observation, repeated calls emit nothing, later bytes reject, and no finish/done/completed candidate
  is produced. Cancellation after done rejects as already terminal. Upstream client ownership/closure
  and `CancelledError` propagation are L2B-B acceptance gates.

### Closed schema roots

- `local-inference-transport.schema.json` has a closed top-level `oneOf` whose `$defs` independently
  close: trusted snapshot, ordered untrusted header claim, canonical header/payload output, transport
  plan, observation, decode summary, typed parser fault, and v1 candidate wrapper.
- The candidate wrapper requires `authoritative:false` and `candidate_kind:"terminal_candidate"`.
  A bare schema-valid v1 `completed` event/result is never a top-level L2B transport document.
- `local-inference-transport-policy.schema.json` closes every policy and limit object. Both schemas
  prohibit external references and validate with Draft 2020-12 plus format checking.

### Result/event boundary

- The decoder does not misuse repeated `started` events for content deltas and does not alter v1
  event/result schemas in place.
- A separate pure assembler may create a v1 terminal event/result candidate only when resolved plan,
  usage, timings, provenance, identity, and terminal evidence are injected and schema-valid.
- Absent or conflicting mandatory evidence fails typed `malformed_result`; no values are invented.

### Golden evidence and adoption guard

- Payload vectors freeze observed source shapes for dispatch direct, embedded-assist, `aq-chat` fast
  path, coordinator route/delegate/workflow client, local runtime, switchboard, and unavailable Ralph.
  Equivalent eligible shapes normalize to pinned canonical bytes; unsafe facts fail typed.
- Stream vectors cover buffered JSON and adversarial SSE byte splits, Unicode, CRLF/comments,
  usage-only final chunks, tool-call fragments, cancellation, malformed/truncated/oversized streams,
  missing/duplicate terminal markers, and strict JSON final artifacts.
- Header-confusion vectors include case variants, duplicates, forged role/priority/profile/model/run
  identity, Authorization/cookie/API-key canaries, and arbitrary `X-*` headers.
- A builder spy proves exactly one canonical-builder call and rejects extra-field smuggling.
- The trusted snapshot binds the SHA-256 of the exact emitted system message and the complete
  `chat_template_kwargs` object. The adapter rejects authority-text mutation, thinking enablement,
  and thinking-budget drift even when the mutated values remain schema-valid and allowlisted.
- Static guards pin that no live inference surface imports L2B modules and no live surface hash is
  changed. No network call, service reload, deployment, store, writer, or traffic cutover occurs.
- A committed fixture manifest lists the exact repository-relative path and SHA-256 for every frozen
  live source: `scripts/ai/aq-chat`, `scripts/ai/lib/dispatch.py`, shared `llm_config.py`, coordinator
  `core/route_handler.py`, `core/llm_client.py`, `extensions/ai_coordinator_handlers.py`, local runtime,
  switchboard, and Ralph server. Tests recompute every hash and also scan these exact paths for imports
  of `local_inference_transport`; missing, added, or changed manifest entries fail closed.
- Every source-shape record carries executable, bounded literal predicates. Validation executes all
  predicates against the hash-pinned live source; descriptive labels alone cannot satisfy parity.

### Phase-0 and dashboard health

- Register one identical new Phase-0 ID in Python and Bash and focused-CI triggers for all 14 files.
- The dashboard may use the sole bounded runtime import of the new module for committed-fixture health.
- Dashboard health is cached by candidate asset digest. Cache misses execute synchronous file/schema
  work with `asyncio.to_thread` from `/harness/overview` (or consume a precomputed immutable result),
  never on the async event loop. Request handling may not run randomized/adversarial vectors.
- Health vector counts and parity are derived by executing every committed fixture during bounded
  validation; fixture-declared counters are not trusted. Actual-builder vectors are structurally
  decoded and recheck their authority digest and thinking object, while source-shape predicates run
  against the hash-pinned source. Cache entries contain only sanitized health.
- Expose only policy/schema status, adapter/digest versions, target decisions, payload/stream vector
  counts, parity state, digest/freshness, shadow mode, and stable reason code.
- Never expose prompts, output, message content, secrets, raw headers, regexes, exception strings,
  model credentials, or telemetry-derived user data. Missing/malformed assets degrade fail-closed.

## Acceptance gates

1. Both new schemas are closed Draft 2020-12 schemas with no external references; policy validates.
2. Payload/header/profile/model/budget/tool mutation matrices fail with stable typed reasons.
3. Injected canonical builder is called exactly once and eligible vectors match pinned canonical bytes.
4. Randomized stream byte splitting and buffered input reconstruct identically across every fixture.
5. Malformed/truncated/duplicate/oversized/post-terminal inputs fail closed; no silent recovery.
6. Missing usage/timing cannot produce a v1 terminal result; complete injected evidence can.
7. Strict JSON capability cross-product and final exact parse pass without leaking wire intent to an
   unsupported target.
8. Static adoption guard proves zero live imports/edits/cutover and Ralph stays explicitly unavailable.
9. Focused L2B-A, L2A, and L1A suites pass; Phase 0 and Tier 0 pass.
10. Dashboard health is fixture-only, bounded, fail-closed, and contains no sensitive fields.
11. Independent reviewer returns APPROVE against the exact staged inventory before commit.

## Stop conditions

- Any active slice owns an implementation file or an authorized file has unrelated unstaged edits.
- A plan requires trusting caller headers/body route claims or forwarding inbound credentials.
- Unknown/unavailable profiles would fall through to `default`.
- Existing permissive SSE recovery must be retained for parity.
- Builder normalization requires changing ambient production behavior in L2B-A.
- Transport observations cannot preserve exact provenance across byte boundaries.
- Acceptance would fabricate usage, timing, completion, lifecycle, authorization, or idempotency.
- Scope expands to live imports, HTTP, auth minting, lifecycle ownership, cancellation of live work,
  telemetry writes, service changes, deployment, L3 delegation adoption, or L4 chat migration.

## L2B-B entry conditions

L2B-B requires fresh authorization, an exact live-file inventory, outbound-header hardening, explicit
profile failure behavior, async resource/cancellation ownership, baseline payload/stream parity, and
rollback. It may remove the dispatch fallback and adopt payload/parser adapters only after those gates.
Ralph needs its own corrected authenticated queued adapter plan; it is not silently repaired by L2B-A.
