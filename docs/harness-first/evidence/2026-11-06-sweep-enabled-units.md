# 2026-11-06 sweep-enabled-units

## Objective
Recovery sweep P2.3 (system-integrity-recovery): every enabled project unit and timer is running and producing output, judged from live systemd state. Report only; no unit, tracker or backlog was changed.

## Workflow/Session IDs
Branch feat/sweep-enabled-units, date 2026-11-06, host live systemd (system + user scope).

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixtures).

## Commands Executed
- `scripts/governance/sweep-enabled-units.py --report docs/harness-first/evidence/2026-11-06-sweep-enabled-units.md --date 2026-11-06`
- `systemctl [--user] list-unit-files --all`, `systemctl [--user] show --timestamp=unix -p <props> <units>` (read-only)
- Filesystem stat of ExecStart paths, StateDirectory/LogsDirectory and `*_DIR` environment paths

## Scope and filter
- Name filter: `^(ai-|aq-|aidb|prsi|llama|coordinator|switchboard|dashboard|command-center|hybrid|mcp-|redis-mcp|qdrant|postgresql|nixos-ai|ralph|harness|agentic|antigravity)` (case-insensitive), unioned with literal unit names declared in `nix/` (system 147, user 4); 0 `${...}`-named declarations cannot be resolved statically.
- Units checked: system 116, user 7; timers evaluated: 39.
- Interval rules: OnUnitActive/Inactive span, or a rough OnCalendar estimate; STALE_TIMER = last fired beyond 3x interval + 600s; NEVER_RAN = timer or service up > 3600s (and past its interval) with no run; RESTART_LOOP = NRestarts >= 5.

## Validation Evidence

Counts per class:

| Class | Count |
|---|---|
| FAILED | 0 |
| NEVER_RAN | 0 |
| STALE_TIMER | 0 |
| NO_OUTPUT | 7 |
| DECLARED_MISSING | 20 |
| RESTART_LOOP | 0 |
| RETIRED_REF | 0 |
| BROKEN_EXEC | 0 |

Total findings: 27. Unknown (not counted as pass): 68.

Findings:

| # | Sev | Class | Scope | Unit | Evidence |
|---|---|---|---|---|---|
| 1 | medium | NO_OUTPUT | system | `ai-autonomous-improvement.service` | /var/lib/ai-stack/autonomous-improvement last written 37d ago; run interval ~1h |
| 2 | medium | NO_OUTPUT | system | `ai-autonomous-improvement.service` | /var/lib/ai-stack/autonomous-improvement/deviations/workflow-deviations.jsonl last written 21d ago; run interval ~1h |
| 3 | medium | NO_OUTPUT | system | `ai-gap-auto-remediate.service` | /var/lib/nixos-ai-stack/optimizer/gap-remediation last written 166d ago; run interval ~1d |
| 4 | medium | NO_OUTPUT | system | `ai-mcp-integrity-check.service` | /var/lib/ai-mcp-integrity last written 12h ago; run interval ~1h |
| 5 | medium | NO_OUTPUT | system | `ai-mcp-process-watch.service` | /var/log/ai-mcp-process-watch last written 214d ago; run interval ~15m |
| 6 | medium | NO_OUTPUT | system | `ai-switchboard.service` | declared output path missing: /var/lib/nixos-ai-stack/optimizer/switchboard-remote-budget.json |
| 7 | medium | NO_OUTPUT | system | `aq-lease-signing-authority.service` | declared output dir empty: /var/lib/aq-lease-signing-authority |
| 8 | medium | DECLARED_MISSING | system | `activation-auto-revert.timer` | declared at nix/modules/services/activation-auto-revert-guard.nix:96 but no unit file is installed (may sit behind a disabled mkIf) |
| 9 | medium | DECLARED_MISSING | system | `ai-headroom-proxy.service` | declared at nix/modules/services/headroom-proxy.nix:74 but no unit file is installed (may sit behind a disabled mkIf) |
| 10 | medium | DECLARED_MISSING | system | `ai-oncalld.service` | declared at nix/modules/services/oncalld.nix:68 but no unit file is installed (may sit behind a disabled mkIf) |
| 11 | medium | DECLARED_MISSING | system | `aq-auto-update-check.timer` | declared at nix/modules/core/auto-update.nix:60 but no unit file is installed (may sit behind a disabled mkIf) |
| 12 | medium | DECLARED_MISSING | system | `aq-auto-update-run.timer` | declared at nix/modules/core/auto-update.nix:85 but no unit file is installed (may sit behind a disabled mkIf) |
| 13 | medium | DECLARED_MISSING | system | `aq-network-policy-watchdog.timer` | declared at nix/modules/core/network.nix:193 but no unit file is installed (may sit behind a disabled mkIf) |
| 14 | medium | DECLARED_MISSING | system | `aq-workflow-deviation-broker.socket` | declared at nix/modules/services/workflow-deviation-broker.nix:33 but no unit file is installed (may sit behind a disabled mkIf) |
| 15 | medium | DECLARED_MISSING | system | `aqos-install-vm-ai-dev-factory-topology.service` | declared at nix/hosts/aqos-install-vm/default.nix:175 but no unit file is installed (may sit behind a disabled mkIf) |
| 16 | medium | DECLARED_MISSING | system | `aqos-install-vm-dogfood-marker.service` | declared at nix/hosts/aqos-install-vm/default.nix:135 but no unit file is installed (may sit behind a disabled mkIf) |
| 17 | medium | DECLARED_MISSING | system | `aqos-vm-dogfood-marker.service` | declared at nix/hosts/aqos-vm/default.nix:84 but no unit file is installed (may sit behind a disabled mkIf) |
| 18 | medium | DECLARED_MISSING | system | `battery-charge-thresholds.service` | declared at nix/modules/hardware/mobile.nix:101 but no unit file is installed (may sit behind a disabled mkIf) |
| 19 | medium | DECLARED_MISSING | system | `llama-cpp-aqdecide.service` | declared at nix/modules/roles/ai-stack.nix:1662 but no unit file is installed (may sit behind a disabled mkIf) |
| 20 | medium | DECLARED_MISSING | system | `llama-router.service` | declared at nix/modules/services/llama-router.nix:36 but no unit file is installed (may sit behind a disabled mkIf) |
| 21 | low | DECLARED_MISSING | system | `activation-auto-revert.service` | declared at nix/modules/services/activation-auto-revert-guard.nix:106 but no unit file is installed (may sit behind a disabled mkIf) |
| 22 | low | DECLARED_MISSING | system | `aq-auto-update-check.service` | declared at nix/modules/core/auto-update.nix:49 but no unit file is installed (may sit behind a disabled mkIf) |
| 23 | low | DECLARED_MISSING | system | `aq-auto-update-run.service` | declared at nix/modules/core/auto-update.nix:71 but no unit file is installed (may sit behind a disabled mkIf) |
| 24 | low | DECLARED_MISSING | system | `aq-network-policy-emergency-revert.service` | declared at nix/modules/core/network.nix:203 but no unit file is installed (may sit behind a disabled mkIf) |
| 25 | low | DECLARED_MISSING | system | `aq-network-policy-watchdog.service` | declared at nix/modules/core/network.nix:174 but no unit file is installed (may sit behind a disabled mkIf) |
| 26 | low | DECLARED_MISSING | system | `aq-workflow-deviation-broker.service` | declared at nix/modules/services/workflow-deviation-broker.nix:45 but no unit file is installed (may sit behind a disabled mkIf) |
| 27 | low | DECLARED_MISSING | system | `meta-optimization-applier.service` | declared at nix/modules/services/meta-optimization.nix:233 but no unit file is installed (may sit behind a disabled mkIf) |

Unknown / not determinable:

- no declared state<x> path (StateDirectory, LogsDirectory, *_DIR env) to check output against: 41 units (e.g. agent-reap.service, ai-aidb-reindex.service, ai-amdgpu-metrics-exporter.service, ai-auth-selftest.service)
- <x> exists (written <x> ago) but no run interval to judge staleness: 19 units (e.g. ai-aidb.service, ai-aider-wrapper.service, ai-audit-sidecar.service, ai-hybrid-coordinator.service)
- output path <x> unreadable without privilege: 8 units (e.g. ai-tempo.service, aq-c2-scheduler-context-issuer.service, aq-revocation-epoch-authority.service, crowdsec-firewall-bouncer-key-sync.service)

Notes:

- `journalctl` was not used for the verdicts; output checks use declared paths only. A service with no declared path is `unknown`, not a pass.
- NO_OUTPUT staleness uses the newest mtime under the declared path; a unit that writes only when something changes can look stale.
- DECLARED_MISSING does not evaluate the module option gating (mkIf/enable); a unit declared behind a disabled option is still reported (medium when it declares wantedBy, else low).
- Units whose state can only be read as root (for example journal of other users, protected state dirs) show as unknown.

## Rollback Plan
Delete this report and the sweep script; nothing else was changed.
