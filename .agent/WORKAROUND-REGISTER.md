# Workaround / Debt Register (SSOT)

## WR-PRSI-M7-REPO-ROOT — dry-run preview resolves wrong repository root — FIXED
- symptom: safe dry-run preview reaches HTTP handler but returns 404 because `repo_root` resolves to `ai-stack`.
- band-aid in place? no.
- root cause: existing `Path.parents` calculation was one level short (`parent.parent.parent.parent` instead of 5 levels up / `resolve().parents[4]`) for this checkout layout.
- producer to fix: PRSI action execution handler root calculation in `ai-stack/mcp-servers/hybrid-coordinator/workflow/prsi_handlers.py`.
- fix-path: corrected `repo_root = Path(__file__).resolve().parents[4]` in `handle_prsi_actions_list` and `handle_prsi_action_execute`.
- class: T2 validation-gap · severity: medium · status: FIXED · opened: 2026-10-02 · closed: 2026-10-02.
- evidence: unit tests and path resolution tests verify `(repo_root / 'scripts/ai/aq-report').exists()` and `(repo_root / 'scripts/ai/aq-optimizer').exists()`.

Every workaround, band-aid, or ad-hoc fix that is NOT yet fixed at its producer lives here —
never silently in the code. Governed by `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md` (proposed
Rule 19). Swept like the agent catch-up queue; items aging past their window escalate.

Entry fields: id · symptom · band-aid in place? · root cause · producer to fix · fix-path ·
class (T1 tooling / T2 validation-gap / T3 diagnosability / T4 gate-coupling / T5
producer-governance-fracture) · severity · status · opened.

Status legend: OPEN (band-aid live, unfixed) · FIXED (producer fixed, band-aid removed) ·
ACCEPTED (documented deliberate tradeoff, no band-aid) · MAINT-DUE (time/env expiry, tracked).

---

## WR-1 — nested-quoting mangles cell-adapter submits — FIXED
- symptom: `sg -c "… python3 -c \"…\""` (triple quote layers) garbled newlines/special chars.
- root cause (T1): no reusable CLI; inline python nested in two shell layers.
- fix: `scripts/testing/cell-submit.py` — argparse CLI, single `sg -c` layer, plain args.
- status: FIXED 2026-08-06 (validated: clean GREEN round-trip, exit 0).

## WR-2 — inline commit messages die on `${}` / `->` — FIXED
- symptom: `git commit -m` with `${pkgs.git}` (zsh bad-substitution) and `->` (control-char hook).
- root cause (T1): shell metachar/expansion in inline messages.
- fix: use `git commit -F <file>`; author multi-line docs via Write + `cat >>`, never inline heredocs with `${}`.
- status: FIXED 2026-08-06 (habit + documented in the PRD).

## WR-3 — runner deploy bugs only discoverable live, one per rebuild — FIXED
- symptom: #10 (durable_reservation.py missing from runnerBundle), #11 (systemd strips JSON quotes), #13 (git not on PATH) each passed offline acceptance, failed live, needed a rebuild to find the next.
- root cause (T2): no deploy-context preflight (bundle-import resolution, env round-trip through systemd, bare-binary PATH deps).
- producer to fix: execution-cell-runner activation path.
- fix-path: a preflight (simulate_nix_change-adjacent) asserting bundle imports resolve, `TRUSTED_REPO_MIRRORS` JSON survives systemd, and every bare-`git` dep is on the service PATH. Normal PRD→build→review slice.
- class T2 · severity MED · status FIXED 2026-08-06 · opened 2026-08-06.
- FIXED: `scripts/testing/test-execution-cell-runner-deploy-context.py` — static preflight asserting runnerBundle import closure (cf #10), git-on-PATH (cf #13), and single-quote-wrapped toJSON env (cf #11). Validated both ways (PASS clean; correctly CAUGHT a simulated missing bundle module with the exact diagnostic). Wired into focused-ci (`config/validation-check-registry.json`, id `execution-cell-runner-deploy-context`) triggering on any runner deploy-surface file change — so this class is caught at commit time, never live.

## WR-4 — cell-create failures hide their cause — FIXED
- symptom: every cell-create failure surfaced only a catch-all code (`quarantined`); the real "why" (git-not-found, isolation-violation, path-escape) required reverse-engineering source+repo.
- root cause (T3): runner Decision keeps only `cell_result.code`, discards `TypedFailure.detail`.
- producer to fix: `execution_cell_runner.py` cell-create failure branch (line ~641).
- fix-path: log `cell_result.detail` low-cardinality class to journald alongside `_log_unproven_tree`. Normal slice.
- class T3 · severity MED · status FIXED 2026-08-06 (validated live: `[cell-create] DENIED code=path-escape detail=…` in journald) · opened 2026-08-06.
- FIXED: added `_log_cell_create_failure()` — on a cell-create denial the runner now logs `code` + truncated `detail` to journald (receipt schema unchanged). Turns the R7-style blind spelunk into a one-line read. Runner suite 13/13.

## WR-5 — tier0 0.10.5 model-profile freshness hard-blocks all commits — FIXED
- symptom: `reviewed_at`/`probed_at` (2026-06-21) aged ~1 day past the 45-day window → tier0 `--pre-commit` fails → ALL commits blocked. Tempts hand-bumping the timestamp (gaming) or bypassing tier0.
- root cause (T4 + T5): a time-based freshness check wired as a HARD pre-commit blocker (T4); AND the producer `model_probe.py` writes measurement fields but NOT the `_meta`/freshness governance fields it's checked against, so a real re-probe clobbers governance and hand-editing becomes the "easy" path (T5).
- profile verified accurate: active.gguf/Qwen3-35B, TPS 3.0, ctx 262144 all match reality — content is NOT drifted; only the timestamps lapsed.
- fix-path: (a) gate hygiene — freshness-class checks WARN in `--pre-commit`, HARD only in scheduled `--maintenance` that opens a register item (needs owner ratification, changes tier0 behavior); (b) producer patch — `model_probe.py` maintains `_meta.reviewed_at`/`freshness_max_age_days` so a re-probe is a complete, honest refresh.
- class T4+T5 · severity HIGH · status FIXED 2026-08-06 · opened 2026-08-06.
- FIXED: (T5) `model_probe.py` `_save` now maintains `_meta`/freshness on every write + fixed a malformed `probed_at` (commit aa0a38a4); a real re-probe refreshed the profile honestly. (T4) tier0 gate hygiene landed — freshness-class checks (0.10.5) WARN in `--pre-commit`, HARD in `--pre-deploy`; validated end-to-end (induced-stale → WARN+pass in pre-commit). Owner-ratified 2026-08-06.

## WR-6 — sudo unavailable in agent shell → repeated fallback attempts — ACCEPTED
- symptom: `sudo -n` needs a password here; I attempted it (cgroup/watcher reads) before falling back to /proc or asking for a `!`-run.
- root cause: no setuid in the agent shell (environment constraint, known).
- resolution: ACCEPTED tradeoff — do NOT attempt sudo; go straight to non-sudo paths (/proc, world-readable files) or a user `!`-run. No producer fix (environment is intentional).
- class — · severity LOW · status ACCEPTED · opened 2026-08-06.

## WR-7 — git-command hook mangles shell variables in commit paths — ACCEPTED
- symptom: `D=/path; git commit -F "$D/msg.txt"` failed with `could not read log file '/msg.txt'` — `$D` did not survive the git-command rewrite hook (RTK/lean-ctx). Cost two failed commit rounds this session.
- root cause (T1): the git wrapper hook re-parses the command; a shell variable in the path is lost/empty by the time git runs.
- resolution: ACCEPTED — in Bash tool `git` invocations, use ABSOLUTE literal paths for `-F <msgfile>` (and generally avoid shell variables inside hook-wrapped git commands). No producer fix (the hook is a deliberate token-optimization wrapper).
- class T1 · severity LOW · status ACCEPTED · opened 2026-08-06.

## WR-8 — tier0 xfail matcher regex can't parse table-format failures — FIXED
- symptom: gate_qa_phase0's xfail excuse-path uses `grep -oP '✗\s+\K[0-9.]+'` (id AFTER ✗), but aq-qa renders failures as a table row with the id BEFORE the ✗ column — so failing_ids is always empty and the documented-xfail path (config/qa-xfail.yaml) never actually excuses anything (effectively dead).
- root cause (T3-adjacent): parser assumes a `✗ <id>` inline format that aq-qa does not emit.
- producer to fix: scripts/governance/tier0-validation-gate.sh gate_qa_phase0 xfail block.
- fix-path: same table-aware parse now used by the freshness-class block (`grep '✗' | grep -oP '<id>'`); before enabling, re-verify config/qa-xfail.yaml entries are still legitimately runtime-blocked (making xfail actually work will start excusing them). Normal slice.
- class T3 · severity MED · status FIXED 2026-08-06 · opened 2026-08-06.
- FIXED: applied the table-aware parse to the xfail block. Safe: config/qa-xfail.yaml is currently empty (`xfail: []`), so nothing is newly excused; the mechanism is now correct for when entries are added. tier0 25/0, no regression.

### WR-5 extension (2026-09-14): LIVE_SERVICE_CLASS_IDS
Extends the WR-5 freshness-class WARN mechanism in `gate_qa_phase0()` with a sibling
`LIVE_SERVICE_CLASS_IDS` (QA phase-0 checks that probe LIVE external/service/runtime state:
systemd unit/timer active, port bound, datastore reachability, AppArmor deployed+runtime
enforcement, inference-server /health, external agent CLI/lane, AIDB vector-search). Same
semantics: WARN (visible, non-blocking) on `--pre-commit`, HARD on `--pre-deploy`/`--maintenance`.
Symptom: a momentarily down/warming/cold-loading/quota-limited live dependency (e.g. post-reboot
llama-cpp cold-load, AIDB warming, antigravity quota/binary) hard-failed QA phase 0 and blocked
commits of unrelated staged changes. Root cause / class: environmental-runtime signal, not a
regression the staged diff introduced (Rule 19 gate corollary). Fix-path: tier0-validation-gate.sh
`gate_qa_phase0()`. All-or-nothing preserved: any failing id NOT in a WARN class still hard-fails
the whole gate + lists every row, so static regressions are never masked. Reclassified base ids:
0.1.1 0.1.2 0.1.3 0.2.1-0.2.5 0.3.1-0.3.3 0.4.1-0.4.3 0.6.1 0.6.2 0.7.4.

### WR-5 extension (2026-09-17): add 0.8.1 (delegate 24h success) to LIVE_SERVICE_CLASS_IDS
Symptom: QA phase-0 `0.8.1 ai_coordinator_delegate 24h success rate` dropped below its ≥50%
floor and HARD-failed tier0 `--pre-commit`, blocking commits of unrelated staged changes
(the local-producer-timing promotion, and any other commit factory-wide). Root cause / class:
`0.8.1` is a rolling LIVE telemetry window ("are delegations succeeding right now") — it fell
because remote reviewer/provider lanes (Luna + others) were quota-limited/down this window, NOT
because any staged diff broke delegation. This is the identical live-service signal already
recognized for `0.10.22` (live throughput), so it belongs in the same WARN-in-precommit /
HARD-in-predeploy class (Rule 19 gate corollary). Fix: append `0.8.1` to `LIVE_SERVICE_CLASS_IDS`
in `scripts/governance/tier0-validation-gate.sh gate_qa_phase0()`. All-or-nothing preserved:
delegation health stays HARD on `--pre-deploy`/`--maintenance`, and any non-class failing row
still hard-fails pre-commit. class: live-service (runtime state) · severity MED · status FIXED
2026-09-17 · queued for Codex/Antigravity confirmatory catch-up review (author self-reviewed;
Codex lane absent).

## WR-9 — focused-ci (run-focused-ci-checks.sh) lacked the freshness-class WARN treatment tier0 has — FIXED
- symptom: `.githooks/pre-commit` runs TWO independent commit-time gates —
  `tier0-validation-gate.sh` (via `gate_qa_phase0` aq-qa id `0.10.5`) AND
  `run-focused-ci-checks.sh` (registry id `model-catalog-freshness`) — both wrap the same
  producer script `scripts/testing/test-model-catalog-freshness.py`. WR-5 gave tier0 the
  freshness-class WARN treatment (2026-08-06), but `run-focused-ci-checks.sh` was never updated
  to match, so it still HARD-blocked ANY commit touching a trigger path (`config/model-profile.json`,
  `model_catalog.py`, `dashboard/backend/api/routes/models.py`, `assets/dashboard.js`,
  `scripts/testing/test-model-catalog-freshness.py`, `phase0.py`, `_aq-qa-bash`) whenever
  `_meta.reviewed_at`/`probed_at` aged past the 45-day window — a pure time-expiry signal, not a
  regression in the staged diff. Two commit-gate runners disagreeing on the same signal is itself
  a gate-hygiene gap (Rule 19 corollary).
- root cause (T4, gate-coupling): `run-focused-ci-checks.sh` has no freshness-class concept at
  all — every non-zero, non-SKIP_EXIT_CODES exit from a registry check unconditionally sets
  `any_failed = True` regardless of mode or failure reason.
- producer to fix: `scripts/governance/run-focused-ci-checks.sh` (the python heredoc dispatch
  loop).
- fix-path: mirrored tier0's exact mechanism — the registry
  (`config/validation-check-registry.json`) carries no per-check class/severity field (verified:
  every entry only has `"tier": structural|behavioral`, unrelated to time-expiry), so tier0 itself
  uses a hardcoded check-id list (`FRESHNESS_CLASS_IDS="0.10.5"`), not a registry field. Added the
  same kind of list to run-focused-ci-checks.sh, `FRESHNESS_CLASS_CHECK_IDS = {"model-catalog-freshness"}`,
  keyed by the registry's own id (tier0 keys by aq-qa's numeric id; both point at the same producer
  script). Because `test-model-catalog-freshness.py` mixes structural assertions (model_id/model_path/
  probe_model_id/dashboard-wiring required — must stay HARD) with pure time-expiry assertions
  (`age_days(...) <= max_age`), a bare check-id match would have been unsafe — it could mask a real
  regression in the same script. Added a second, content-based guard:
  `FRESHNESS_TIME_EXPIRY_MARKERS` (the exact 3 `AssertionError` messages the script raises only for
  the elapsed-days checks: "model profile review is stale", "model probe is stale", "model catalog
  review is stale"). A `model-catalog-freshness` failure downgrades to WARN in `--pre-commit` ONLY
  when its captured stdout+stderr contains one of those markers; any other failure in the same
  check (structural regression, import error, missing file) still HARD-fails today, unchanged. In
  `--pre-deploy`/`--maintenance` the downgrade never applies (gated on `mode == "--pre-commit"`),
  so freshness stays HARD there. `model-profile.json` timestamps were NOT touched — that lapse is
  tracked separately as ongoing maintenance, not fixed by this change (anti-gaming).
- class T4 (gate-coupling) · severity MED · status FIXED 2026-09-25 · opened 2026-09-25.
- FIXED: validated live — staged a trigger-path change, ran
  `run-focused-ci-checks.sh --pre-commit`: `model-catalog-freshness` reported
  `[focused-ci] WARN: ... freshness-class (time-expiry) ...` and the run exited 0. Ran the same
  script `--pre-deploy` with an unstaged trigger-path change: `model-catalog-freshness` reported
  `[focused-ci] FAIL: ...` (no WARN) and exited 1 — freshness stays HARD there. Proved non-freshness
  checks still HARD-fail in `--pre-commit` via a synthetic always-failing canary check
  (`command: ["false"]`) added to a scratch copy of the registry: it printed
  `[focused-ci] FAIL: TEMP canary ...` and the run exited 1. `bash -n` + embedded-python
  `py_compile` clean; `repo-structure-lint.sh --staged` PASS. Queued for independent Opus binding
  review before PR (Rule 18 — author self-validated, no self-review of acceptance).

## 2026-09-27 — Resumed context guards / memory persistence
- aq-memory swallowed disk-write failures; current temporal_facts.json is nobody:nogroup 0644. Repair failure reporting first; storage ownership and coordinator working-memory HTTP 500 remain open. Repository handoff is the checkpoint fallback; queued memory writes are not durability evidence.
- 2026-10-02 takeover update: the working-memory save endpoint returned HTTP 500; this does not establish that the separate MemoryBroker fact store is down. The shared parent is `0711 root:root` and the intended child owner is `ai-hybrid` (no `childagent` account is intended). Retirement and querygaps show additional DAC symptoms, but their paths/producers are being traced independently. No successful working-memory save is claimed.
- 2026-10-02 runtime evidence: Ralph R1 source tests pass and `REPO_ROOT` is active in the service environment, but authenticated sync reaches the handler and reports missing `python3`; add the existing `ralphPython` runtime to the declared service PATH and verify live sync. R2 aggregate and dedicated checks now both pass. `/readyz` currently returns 200.
- 2026-10-02 validation evidence: outside-sandbox tier0 reported 52 PASS / 2 FAIL: L2B whole-source hash drift after the authorized repo-root change and `/readyz` during owner switch. Write-region and loop-bounds checks passed outside sandbox. QA phase 0's external 120s timeout (124) with empty output remains a failure; buffering is suspected, unproven.
- 2026-10-02 QA phase-0 observation: external 120s timeout (exit 124) left an empty log; Python output buffering is suspected but unproven. This is diagnostic context, not a workaround or pass signal. Keep the failure visible while tracing capture/flush behavior.
- Tier0 acquires its own checkout: do not wrap it in aq-gate-checkout run. Released only this session's outer lock after nested acquisition stalled. Direct gate reached the 120-second timeout; TERM did not stop remaining gates, so interrupted explicitly. No full PASS or commit claimed.
- Sandbox blocked QA evidence lock under /var/lib; retry requested using normal escalation.

## WR-10 — event-log fallback implemented before canonical-path root fix — FIXED
- symptom: the agent added a writable fallback after writes to `.agents/events` failed, before establishing why that path was unwritable.
- root cause (T5): producer-path ownership and mount authority were not checked during the first failure response; the managed `.agents` mount is intentionally read-only and the logger had the wrong canonical target.
- resolution: move the canonical ledger to `.agent/collaboration/a2a-events.jsonl`, retain `.agents/events/a2a-events.jsonl` only as a legacy read source, and keep the fallback as an emergency guard for unexpected failures. Add a regression test pinning the default path.
- class T5 · severity MED · status FIXED 2026-09-27 · opened 2026-09-27.

### Hourly PRSI redundant LLM wrapper — FIXED / follow-up open
- 2026-09-28 root cause resolution: isolated worktree helper defaulted to `.agents/delegation`, an intentionally read-only mount, and PRSI preflight checked neither the writable delegation root nor shared Git metadata. Dispatch now accepts `AQ_DELEGATION_DIR`, preflights both write authorities, and incident-ledger changes wake a one-item dispatcher with a five-minute queue sweep. Repository validation passed; service activation/live integration remain unverified.
- symptom: each hourly PRSI cycle submitted a fixed Python command through `aq-ralph-task`.
- root cause: deterministic orchestration was routed through an LLM task wrapper; `aq-report` still performs its own local-model summary, so total model use requires further measurement.
- resolution: invoke `prsi-orchestrator.py cycle` directly from the service; keep the hourly cadence until queue/event processing is safely isolated and measured.
- follow-up: add provider/session/lane token and cost attribution, and resolve writable isolated-worktree authority before automatic repair dispatch.
- class T2 · severity HIGH · status PARTIAL 2026-09-28 · opened 2026-09-28.

### RSI report dependency — root fix implemented, runtime follow-up open
- Every RSI dispatch called full report discovery before incident intake; model/report outages could obstruct their own repair intake and each invocation added avoidable work.
- Incident-only sync now reuses queue deduplication without model-backed reports and preserves existing degradation evidence. Regression exercises two dry runs with report discovery forbidden.
- Shared atomic estimated-budget reservations are now implemented for both lanes, including failed attempts; focused concurrency tests pass. Unattended activation remains incomplete: writable isolation and runtime validation still need resolution. No guard bypass or substitute execution folder was introduced.
- Context acquisition friction: an unverified lean-ctx range mode returned a full file. Supported `lean-ctx -c --raw` with explicit bounded `sed` ranges is used pending validation of range-mode rejection in the tool itself.

### RSI dispatcher omitted required Git runtime dependency — FIXED / activation pending
- 2026-09-28 root cause: the hardened systemd `PATH` for `ai-prsi-rsi-dispatch` provided Python but omitted Git, although fail-closed repository/worktree preflight invokes Git. This made every queued repair block before claim (five pending incidents observed).
- Root fix: add `pkgs.git` to the unit's `path` and pin the service dependency in `test-prsi-rsi-intake.py`. Activation and live terminal-outcome verification remain required.
- Investigation friction: lean-ctx blocked another broad search after its 11-search/300-second loop limit; switched to exact-path reads and tree navigation instead of retrying.
- class T2 · severity HIGH · status FIXED / activation pending 2026-09-28.
### 2026-09-28 — deploy projection exhausted RAM-backed /tmp; target lookup masked timeout
- Temporary workaround: run deploy with `TMPDIR=/var/tmp`; the 7.3 GB projection fits disk-backed storage and avoids pressure on `/tmp` tmpfs. Do not increase tmpfs for this workload; first measure RAM headroom and projection cleanup.
- Root cause found separately: deploy target membership called full per-target NixOS config evaluation; timeout was converted to false even while flake name discovery listed the target. Fix membership using the discovered names and retain the distinct evaluation-error path. Focused regression added.
- Follow-up: consider making disk-backed deploy temp the documented/default policy after checking cleanup and available-space guard.
### 2026-09-28 — Tier 0 pre-commit gate stall
- Attempted mandated serialized gate; after >4 minutes it emitted no output and a nested `tier0-validation-gate.sh` process appeared. Stopped the run (exit 130); focused tests passed, full gate is unverified.
- No gate bypass used and no commit or activation claimed. Diagnose nested invocation/quiet runner before retrying; preserve this as an open validation blocker.

### 2026-09-30 — aq-report token metrics exceeded PRSI memory bound
- Root cause: `useful_token_metrics` loaded the complete 92,164,469-byte `agent-run-events.jsonl` and built/copy-filtered historical timelines before selecting the requested window.
- Bounded fix: stream JSONL and retain only in-window token rows plus per-run duration aggregates. Regression asserts the whole-file `load_jsonl` path is not used.
- Evidence: same redirected, profiled aq-report path fell from 552,192 KiB process-tree peak (active `useful_token_metrics` stack ~538,236 KiB) to 115,852 KiB (−422,384 KiB / 78%). Focused test 7/7 and py_compile passed. Keep the 256M service cap unchanged.
- Runtime remains pending exact-subject independent review and a serialized live acceptance window; do not manually start the executing PRSI unit while Remediator/timer ownership is unsettled.
- 2026-09-30 live acceptance (claude-opus): scheduled `ai-prsi-orchestrator` cycle 09:28 PDT failed `oom-kill` (pre-fix, 2m25s); first post-fix cycle 10:08 PDT ran sync (aq-report) to `Result=success` in 9s under the unchanged 256M cap. Exact subject 6c06b38b/243885d0 independently reviewed PASS by claude-opus (streaming path is order-independent; missing-file still yields `status=no_data`); local Qwen review local-20260930-105223-xbkns7 dispatched.

## WR-PRSI-THROTTLER — aq-throttler kept on legacy PRSI queue file — FIXED
- symptom: aq-throttler list-wraps the PRSI queue dict on write; pointed at the canonical queue it erased state (2026-10-02).
- band-aid in place? no: aq-throttler stripped of direct queue mutations in commit `1cd5b206`; runs `prsi-orchestrator.py execute --limit 1`. Pinned by `test-prsi-queue-path-ssot.py` lines 88-94 (asserts zero queue writes in aq-throttler).
- root cause (T5): throttler writer predated queue schema; no shared queue-write API.
- producer fixed: `scripts/ai/aq-throttler` executes via orchestrator CLI; queue mutations centralized in `scripts/ai/lib/prsi_queue.py`.
- class: T5 producer-governance-fracture · severity: high · status: FIXED 2026-10-02 · opened: 2026-10-02

## WR-ANTIGRAVITY-IDE-ROLE-BAN — artificial unsupported role ban on Antigravity/Gemini — FIXED
- symptom: aq-antigravity-inbox and prsi-orchestrator rejected implementer, coordinator, and subagent roles with `blocked_unsupported_ide_worktree_isolation`.
- band-aid in place? no: removed hardcoded role ban. Replaced with real per-dispatch git worktree isolation via `wt_create` and `wt_handback` (`scripts/ai/lib/worktree-isolation.sh`) in `delegate-to-antigravity` for code modifications, while unblocking non-modifying coordination and subagent roles per Rule 21.
- root cause (T5): artificial blanket ban was applied instead of wiring worktree lifecycle management into the Antigravity delegation bridge and properly differentiating code modification roles from coordination roles.
- producer fixed: `scripts/ai/delegate-to-antigravity` allocates isolated worktree and generates patch on completion; `scripts/ai/aq-antigravity-inbox` enforces worktree isolation fail-closed for implementation roles and allows coordination/subagents; `scripts/automation/prsi-orchestrator.py` verifies standard preflight for all lanes.
- class: T5 producer-governance-fracture · severity: HIGH · status: FIXED 2026-10-03 · opened: 2026-10-03
## WR-ANTIGRAVITY-IDE-WORKSPACE-BINDING (2026-10-03)

- **Symptom:** A receipt/task metadata record can indicate completion without proving that Antigravity performed an editing task in that task's isolated workspace.
- **Root cause:** The IDE `--reuse-window` route provides no verifiable per-task workspace/worktree binding; receipt evidence authenticates completion output, not IDE workspace authority.
- **Producer:** Antigravity bridge/inbox integration and caller dispatch contract.
- **Fix path:** Fail closed for editing roles until bridge dispatch and inbox enforcement establish and verify a dedicated task workspace; root integrates caller/isolation repairs and submits the frozen subject to independent review.
- **Class / severity:** authority/isolation; high.
- **Interim state:** Live IDE mutation is deferred. Receipt findings 2/3 have focused temporary-repository real-supervisor coverage only; earlier resolved/pass statements are Antigravity self-report, not final acceptance.

## WR-COLLAB-PULSE-TEMP-CONTENTION (2026-10-03) — FIXED

- Symptom: concurrent aq-event writers contend on a common temporary path (`path.with_suffix(".tmp")`).
- Root cause / producer: shared atomic-write staging in `scripts/ai/lib/resume_projector.py` and `scripts/ai/lib/span_projector.py`.
- Fix path: unique writer staging with PID and 8-byte random token (`.{name}.{pid}.{secret}.tmp`) in same parent directory plus concurrency regression.
- Class / severity: concurrency; medium. Status: FIXED 2026-10-05.
- Evidence: `scripts/testing/test-event-bus-a2a.py` `test_concurrent_atomic_write_resistance` exercises 20 synchronized concurrent threads with barrier start and zero staging collisions.

## WR-TOOLCHAIN-PSMISC-MISSING (2026-10-05)

- Symptom: `pstree`, `fuser`, and `killall` unavailable on host and agent PATH (`command not found`).
- Root cause: `nix/modules/roles/agentic-toolchain.nix` included `procps` (`ps`, `watch`, `top`) but omitted `psmisc`; `nix/modules/core/base.nix` omitted `psmisc` from `basePackageNames`.
- Fix path: add `psmisc` to `baselinePackages` in `agentic-toolchain.nix` and `basePackageNames` in `base.nix`; assert in `test-agentic-toolchain-baseline.py`.
- Class / severity: T1 tooling; medium. Status: FIXED 2026-10-05.
- Evidence: `psmisc` declared in `nix/modules/roles/agentic-toolchain.nix` baselinePackages and `nix/modules/core/base.nix` basePackageNames; `scripts/testing/test-agentic-toolchain-baseline.py` checks both declarations and retained `procps`. Runtime availability awaits orchestrator deployment.

## WR-CVE-NIXOS-CLOSURE-TRIAGE — configured dismissals / accepted containment / updates deferred (2026-10-03)

- **Symptom:** 269 Grype NixOS closure alerts include product-name collisions, version-ordering errors, distro-specific/already-fixed findings, and retained legacy libraries.
- **Root cause / producer:** Grype CPE/version matching differs from Nix package identity and patch metadata; upstream appimage-run and playwright-webkit closures retain old dependencies. Updating Playwright alone does not replace its bundled libraries.
- **Triage state:** Batch 1 is recorded in d2d8e00e. Batch 2's supplied nixpkgs-unstable Playwright 1.63.0 dry-run still includes libxml2 2.13.9 and libjxl 0.8.2. System sqlite/libcap/libusb/nghttp2/gdk-pixbuf lock updates remain deferred to owner-directed tiered updates to avoid 120+ derivation rebuilds.
- **Interim mitigation:** Batch 3 `.grype.yaml` contains explicit CVE+package reasons and is loaded by both live closure scan paths. Batch 4 accepts legacy libpng 1.2.59 in the AppImage bubblewrap sandbox and WebKit's bundled libraries in the Playwright browser sandbox, plus libmad audio decoding through roc-toolkit and busybox internal helpers. Only the supplied libpng/libmad/busybox pairs are suppressed; WebKit is documented without blanket ignores.
- **Class / severity:** Accepted contained risk (`d`) plus scanner false positives (`a`); underlying CVE severities remain unchanged. Lack of an upstream fix alone does not establish a false positive; supplied disputed/no-fix rationales remain reviewable exceptions.
- **Fix path:** Reassess rules against upstream advisories and actual installed versions/consumers, update producer bundles when fixes exist, perform owner-directed tiered lock updates, then rescan. Package-name rules are not version/path scoped, so reassess whenever the closure changes.
- **Evidence / limits:** SSOT `.agents/plans/cve-triage-20261002/TRIAGE.md`; dry-run findings and containment supplied by orchestrator. Focused tests verify config forwarding, not runtime containment or reduced live alert counts. No deployment, lock update, or GitHub dismissal performed by this slice.

## WR-AQ-CTX-FRESHNESS-SERIAL-SPAWN (2026-10-05) — FIXED

- **Symptom:** `aq-ctx-freshness --check` and `--ensure` took 25–35 seconds on every Git checkout hook, worktree creation, and session-start invocation.
- **Root cause / producer:** `find_graph_dir()` in `scripts/ai/aq-ctx-freshness` executed a `while IFS= read` loop over `find ... -name index.json` that spawned a separate `python3` subprocess for every graph (211+ graphs) and called `json.load()` on each 7.3 MB index file, parsing 1.54 GB of JSON AST/symbol dictionaries serially.
- **Fix path:** Replaced serial subshell loop with a single `python3` invocation that reads bounded 1,024-byte headers from `index.json` files (where `project_root` lives on line 3), extracts candidate roots with regex, checks exact match first, and falls back to git-common directory checks for worktrees.
- **Class / severity:** Performance / latency friction; medium. Status: FIXED 2026-10-05.
- **Evidence:** Runtime dropped from 25.060s to 0.134s (a 187x speedup). Validated by `bash -n scripts/ai/aq-ctx-freshness` and `scripts/testing/test-aq-ctx-freshness.sh` PASS.

## WR-QA-EVIDENCE-SYSTEMD-MOUNT (2026-10-05) — FIXED

- **Symptom:** `ai-stack-health-monitor.service` failed every 15 minutes with `[aq-qa] immutable evidence unavailable: ROOT_MOUNT_TARGET: /var/lib/ai-stack/hybrid/telemetry` and pushed recurring high-severity alerts (`attn-14dd7fb8`) to the attention queue.
- **Root cause / producer:** `scripts/ai/lib/qa_evidence_store.py`'s `mount_targets()` treated all entries in `/proc/self/mountinfo` as forbidden mount targets. When systemd runs services under `ProtectSystem=strict` with `ReadWritePaths = [ ... "/var/lib/ai-stack/hybrid/telemetry" ]`, it establishes a namespace self-bind mount (`root_within_fs == mount_point` on the same physical filesystem) to permit writing, which tripped `ROOT_MOUNT_TARGET`.
- **Fix path:** Updated `mount_targets()` in `qa_evidence_store.py` to classify mounts: only pseudo-filesystems (`tmpfs`, `ramfs`, `overlay`, `fuse`, `shm`) or redirected mounts (`root_within_fs != mount_point`) are classified as forbidden targets; benign systemd namespace self-bind mounts on durable filesystems are accepted. Added regressions in `scripts/testing/test-telemetry-root-boundary.py`.
- **Class / severity:** Stability / observability false-alarm; medium. Status: FIXED 2026-10-05.
- **Evidence:** `scripts/testing/test-telemetry-root-boundary.py` PASS (6/6 tests), `scripts/testing/test-qa-evidence-store.py` PASS (4/4 tests), `scripts/testing/test-ai-stack-health-monitor.py` PASS.

## WR-CI-NIX-BUILD-RUNNER-DISK-SPACE (2026-10-05) — FIXED

- **Symptom:** CI job `Nix Build / Build NixOS Configuration` failed with `System.IO.IOException: No space left on device` during `nix build .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel`.
- **Root cause / producer:** `.github/workflows/nix-build.yml` allocated an 8GB swapfile without clearing pre-installed caches and toolchains (`/usr/share/dotnet`, `/opt/ghc`, `/usr/local/lib/android`, `/opt/hostedtoolcache/CodeQL`), leaving under 6GB of disk space on `ubuntu-latest` hosted runners.
- **Fix path:** Added `Free disk space` step to `.github/workflows/nix-build.yml` before installing Nix, matching the existing production pattern in `.github/workflows/security.yml`.
- **Class / severity:** CI / infra; medium. Status: FIXED 2026-10-05.
- **Evidence:** Prunes ~25-30 GB before Nix evaluation; commit `1b673c8e`.

## WR-AQ-OPTIMIZER-SUDO-AUTH (2026-10-05) — FIXED

- **Symptom:** `aq-optimizer` hangs for up to 3 x 120s = 360s on unattended service restarts (`systemctl restart svc`), blocking `prsi-orchestrator.py execute`.
- **Root cause / producer:** `_restart_service(svc)` in `scripts/ai/aq-optimizer` invoked bare `["systemctl", "restart", svc]` without `--no-ask-password` or `sudo -n`. When executed unprivileged, polkit prompts for interactive credentials, blocking non-interactive runners on stdin.
- **Fix path:** Updated `_restart_service` to run `sudo -n systemctl restart --no-ask-password svc` when non-root with fallback to direct `systemctl restart --no-ask-password svc`.
- **Class / severity:** T1 tooling / automation; medium. Status: FIXED 2026-10-05.
- **Evidence:** `python3 scripts/automation/prsi-orchestrator.py execute` runs in 1.1s with 2 actions applied without hanging; commit `ba30137d`.

## WR-PYTEST-ASYNCIO-DECLARATION (2026-10-05) — FIXED

- **Symptom:** Every pytest test invocation produced `PytestConfigWarning: Unknown config option: asyncio_mode` and `asyncio_default_fixture_loop_scope`.
- **Root cause / producer:** `pytest.ini` declares `asyncio_mode = auto`, but `nix/home/base.nix` and `nix/modules/core/base.nix` only included `pytest-cov` and `pytest-xdist`, omitting `pytest-asyncio`.
- **Fix path:** Declared `ps."pytest-asyncio"` in `nix/home/base.nix` and `nix/modules/core/base.nix`.
- **Class / severity:** T1 tooling / test hygiene; low. Status: FIXED 2026-10-05.
- **Evidence:** `nix eval .#nixosConfigurations.hyperd-ai-dev.pkgs.python3Packages.pytest-asyncio.name` evaluates `"python3.13-pytest-asyncio-1.3.0"`; `check-package-count-drift.sh` PASS; commit `ba30137d`.
