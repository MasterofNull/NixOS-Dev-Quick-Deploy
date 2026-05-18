# Phase 58A — Codex Foundation Plan

## Objective

Create the control-plane foundation that makes future capability expansion repeatable:

- one role model,
- one routing/profile contract,
- one capability lifecycle model,
- one review-gated execution policy,
- one reusable domain-activation template.

## Recommended Workstreams

1. **Instruction-plane convergence**
   - Canonical role matrix
   - Codex first-class instruction surface
   - Regeneration / drift rules for Claude, Gemini, Qwen, switchboard, and docs

2. **Routing-contract normalization**
   - Profile inventory SSOT
   - Role → lane → profile mapping
   - Reconciliation of docs, config, and live switchboard behavior

3. **Trust and review policy**
   - Gemini review-gate artifact and enforcement path
   - Qwen bounded-task eligibility model
   - Approval boundaries for dangerous operations

4. **Capability lifecycle foundation**
   - Registry schema
   - Promotion states
   - Runtime / operator / validation / rollback surfaces

5. **Domain activation template**
   - Domain tag shape
   - Instruction payload
   - Preferred tools / memory namespaces / validation hooks

## Ordered Slices

1. **Slice A — Role Matrix SSOT**
   - Define canonical agent roles and ownership boundaries.
   - No behavior change yet.

2. **Slice B — Routing/Profile Inventory**
   - Reconcile documented, configured, and runtime profiles.
   - Produce one authoritative mapping.

3. **Slice C — Codex Instruction Surface**
   - Add explicit Codex instructions derived from the role matrix.

4. **Slice D — Gemini Review-Gate Contract**
   - Specify artifact, enforcement point, and failure behavior.

5. **Slice E — Qwen Eligibility Contract**
   - Define the bounded task categories Qwen may receive.

6. **Slice F — Capability Lifecycle Schema**
   - Add the machine-readable state model and evidence requirements.

7. **Slice G — Domain Activation Template**
   - Define the reusable bundle future domains instantiate.

## Dependencies

- Existing canonical workflow must remain authoritative.
- Current switchboard/profile behavior must be inspected before changing docs.
- Gemini hardening work should be preserved, not diluted.
- Local-agent coding loop work should remain bounded rather than reframed as general autonomy.

## Risks

| Risk | Mitigation |
|---|---|
| Turning documentation cleanup into architecture theater | Require each slice to unlock a concrete future behavior |
| Over-centralizing everything into one brittle file | Use SSOT + generated projections, not one giant prompt |
| Making review gates purely ceremonial | Define enforceable artifacts and failure paths |
| Prematurely changing runtime behavior | Separate contract slices from behavior slices |
| Overloading Qwen because local is cheap | Keep eligibility explicit and machine-checkable |

## Validation

- Role guidance is consistent across all active agent-facing surfaces.
- Runtime profiles and documentation agree.
- Codex has a first-class instruction target.
- Gemini review policy has a concrete enforcement design.
- Qwen eligibility can be evaluated without human interpretation.
- Capability lifecycle can represent at least: proposed, implemented, validated, candidate, promoted, default, superseded/retired.

## Codex Should Own

- Cross-agent synthesis
- Scope control
- Profile / routing consistency review
- Final acceptance
- Integration quality

## Codex Should Not Own

- Long-form architecture synthesis that Claude is better suited for
- Research sweeps that Gemini can perform faster
- Routine bounded local checks that Qwen can handle
- Unreviewed adoption of Gemini-authored implementation

