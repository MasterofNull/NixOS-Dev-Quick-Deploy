# L2A Plan — Canonical Request, Context, and Policy Shadow Kernel

Status: AUTHORIZED — INDEPENDENT PLAN REVIEW REQUIRED BEFORE IMPLEMENTATION
Owner authorization: 2026-07-13 — proceed with the next local-inference L2 unless a prerequisite
phase is required.
Parent PRD: `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
L1A baseline: commit `0c171504`

## Prerequisite verdict and outcome

No separate implementation phase is required before L2. L2 begins with this L2A shadow slice and an
internal L2.0 scope freeze. L2A adds a deterministic canonical builder, caller/task policy,
context redaction/compaction, and offline parity evidence without importing the new modules from any
live caller or execution path.

The PRD sequencing ambiguity is resolved as follows:

- **L2A:** canonical request/context/policy shadow kernel (this slice);
- **L2B:** transport, event, and raw-llama payload normalization, shadow-first and separately authorized;
- **L3/L4:** live delegation and `aq-chat` adoption after authority, security, parity, and rollback gates.

C0.3 ratification is not a prerequisite for this no-writer/no-cutover slice. It is a prerequisite
before lifecycle authority moves. Descriptor-bound path enforcement and adversarial symlink/rename
tests are prerequisites before any live write-capable adoption.

## Frozen decisions

- Retain `local-orchestrator` as the kernel-declared front door.
- Retain the tracked per-authority consolidation direction without ratifying a shared lifecycle spine.
- Treat caller `role`, `agent_type`, `human_gate`, model class, profile, priority, prompt prose, and
  profile-card instructions as untrusted request data. Only injected trusted facts can assign them.
- Keep contract version `1.0`; L2A must not make an incompatible wire-schema change.
- `config/local-inference-policy.json` governs only shadow caller-tier, task, context, strict-output,
  and transition policy. It must not duplicate model identifiers or live profile caps. Profile
  realization/caps enter the pure resolver as an injected, immutable snapshot.
- `local-coding` is `conflicted_unavailable` in the shadow policy until the live switchboard-local
  realization and the EDGE/unprovisioned routing declaration are adjudicated.
- `ralph` is an execution mode, not an available profile, in L2A. A request that names it as a profile
  fails typed; the existing v1 schema enum is retained for compatibility and tested as unavailable.
- Legacy `default` remains outside the v1 local-inference profile contract and is not silently selected.
- `local-tool-calling` is read-only in target shadow policy absent a verified approval and an
  authority-issued lease surviving the full L1A intersection. Profile-card prose grants nothing.
- Redaction and compaction are pure: no filesystem, environment, clock, network, logging, model,
  lifecycle, telemetry, or subprocess effects. Reports contain rule IDs and digests, never secrets.
- Strict JSON means exact JSON only. L2A may describe `response_format` intent for a later transport
  adapter, but it rejects prose/fences, duplicate keys, and non-finite values rather than extracting.

## Exact implementation inventory

1. `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
2. `.agent/PROJECT-LOCAL-INFERENCE-L2A-PLAN.md`
3. `config/schemas/local-inference-policy.schema.json`
4. `config/local-inference-policy.json`
5. `scripts/ai/lib/local_inference_context.py`
6. `scripts/ai/lib/local_inference_policy.py`
7. `scripts/testing/fixtures/local-inference-l2a-golden.json`
8. `scripts/testing/test-local-inference-l2a.py`
9. `scripts/testing/harness_qa/phases/phase0.py`
10. `scripts/ai/_aq-qa-bash`
11. `config/validation-check-registry.json`
12. `dashboard/backend/api/routes/aistack.py`
13. `assets/dashboard.js`

No other schema, contract-v1 module, live caller, dispatch, coordinator, switchboard, Ralph, Nix,
environment, port, telemetry, database, lifecycle, tool-execution, or deployment file is authorized.

## Required behavior

### Pure context adapter

- Validate message ordering before compaction: at most one leading system message; assistant tool
  calls and tool results use a unique, adjacent matching `call_id`; orphan, mismatch, duplicate, and
  incomplete pairs fail typed.
- Recursively normalize text to NFC.
- Redact configured credential/private-key/PII rule classes using bounded deterministic patterns.
  Replacements contain only `rule_id` and SHA-256 digest. Redaction of required system context blocks.
- Preserve the system message, the newest complete assistant/tool pair, and newest messages fitting
  the effective character budget. Replace evicted turns with one deterministic digest summary placed
  immediately after the leading system message, or first when no system message exists. The budget is
  the sum of NFC-normalized Unicode code points in retained message contents plus the summary content;
  JSON envelope/key overhead is excluded. Protected messages and tool pairs are never partially
  truncated. If the protected set plus required summary cannot fit, fail with the stable typed reason
  `context_budget_mandatory_overflow`.
- Be idempotent and byte-deterministic across repeat runs and canonically equivalent Unicode.
- For JSON artifacts, add an exact JSON-only contract descriptor and expose a transport-neutral
  `response_format={"type":"json_object"}` intent only when support is injected as true. This is
  shadow-only internal context metadata, excluded from v1 request and resolved-plan canonical bytes,
  and statically prohibited from reaching any transport until L2B.

### Pure policy resolver

- Strictly validate the policy JSON against the offline Draft 2020-12 schema.
- Validate all trusted ingress/profile/runtime fact shapes and return stable typed errors instead of
  leaking `KeyError`, regex, JSON, or validator exception text.
- Resolve caller tier from trusted authenticated facts, never `requester.model_class`.
- Enforce task eligibility, maximum side-effect class, lane/mode constraints, and explicit profile
  transition decisions before invoking the L1A resolver.
- Compute effective budgets as the component-wise minimum of request, task, trusted caller tier,
  injected profile cap, and runtime cap. Zero, negative, boolean, absent, and magic-zero values fail.
- Intersect task-policy tools with L1A role, approval, lease, and runtime facts. No prompt/profile text
  can grant write authority.
- Never select `default`, reinterpret Ralph as a profile, or map a conflicted/unavailable profile to
  another capability.

### Golden evidence and operator health

- Golden vectors cover flagship, standard, budget, and deterministic trusted caller tiers and pin
  canonical resolved-plan bytes. Every tier adapter produces a schema-valid request. Equivalent tasks
  resolve identically where the narrower task/profile cap makes tier policy non-binding. A tier
  mutation changes pinned bytes only when it changes an effective decision; mutations to binding task,
  profile, eligibility, authority, or budget policy must break the pinned result. Malformed or forged
  trusted-tier facts always fail typed.
- Negative vectors cover caller-role/priority forgery, unavailable/conflicted profiles, Ralph-as-profile,
  architecture/destructive ineligibility, magic/invalid budgets, wildcard/write authority, malformed
  trusted facts, redaction leakage, required-context block, tool-pair violations, and permissive JSON.
- The existing harness overview gains a bounded `local_inference_l2a` projection labeled
  `shadow_fixture_only`. It reports policy/schema/context versions, caller-tier parity, profile
  decisions, redaction/compaction vector counts, digest/freshness, and a stable reason code.
- Missing, stale, malformed, incomplete, or invented health degrades visibly. No prompt, secret,
  raw message/tool output, regex, file content, or exception text is exposed.
- Phase 0 and Bash register the same new check ID `0.10.38`; focused CI triggers on every behavior and
  dashboard surface in this inventory.
- A static adoption guard proves no live inference caller, transport, router, lifecycle, or tool
  execution surface imports `local_inference_context` or `local_inference_policy` in L2A. The
  dashboard's bounded read-only fixture-health loader is the sole permitted runtime import.

## Acceptance gates

1. Policy schema is offline-strict Draft 2020-12 with closed object boundaries.
2. All four caller tiers produce schema-valid requests and pinned byte-identical plans for the same
   bounded task when tier policy is non-binding. Binding policy mutations change pinned bytes or fail
   typed; non-binding tier substitutions preserve them; malformed/forged trusted-tier facts fail typed.
3. Context redaction and deterministic compaction pass all ordering, leakage, idempotence, NFC, and
   bounded-size vectors.
4. Strict JSON rejects prose, Markdown fences, duplicate keys, and non-finite values.
5. Every v1 local profile is explicitly registered, conflicted/unavailable, or mode-only; no implicit
   fallback occurs.
6. Live adapter, transport, lifecycle, tool, Nix/env/port, and deployed profile bytes are unchanged.
7. Focused tests, dashboard behavioral coverage, `aq-qa 0 --machine`, security audit of the exact
   candidate, Tier0, and independent review pass.

## Stop conditions

Stop on any live inference/execution import or cutover beyond the bounded dashboard health loader,
new store/writer, contract-v1 incompatible shape, profile/model/cap
duplication, caller-created authority, permissive JSON extraction, secret/raw-content health output,
unadjudicated profile silently mapped to a convenient value, path enforcement claimed from
resolve-then-open logic, overlapping active writer, or inability to preserve unrelated worktree work.

## Deferred and separately authorized

- L2B transport/event/payload adapters and removal of raw llama payload clones.
- Live path/lease enforcement using descriptor-bound operations, no-follow semantics, nearest-existing
  parent checks, atomic creation, and post-mutation revalidation.
- Live `delegate-to-local` and `aq-chat` adoption.
- Lifecycle ownership, cancellation, idempotency, replay, telemetry writers, and legacy retirement.
- Deployment or traffic cutover.
