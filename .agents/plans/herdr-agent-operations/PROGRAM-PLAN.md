---
doc_type: plan
id: herdr-agent-operations-program
title: Herdr Agent Operations Program Plan
status: active
owner: codex-orchestrator
date: 2026-08-08
parent_prd: herdr-agent-operations
---

# Herdr Agent Operations program plan

## Current evidence

- The repository contains cmux-style comments and matrix/focus rendering in
  `scripts/ai/aq-tui-dashboard`, but no cmux runtime integration or cutover.
- Herdr upstream provides a Rust binary, persistent PTY server, agent state,
  CLI/socket APIs, remote attach, Nix flake, and Claude/Codex/Antigravity
  integrations.
- Its control API is intentionally mutation-capable, so direct agent access
  conflicts with AQ-OS zero-trust and single-authority invariants.
- The existing AQ TUI and web dashboard remain required measurement surfaces;
  Herdr hosts/augments them rather than replacing them.

## Sequence

### H0 — deny-by-default intake

Pin one stable Herdr release and upstream commit/NAR hash. Review Apache-2.0
license, Cargo lock/SBOM, Nix flake, socket protocol, plugin/integration hooks,
update and remote-manifest behavior, persistence, logs, and restore semantics.
Land closed layout/role projection contracts and adversarial fixtures. Candidate
remains `proposed` until independent flagship acceptance.

### H1 — package and inert user session

Add the pinned flake/package and a default-OFF Home Manager or user-systemd
configuration for named session `aq-os`. Generate config with update checks,
manifest checks, plugins, remote bootstrap, and agent restore disabled. Add a
read-only `aq-herdr status` facade and exact rollback. No pane/process launch.

### H2 — presentation projection and Service Coverage

Build deterministic desired layout from canonical AQ records. Reconcile only
workspace/tab/pane labels and harmless monitor commands through an allowlist.
Expose configured/running/socket/protocol/version/session/pane-role/drift data
to Phase-0, `aq-tui-dashboard`, and the web command center. Unknown or manually
created panes are visible as unmanaged; they are not killed automatically.

### H3 — confined executor adoption

Integrate only after the host dispatch broker and execution-cell boundary are
active. Broker starts admitted task argv in a Herdr PTY while the child cell
hides the Herdr socket/config/binary and scrubs `HERDR_*`. Test attempts to send
input, spawn siblings, close panes, install plugins, or stop the server from
inside every agent role. All must deny. Canonical lifecycle and cancellation
remain registry/lease/fence driven.

### H4 — dogfood, remote attach, and cmux retirement

Run a bounded soak across orchestrator, flagship reasoning, implementer,
reviewer, researcher, and local modalities. Validate detach/reattach, server and
system restart reconstruction, narrow terminals, and SSH attach without remote
bootstrap. After references are scanned and docs updated, rename cmux-specific
comments to generic agent-matrix terminology; archive, never delete, obsolete
artifacts under the repository SOP.

## Immediate H0 inventory

1. `config/agent-capability-intake-candidates.json`
2. `.agent/PROJECT-HERDR-AGENT-OPERATIONS-PRD.md`
3. `.agents/plans/herdr-agent-operations/PROGRAM-PLAN.md`
4. `.agents/plans/herdr-agent-operations/H0-INTAKE-REPORT.md`
5. `scripts/testing/test-herdr-intake-contract.py`
6. `scripts/testing/test-capability-intake.py`
7. `ai-stack/mcp-servers/shared/tool_security_auditor.py`

No flake lock, package, binary, config, service, socket, plugin, integration,
agent skill, remote attach, process launch, deployment, or dashboard change is
authorized by H0.
