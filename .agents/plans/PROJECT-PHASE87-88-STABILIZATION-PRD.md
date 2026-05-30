# Phase 87/88 — Observability, Learning Loop, and Codebase Hygiene PRD

## Status: AUTHORIZED — 2026-05-30
## Orchestrator: Claude (Sonnet 4.6)
## Team vote: Gemini (Architect) · Qwen3 (Implementer) · Claude sub-agent (Reviewer)

---

## 1. Goal

Consolidate the stack after Phase 86. Fix broken telemetry signals, wire the dormant
training loop to a schedule, and clean up technical debt that was flagged by all three
agents in the priority debate. Rust refactor is explicitly paused until these are complete.

---

## 2. Phase 87 — Observability + Learning Stabilization

### 87.1 — Downshift Metric Denominator Fix
**Problem**: `continuation_candidates` in `scripts/ai/aq-report` (~line 1757) counts ALL
routes where `generate_response_requested=True`. But the downshift evaluator only runs
when `retrieval_strategy_active=True` (http_server_impl.py line 1204). Routes where
the strategy was inactive could never be downshifted — they inflate the denominator,
making "0/26 candidates" look broken when it just means the strategy wasn't active.

**Fix**: Read `retrieval_strategy_active` from audit_metadata (already emitted at
http_server_impl.py line 1251). Increment `continuation_candidates` only when BOTH
`generate_response_requested is True` AND `retrieval_strategy_active is True`.

**Files**: `scripts/ai/aq-report`
**Lines**: ~1757–1758 (continuation_candidates increment)
**No rebuild required**: script change, takes effect immediately.
**Acceptance**: `aq-report | grep downshift` shows denominator ≤ total synthesis routes
and meaningful non-null percentage once real continuation queries flow through.

---

### 87.2 — P95 Dispatch Token Guard Validation
**Problem**: RESUME.json lists `dispatch P95=244s` as open. Commit `4bf43cae` added
anti-loop guardrails. Need to confirm the guard is actually enforced in the hot path.

**Fix**: Read `scripts/ai/lib/dispatch.py` — confirm `_LOCAL_MAX_TOKENS_HARD_CEILING=180`
is applied in DirectRunner before submitting to llama.cpp. If the guard is confirmed,
close the issue. If a bypass path exists (e.g. explicit `max_tokens` override skipping
the ceiling), patch it.

**Files**: `scripts/ai/lib/dispatch.py`
**Acceptance**: grep confirms ceiling enforcement; issues-backlog.md item updated
to RESOLVED or OPEN-WITH-BYPASS-PATH depending on findings.

---

### 87.3 — Training Ingest Daily Wiring
**Problem**: `training_ingest.py` (ai-stack/local-agents/) is called by
`aq-local-training-loop` in Phase 1 but that loop is user-invoked only.
No systemd timer runs the ingest automatically. Result: 352k+ telemetry events
accumulated with 0 training signal flowing to dataset. Local model cannot improve.

**Fix**:
1. Add `ai-training-ingest.service` + `ai-training-ingest.timer` to
   `nix/modules/services/mcp-servers.nix` — daily run, calls
   `python3 .../training_ingest.py --hours 24`.
2. Add QA check to `scripts/testing/harness_qa/phases/phase0.py`:
   verify `fine-tuning/dataset.jsonl` exists and has at least 1 row
   (created by training_ingest). xfail if file absent (first run).

**Files**: `nix/modules/services/mcp-servers.nix`, `scripts/testing/harness_qa/phases/phase0.py`
**Requires**: nixos-rebuild switch to activate timer.
**Acceptance**: QA check 87.3.1 passes; `systemctl list-timers ai-training-ingest` shows next run.

---

## 3. Phase 88 — Codebase Hygiene

### 88.1 — Orphan Handler Cleanup
**Problem**: `aq-integrity-scan` found 221 unreachable handler registration gaps and
187 zero-import dead code modules. These bloat context windows and slow codebase
search for agents and humans alike.

**Scope (bounded)**: Do NOT delete modules without verifying they are truly unused.
Use `aq-integrity-scan` output as a starting list, grep each for importers before
removing. Focus first on zero-import modules in `ai-stack/mcp-servers/` — these are
the safest to clean.

**Files**: output of `scripts/ai/aq-integrity-scan`
**Acceptance**: Running `aq-integrity-scan` after cleanup shows ≥20% reduction in
zero-import count; `aq-qa 0` still passes all checks.

---

### 88.2 — Untracked File Commits
**Problem**: Several files are untracked and need to be either committed or gitignored:
- `config/harness-prompt-extensions.yaml` — active runtime config, must be committed
- `.agent/RUST-ENGINEERING-INSTRUCTIONS.md` — pre-flight artifact, must be committed
- `.agent/skills/rust-ecosystem/` — skill files, must be committed
- `.agents/plans/RUST-REFACTOR-TEAM-COLAB.md` — planning doc, must be committed
- `prd.md` in repo root — wrong location per file placement contract (Rule in CLAUDE.md);
  move to `.agent/` or delete if duplicate

**Acceptance**: `git status` shows no untracked files in `.agent/`, `.agents/plans/`,
`config/`, and `scripts/ai/`.

---

## 4. Phase 88.5 — ACCELERATE PRD Hardware Validation

**Problem**: `PROJECT-ACCELERATE-PRD.md` has 6/6 implementation slices complete
(aq-workflow CLI, ROCm native, workspace provisioning, Workflow DSL, checkpoint/resume,
graph engine v1). Remaining: 2 acceptance criteria need live hardware runs:
- ROCm perf benchmark
- Concurrency integration test

**Fix**: Run the two pending validation steps against live hardware and mark the PRD
as VALIDATED or open issues for any failures found.

**Acceptance**: Both remaining criteria in PROJECT-ACCELERATE-PRD.md marked green
or new issues logged in issues-backlog.md.

---

## 5. Execution Order

```
[user] nixos-rebuild switch --flake .#hyperd-ai-dev   ← prerequisite for Phase 85+86+87.3
87.1  downshift metric fix                             ← Python only, no rebuild
87.2  P95 dispatch guard validation                    ← Read + verify, no rebuild
87.3  training ingest timer wiring                     ← Requires rebuild
88.1  orphan cleanup (bounded)                         ← Python only
88.2  untracked file commits                           ← git only
88.5  ACCELERATE hardware validation                   ← requires live stack
```

## 6. Out of Scope (Explicitly Paused)

- Rust refactor Phase 0 (all cargo work)
- PAEA Phase 2 Skill Factory (blocked on training loop working first)
- Role enforcement runtime (Phase 58A.5, low priority, doc-only for now)
