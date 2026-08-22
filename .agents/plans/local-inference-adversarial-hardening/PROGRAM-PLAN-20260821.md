---
doc_type: plan
id: aqos-local-inference-adversarial-hardening-plan-20260821
title: AQ-OS Local-Inference Adversarial Hardening Program Plan
status: active
owner: codex-orchestrator
date: 2026-08-21
parent_prd: aqos-local-inference-adversarial-hardening
---

# Forward implementation queue

| Order | Slice | Primary paths | Binary acceptance | Route |
|---|---|---|---|---|
| A0 | Stabilization | parser boundary, harness Tier-0 gate, L2B fixture | Rejected Cluster 5/6 behavior removed; QA/Tier-0 green | complete at `ad579eb3`, `79297100` |
| A1 | Mandatory contract gates | Tier-0 gate and its contract test | L2B, gate-self, and external-capability admission tests cannot be absent/skipped/hung | remote implementer + independent review |
| A2 | Promotion truth | bench runner, focused promotion test | Partial/missing dimensions, missing eligibility evidence, or fewer than two full runs cannot promote | remote implementer; local only runs corpus later |
| A3 | Playwright fail-closed admission | candidate/catalog, wrapper, admission test | Unenforced egress cannot launch or report accepted; negative external-egress proof required for activation | remote implementer + security review |
| A4 | Local completion health | switchboard/API/qa/dashboard/dispatch eligibility | One bounded completion probe and last terminal/breaker evidence gate unattended dispatch | Codex implementation + Claude review |
| A5 | Llama confinement | Nix role, AppArmor/systemd contract tests | Actual executable is confined; inference works; shell/home/external-network denials proven | Codex systems slice + rebuild |
| A6 | Provisional integration isolation | workflow SSOT plus executable commit/integration guard | New provisional subjects cannot land on main; typed receipt controls integration/activation | remote plan, Codex implementation |
| A7 | Faithful multi-turn replay | cassette, replay bench, two-turn golden | Exact recorded tool results reproduce Turn 2 with zero handler side effects | local-eligible only after A4; otherwise remote |
| A8 | Capability reachability | capability catalog, tool/skill/MCP/RAG probes | Every intended local capability has reachable evidence or typed unavailable state | mixed remote/local |
| A9 | Pass-two adversarial review | exact committed range and runtime evidence | Codex and Claude independently return non-blocked disposition or open bounded forward slices | Codex + Claude review |
| A10 | Dogfood/promotion | dogfood runner, corpus, policy, telemetry/dashboard | Honest scorecard and stop conditions; no self-review/commit; promotion thresholds enforced | local execution under remote orchestration |

# Queue safety

- At most one local inference task at a time and five tasks per unattended window.
- No automatic retry after scope drift, missing telemetry, validation failure, critical thermal state,
  or repeated no-change. One retry maximum for a typed transient provider/runtime error.
- Patch-only outputs in declared files; no deploy, activation, commit, foreign diff, or credential access.
- Remote plans are bounded prompts with exact paths and binary acceptance. Local prompt payloads stay
  within the selected profile budget and reference skills by name rather than embedding full skill text.
- Every slice publishes task ID, subject hash, validations, terminal disposition, and next gate.

# Current authority

Repository implementation is authorized for A1-A4 and A6-A8 within exact declared slice ownership.
A5 may edit/evaluate Nix but requires separate rebuild/switch readiness and live activation checkpoint.
A9 is read-only. A10 remains activation-blocked until A1-A9 evidence permits it.

# Execution checkpoint — 2026-08-22

- A1-A4 and A6-A8B are implemented and focused tests pass; A2 promotion evidence is now
  model-artifact-bound, and A8 separates reachable profiles from conditional or quarantined tools.
- A5 repository/Nix closure validation passes and now asserts that enabled llama inference cannot
  evaluate with AppArmor disabled. Its terminal state remains `ACTIVATION_BLOCKED` pending rebuild.
- Tier-0 is 43/44: every repository gate passes; only live QA 0.3.3 reflects the pre-rebuild
  generation. A9 will review this exact combined subject once, with further non-critical findings
  routed forward rather than replayed into the completed slices.
- A10 begins with one bounded, remotely reviewed task after rebuild evidence. Expansion to an
  unattended queue requires measured correctness, not merely a landed edit or healthy capacity.
- Commit `86fc4f8e` preserves the first safe-at-rest reviewed checkpoint. A second independent
  reviewer then found receipt binding, replay confidentiality/totality, and external-account
  authority gaps. These are being completed as A6/A7/A8 forward slices (plus A3 admission
  binding), without reopening or erasing the completed checkpoint.
