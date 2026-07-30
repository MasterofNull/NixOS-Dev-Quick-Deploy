# Agent and Model Configuration Parity — Program Plan

**Status:** ACTIVE DESIGN / bounded corrections may proceed independently

## Sequence

1. **C0 — inventory and contract:** closed `AgentDeployment` schema, source
   precedence, pure resolver, provider/modality inventory, golden fixtures.
2. **C1 — Codex effective parity:** declare project roles, validate exact role
   layers, add effective-config doctor, fingerprint live/user/project/Nix
   projections, Phase-0 check, dashboard health.
3. **C2 — remote adapters:** route Claude and Antigravity through one monitored
   lifecycle owner; honor model/token/deadline/retry/parking inputs; typed review
   outputs; eliminate duplicate model maps and unsafe secondary writers.
4. **C3 — local modalities:** enforce eligibility, correct `aq-chat` role
   assignment, converge payload builders, make embedded retrieval non-generative,
   align phase/tool budgets, enrich lifecycle evidence.
5. **C4 — observability and feedback:** config-health API/dashboard/alerts,
   deployment lineage in receipts, quota/capacity parking, catch-up reviews,
   typed learning-candidate propagation.
6. **C5 — canary/adoption/cleanup:** one lane at a time, rollback evidence,
   soak metrics, then retire bypasses and stale projections.

## Immediate bounded slices

- **C1A:** add three named Codex agent declarations to `.codex/config.toml` and
  exact/adversarial tests. No user-config, Nix, runtime, staging, or deployment.
- **C1B:** pure effective-config doctor plus fixtures; no live mutation.
- **C1C:** Phase-0 and dashboard configuration health, satisfying Service
  Coverage; separate authorization because shared surfaces are busy.
- **C2A:** repair Antigravity loop lifecycle/token/deadline/model-lineage
  contract without live provider cutover.
- **C2B:** Claude timeout/retry/parking and TaskRegistry single-writer adoption.
- **C3A:** embedded modality and `aq-chat` role-policy correction design.
- **C3B:** local eligibility/budget/receipt enforcement.

## Current capacity

- Claude: capacity-parked until 02:00 UTC 2026-07-30; catch-up review queued.
- Antigravity/Gemini: two monitored inbox reviews queued.
- Native Codex: available for bounded implementation/review after effective hook
  correction; never self-accept.
- Local: advisory review may run asynchronously and must not gate progress.

## Gates

Each slice requires exact inventory, input hashes, disjoint writer check,
focused validation, explicit external/live exclusions, independent verdict, and
an integration authority before staging or commit. The sole staged C0.3 record
remains untouched.

