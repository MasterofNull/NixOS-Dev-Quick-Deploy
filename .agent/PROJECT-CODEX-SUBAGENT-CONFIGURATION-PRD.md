# Codex Sub-agent Configuration Parity PRD

**Status:** ACTIVE — owner-directed corrective work  
**Upstream:** `.agent/WORKFLOW-CANON.md`,
`docs/architecture/role-matrix.md`,
`.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`  
**Scope:** native Codex sub-agents only; external Claude, Antigravity, and local
lanes remain governed by their existing adapters and the later cross-provider
configuration contract.

## Problem

Every native child parsed a stale user configuration containing the removed
`features.codex_hooks` key. The same effective file trusted `/`, allowing every
filesystem project to load project-scoped Codex configuration. The repository
also had no project-scoped native sub-agent defaults or role-specific agent
files, so implementation and review model/permission choices depended on
interactive convention.

## Required contract

1. The effective and Home Manager-projected Codex configuration uses only
   `features.hooks = true`; deprecated keys fail validation.
2. Trust is explicit per repository. A blanket `/` trust entry is prohibited.
3. Native sub-agents are enabled with at most three concurrent child threads.
4. Economical bounded work defaults to `gpt-5.6-terra` at medium effort.
5. A flagship reviewer uses `gpt-5.6-sol`, high effort, and read-only defaults.
6. Explorer/research work uses `gpt-5.6-terra`, low effort, and read-only
   defaults.
7. Implementers are workspace-write but may not re-scope, self-accept, stage,
   commit, deploy, or route other agents.
8. Parent live sandbox/approval overrides remain authoritative. Agent files may
   narrow permissions, never broaden them.
9. All custom agent files define name, description, and developer instructions.
10. A focused machine-readable test validates the complete project layer.

## Monitoring boundary

Native Codex surfaces expose Active/Done agent threads. AQ dashboard parity is
not falsely claimed by this configuration-only slice. A later C1 slice must
project native thread identity, role, model class, state, elapsed time, and
terminal outcome through the broker/Agent Ops contract without prompt or output
content and without creating a second lifecycle writer.

## Acceptance

- Current `codex features list` reports stable `hooks=true` and
  `multi_agent=true` without a deprecation warning.
- Effective user config has explicit repository trust and no root trust.
- The project configuration and all custom agents parse as TOML.
- The focused test passes and rejects deprecated hooks, root trust, excess
  concurrency, missing required fields, a writable reviewer/explorer, or a
  non-economical default worker.
- No live provider call, route cutover, deployment, staging, or commit occurs.

