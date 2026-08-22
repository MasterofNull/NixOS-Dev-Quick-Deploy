---
doc_type: prd
id: aqos-local-inference-adversarial-hardening
title: AQ-OS Local-Inference Adversarial Hardening PRD
status: active
owner: codex-orchestrator
phase: "2026-08-21 adversarial hardening"
priority: critical
---

# Outcome

Make the current AQ-OS and local-inference ecosystem safe, measurable, capability-complete, and
eligible for bounded unattended dogfood. Remote flagship agents independently review and design;
local models execute only measured, declared, patch-producing tasks after activation gates pass.

# Evidence that opened this program

- Claude Opus review `claude-20260821-215542-ibx1c3`: `PLAN_BLOCKED` for unattended dogfood.
- Codex live audit: invalid partial-dimension model promotion and an intentional AppArmor attachment
  bypass in the running llama service.
- Independent reviewer: unsafe provisional bytes landed on `main`; Playwright admission overstates
  confinement; safe multi-turn replay is not faithful.
- Current stabilization base: `aq-qa 0 --machine` PASS and Tier-0 36/36 PASS after forward repairs.

# Product and engineering requirements

1. A local lane is eligible only after a bounded real completion probe, not component liveness alone.
2. Promotion requires all declared dimensions, evidence-bound eligibility gates, minimum samples, and
   consecutive full runs. Partial runs are diagnostic-only.
3. Every safety-critical local-inference contract and its gate-self-test runs in a mandatory lane.
4. High-risk capabilities report their actual runtime enforcement. Missing confinement blocks launch.
5. The primary llama service must not evade AppArmor attachment; systemd and MAC controls are additive.
6. Provisional work is isolated from the integration branch until an independent terminal disposition.
7. Safe replay reproduces recorded bounded tool outputs for multi-turn fidelity without executing tools.
8. Local agents can reach the intended tools, leases, skills, MCP/RAG/memory/context, telemetry, and
   queues; dark capabilities are either wired with observable evidence or explicitly unavailable.
9. Dogfood results distinguish success, no-change, validation failure, timeout, thermal deferral,
   scope rejection, and runner error. No local self-review or self-commit grants promotion.

# Delivery gates

- Two-pass independent adversarial review: Codex plus Claude; exact fresh subject on pass two.
- Focused tests, `aq-qa 0 --machine`, and full Tier-0.
- Nix evaluation/build before rebuild; live positive inference and negative confinement probes after.
- Dashboard and aq-qa parity for new health/telemetry fields.
- One atomic commit per slice. Findings move forward; no same-slice revision loop.

# Explicit exclusions

- No model swap based on the stale PROMOTED sentinel.
- No unattended queue activation before the completion-probe and promotion contracts pass.
- No unrestricted browser egress, destructive local tools, external-account actions, or local self-merge.
- No claim that Codex plugins are natively available to local models; project skills and approved MCP
  capabilities must be projected through their own registries and tool contracts.

# Terminal definition

This current hardening increment is complete only when pass-two review is not `PLAN_BLOCKED`, all
activation blockers are closed or explicitly unavailable, the promotion sentinel is evidence-valid,
and a bounded dogfood corpus produces an observable scorecard without false success.
