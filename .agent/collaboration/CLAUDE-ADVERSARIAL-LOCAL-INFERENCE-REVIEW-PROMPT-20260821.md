---
doc_type: collaboration-brief
id: claude-adversarial-local-inference-review-20260821
title: Claude adversarial AQ-OS and local-inference configuration review
status: active
owner: codex-orchestrator
date: 2026-08-21
---

# Role

Act as the independent flagship adversarial reviewer. Codex is orchestrator. Do not edit, stage,
commit, dispatch other agents, deploy, rebuild, or activate anything. Review the current worktree and
HEAD `9236887c`, including uncommitted forward repairs. Record the exact HEAD and diff hash you saw.

# Objective

Determine whether the recent AQ-OS harness, workflow, loop, role, and configuration changes are safe,
operable, measurable, and aligned with strong software/project-management practice while fully using
the capabilities built for local inference. Find both unsafe behavior and dark/unused capability.

# Required coverage

1. Recent range `cc63ac57..HEAD`, especially provisional commits `5c3e7a1d`, `962e802f`,
   `8e488ff7`, `70e3eb16`, `e8599514`, and `72c069ad`, plus current forward repairs.
2. Role separation, commit-forward provisional policy, async review queue, terminal dispositions,
   stale PENDING/RESUME/claim reconciliation, WIP/latency, and main-branch integration safety.
3. Local profiles and routing: switchboard profiles, direct/agent/background/batch classes,
   task eligibility, fallbacks, model/config SSOT, token/context budgets, thermal/slot controls.
4. Capability use: tool registry and leases, skills/plugins, MCP/coordinator surfaces, RAG/AIDB/memory,
   context assembly, record/replay, prompt queues, edit tools, telemetry/traces, dashboard and aq-qa.
5. Isolation/security: tool arguments, replay safety/fidelity, credentials, workspace boundaries,
   AppArmor/systemd confinement, Playwright MCP admission truth, least privilege, activation gates.
6. Dogfood readiness: honest success/no-change/failure receipts, deterministic corpus, promotion
   thresholds, unattended stop conditions, no self-review/self-commit, and morning evidence.

# Known claims to verify, not trust

- Generic mocked tool outputs can cause Turn-2 replay prompt drift.
- Playwright MCP is cataloged enabled/accepted although its root systemd confinement rule was removed.
- Moving integration tests out of pre-commit may be unsafe until a required async CI lane exists.
- Independent review rejected Cluster 5 data mutation and Cluster 6 fail-open gate; forward repairs are
  present in the worktree and need fresh-subject scrutiny.

# Output contract

Return a concise Markdown review with:

- terminal disposition: `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`;
- BLOCKER/HIGH/MEDIUM findings, each with exact file/line evidence, consequence, and one bounded next
  implementation slice;
- a capability-utilization matrix: capability, intended local-agent use, current reachable proof,
  dark/broken state, and recommended gate;
- explicit agreements/disagreements with the known claims;
- the smallest ordered implementation queue before first dogfood, and what may safely wait until after;
- no same-slice revision loop and no generic documentation-only recommendations.
