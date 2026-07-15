# M1 Implementation Packet — Lower-Model Safe

Status: **CONSUMED — M1 ACCEPTED AND COMMITTED `748c5a9c`**

Read first:

- `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
- `.agents/plans/agent-ops-traceability-r0m/IMPLEMENTATION-AUTHORIZATION-M1.md`
- `scripts/ai/lib/agent_ops_projection.py`
- `scripts/testing/test-agent-ops-projection.py`

Historical execution packet only. The single-use M1 authorization has been consumed; do not reuse
this packet for M2/M3 or any revision without a new exact authorization.

## Exact edit scope

Edit only the eight files in the M1 authorization. Do not use Git. Do not route another agent.

## Discrete implementation steps

1. In `scripts/ai/aq-tui-dashboard`, replace `pgrep -af` authority with a bounded host-fact reader:
   enumerate at most 4096 numeric `/proc` entries; read bounded `stat`, `cmdline`, and `cgroup` bytes;
   parse PID, PPID, session, process group, start time, executable, and NUL-delimited argv. Record
   unreadable facts explicitly. Never infer from a flattened command substring.
2. Add bounded, read-only delegation-registry and trusted-progress readers. Reject symlinks and
   non-regular repository files, cap bytes/records, preserve PID start time, and pass only the M0
   projector's declared fields. Malformed rows become bounded conflict evidence, not exceptions.
3. Add bounded Antigravity inbox facts for pending, output-present-not-archived, archived, missing
   output, and stale state. File existence alone never proves completion.
4. Inject all facts into `project_agent_ops()` and validate with `contract_health()`. Keep
   `agent_ops_projection.py` pure: it must not read `/proc`, files, environment, subprocesses, or
   clocks directly.
5. Make `--json` include the closed projection and sanitized health. Preserve compatible service/A2A
   keys if operators already consume them; do not retain a second process-authority classification.
6. Render tracked/degraded/blocked state in the TUI. Untracked active work is red/blocked; idle
   daemons and the main interactive session are not counted as delegations. Deduplicated wrapper
   chains render once.
7. Extend the golden fixture and focused tests for every M1 adversarial case. Readers use injected
   temporary roots/facts in tests; never depend on the implementation sandbox's real `/proc` for
   deterministic acceptance.
8. Update `docs/operations/agent-ops-window.md` to identify the projection SSOT, uncertainty states,
   private-PID-namespace limitation, sanitized JSON contract, and host-visible acceptance smoke.

## Mandatory negative tests

- PID reused with a different start time;
- argv contains incidental `exec`, `codex`, or `delegate-to` text in a non-executable argument;
- bwrap parent/child plus escaped PGID/session but same valid cgroup;
- `/proc` permission denial and disappearing PID;
- absent/generic cgroup;
- oversized process, registry, progress, and inbox inputs;
- symlink/non-regular registry, progress, inbox, or archive entry;
- duplicate registry rows and terminal/live conflict;
- forged/untrusted progress producer;
- Antigravity output written but task not archived;
- prompt, token, secret, raw argv, and path-content canaries absent from default cards and metrics;
- cache expiry/convergence after a process exits.

## Validation order

```bash
python3 scripts/testing/test-agent-ops-projection.py
python3 -m py_compile scripts/ai/lib/agent_ops_projection.py scripts/testing/test-agent-ops-projection.py scripts/ai/aq-tui-dashboard
scripts/ai/aq-tui-dashboard --json
scripts/governance/tier0-validation-gate.sh --pre-commit
```

The local `--json` run is diagnostic only inside a private PID namespace. Final acceptance requires
an independent host-visible reviewer run proving that old Codex/bwrap processes become correctly
tracked, idle, stale, or blocked and that active counts converge after exit.

Stop and report `BLOCKED` if a ninth file, wrapper enforcement, Phase-0/registry gate, lifecycle
write, process termination, web dashboard change, inference change, or store is needed.
