# Slice 0 — Coordinator Bring-up / Validation-Chain Green: Runbook

Orchestrator: claude-opus-4-8, 2026-07-06. Goal: get the coordinator `/qa/check`
validation chain returning machine JSON end-to-end, and clear the failed AIDB unit, so
autonomous loops can trust their own gate.

## Status: fixes verified present in source (rebuild-gated activation)
All 5 PENDING-REBUILD `/qa/check` fixes confirmed in the working tree (2026-07-06):
1. ✅ `mcp_handlers.py` — JSON-mode empty-stdout recovery (`run_qa_check_as_dict`).
2. ✅ `_aq-qa-bash` — `drop_spec.py` probe guarded (import/test failure → normal row).
3. ✅ `tool_registry.py` — audit DB default prefers `XDG_STATE_HOME`/`DATA_DIR`.
4. ✅ `mcp-servers.nix:2481` — `/nix/store/*-source/scripts/** ix` exec rule (store-path aqd/aq-alerts) + `hybridPython` on coordinator path.
5. ✅ `mcp-servers.nix` — per-process net-table read rules for `ss` (tcp/tcp6/udp/unix) + THP.

No further source edits needed — this slice is now an activation + verification pass.

## Blockers (both privileged — operator runs)
- Gate is RED on `ai-aidb-reindex.service` (failed oneshot — known-benign partial reindex).
- The `/qa/check` fixes need a `nixos-rebuild switch` to enter the store-backed service.

## Runbook (operator)
```bash
# 1. Clear the benign failed oneshot (unblocks the tier0 gate)
sudo systemctl reset-failed ai-aidb-reindex.service

# 2. Activate the 5 staged coordinator fixes
sudo nixos-rebuild switch --flake .#hyperd-ai-dev

# 3. Restart the coordinator so it runs the new store source (if not restarted by switch)
sudo systemctl restart ai-hybrid-coordinator
```

## Post-rebuild verification (Claude runs, then closes the 5 items)
```bash
# /qa/check must return machine JSON, not "parse_error: aq-qa produced empty stdout"
curl -s --max-time 30 http://127.0.0.1:8003/qa/check | python3 -m json.tool | head
# expect: a results object with check rows, not a parse_error
aq-qa 0 --machine | tail -3          # phase-0 green from the live path
```
On success: mark the 5 PENDING-REBUILD items `[DONE]` in `issues-backlog.md` and re-run
`tier0-validation-gate.sh --pre-commit` (should be 21/0 once the aidb unit is cleared).

## Slice-0 sub-item [DONE 2026-07-06] — stale-registry-orphan reconciliation
- **Implemented**: `aq-agent-reap --reconcile-registry` (+ `--registry-only`, `--registry-age`,
  `--force`). Pure `should_orphan_row` + atomic `reconcile_registry`; a `_dispatch_active`
  quiescence guard refuses a live rewrite while delegate/agent processes are appending (would
  race the whole-file replace) — downgrades to a safe preview unless `--force`. Tests 10/10
  (4 process + 6 registry). Live run (system quiescent) reconciled the 8 orphans; registry
  503→503 rows, ops-window attention 8→0. registry.jsonl is gitignored (no commit needed).
- **Follow-up**: wire `--reconcile-registry` into the reaper's systemd timer (if present) so it
  runs periodically; mirror to `issues-backlog.md [DONE]` once that file settles.
- Original analysis retained below.

### [DONE] stale-registry-orphan reconciliation — root cause
- **Severity**: medium (observability integrity — the ops window shows false `running` state).
- **Evidence (2026-07-06)**: `aq-tui-dashboard` flagged 8 delegations `◷ stalled` at 7h–23h.
  All 8 have dead/absent pids: antigravity×4 (pid=None, never recorded), local-agent×3 +
  local-direct×1 (pids dead). They are zombie registry rows: process gone, `status=running`.
- **Root cause**: the reaper and the registry are DISCONNECTED. `aq-agent-reap` only kills
  orphaned *processes* (aq-agent-loop holding the llama slot); it never reconciles
  `registry.jsonl`. Registry rows flip to `done`/`failed` only in the delegate `--wait` path
  (`update_registry ... status`). A background/non-wait dispatch whose process dies — or an
  antigravity dispatch that never records a pid — leaves `status=running` permanently.
- **Proposed fix**: extend `aq-agent-reap` with a `--reconcile-registry` pass (registry +
  process orphans belong to the same reaper): for each `status=running` row where pid is
  None/dead AND age > threshold, atomically rewrite `status` → `orphaned` (preserve the row
  for audit; never delete). Add a `test-aq-agent-reap.py` case. Then `aq-tui-dashboard`
  attention drops to true live work. Optionally wire the reconcile pass into the reaper's
  systemd timer if one exists.
- **Guardrails**: atomic rewrite (temp + os.replace, like training_ingest); never touch rows
  with a live pid; bound the age threshold via env (`AQ_REAP_REGISTRY_AGE_S`).
- **Status**: QUEUED (not implemented — gate red + `issues-backlog.md` under concurrent edit).
  Mirror to `issues-backlog.md [OPEN]` once that file settles.

## Deferred (not rebuild-gated, but collision-risk while codex/gemini active)
- `delegate-to-local-task-subcommand-parser-drift` (`--status/--check/--cancel`): the arg
  parser at `scripts/ai/delegate-to-local:96-98` handles `--check ID` but the documented
  positional form drifts. Low priority; hold until the concurrent agents settle to avoid a
  shared-index collision on the live delegation path.
- `sandbox-observability-contract-fragmentation`: routine host probes surface as errors —
  research-level, route to the Slice-2 sandboxing debate.
