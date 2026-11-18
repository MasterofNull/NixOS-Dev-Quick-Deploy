# F3 MVP FREEZE (rev 2)

Frozen: 2026-11-14. Source draft: `F3-MVP-FREEZE-DRAFT-rev2.md`, sha256 `1675bbc1b429642b30d8eff7619638bf279fb782f35e00cf9e1c078ce259f4dc`.
Reviewers: Codex PLAN_READY_WITH_FOLLOWUPS (`codex-20261114-172254-y10co7`), local Qwen PLAN_READY_WITH_FOLLOWUPS (`local-20261114-094351-5czah4`). Both followups are satisfied (S4b shipped as #782; the live fixture rows are archived).
Gemini, the author of the pillar, is out until 2026-11-20; its advisory review is queued in `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` and is advisory unless it finds a real defect (Rule 18).
The text below is the draft verbatim, except one citation reformatted so the plan-path gate resolves it (`run-test-group.py:8,49` became `run-test-group.py` (lines 8, 49)). The Gemini review copy has two citation touch-ups for the same gate.

---

# F3 MVP FREEZE DRAFT rev 2: verified trajectories (offline collector); System 1 telemetry deferred
Changes from rev 1 (sha 4fcf42b7); C = Codex REQUEST_REVISION, L = local Qwen PLAN_READY_WITH_FOLLOWUPS:
1. C1/C2 (S6 placement, "cannot change behaviour"): S6 DEFERRED and renamed "gate/size telemetry (prototype)"; the observation contract is written in section 3 for a later freeze. L(b)/L(c) uncaught-exception point is absorbed there (bounded, nonblocking, drop-on-overload).
2. C3 + C4 (S5 privacy, offline collector, aq-scoreboard ownership, diff range, merge_sha, 0600): adopted in section 2. L(b) `files:null` fail-open: adopted, an unreachable range now quarantines the row (identifiers only) and is retried.
3. Open Q2 (L and C agree: isolation first): new prerequisite S4b (section 2a), must land before S5 activates.
4. Open Q1 (C: include RC-then-PASS; L: PASS only): decided C's way plus a rounds count. Open Q3: S6 deferred (both agree). L(a) Q recommendations otherwise match.
5. Removed the five-day supply forecast and the 12k-chars=8k-tokens claim (sections 3, 6); citations re-verified against origin/main f4e0e5f66: `aq-land:679-691`, `:688`, `delegation_dir.py:20-30`, `delegate-to-local:319-326`.
Authors: Simurg@claude/sonnet (draft); orchestrator Simurg@claude/opus-5.5#da0ef470. Design only. Citations are `origin/main:<path>:<line>` (f4e0e5f66). UNVERIFIED = not checked. Working tree = gitignored runtime state.

## 0. Prototype verdicts (Gemini's, `.agents/delegation/outputs/frugal-sota-leadership/`)
- `collect_verified_trajectories_prototype.py`: KEEP redact-then-scan-then-quarantine. DROP its regexes (:18-33,:58-76): `scripts/ai/lib/outcome_receipt.py` ships `scan` (:35), `_redact` (:43; wraps `telemetry_privacy.redact_secrets`) and `_append` (:54). Two scanners drift; S5 imports them.
- `system1_router_prototype.py`: KEEP the disposition vocabulary (defer / substitute_remote). DROP its vitals reader and 0.70/0.55/80C thresholds: `power_gate.py` (S3) owns them (`evaluate` :93). DROP "<20ms" and 90C: unmeasured KPIs.

## 1. What the real data source has (S4 receipt, `outcome_receipt.py:77` `record_landing`)
Present: `schema, pr, head_sha, author_lane, reviewer_lanes, review_verdicts, request_changes_rounds, tier0, ci, tier0_failures, ci_failures, tokens{lane:{in,out}}, recorded_at`.
Absent: task text or slice id; files touched; diff; context packet (S1 not on main, UNVERIFIED); review `run_id` (used for token lookup only); merge sha; author-lane tokens. `tier0` is always `None`: `aq-land:688`, inside `record_outcome` `aq-land:679-691`.
Consequence: MVP trajectory = outcome facts + git-derived path stats. Diff bodies and rejected-attempt text are DEFERRED (no source, widest secret surface).

## 2. Slice S5: offline trajectory collector (one PR, after S4b)
- Shape: a CLI `scripts/data/collect-verified-trajectories.py`, run by hand or timer after landings. It is NOT called from `aq-land` and never adds landing latency; `aq-land` is not modified (`record_outcome` stays as is, `aq-land:679-691`).
- Owned paths: `scripts/data/collect-verified-trajectories.py` (NEW), `scripts/ai/lib/outcome_receipt.py` (additive helper only, no schema change), `scripts/ai/aq-scoreboard` (counters), `scripts/testing/test-collect-trajectories.py` (NEW), `config/ci-checks.json`, `.gitignore`.
- Eligibility: receipt row with `PASS` in `review_verdicts`, `ci=="pass"`, `author_lane not in reviewer_lanes` (independent review). REQUEST_CHANGES-then-PASS histories are INCLUDED; `rejected_rounds = request_changes_rounds` is kept as a count only, not as rejected-attempt text (none exists).
- Row = receipt fields + `rejected_rounds` + `files:[{path,added,deleted}]` (paths only) + `merge_sha`. Output: `<delegation dir>/trajectories.jsonl`, dir from `resolve_delegation_dir` (`delegation_dir.py:20-30`, honours `AQ_DELEGATION_DIR`). Idempotent per `pr` (rule as `outcome_receipt.py:99-100`).
- Offline producers (no `aq-land` change): `merge_sha` and the PR base/head come from `gh pr view <n> --json mergeCommit,baseRefOid,headRefOid`. Diff range = `git diff --numstat <baseRefOid>...<headRefOid>`; if a commit is missing locally, fetch `refs/pull/<n>/head` once. If still unreadable: quarantine identifiers only with reason `range_unreachable` and retry next run; never write `files:null` to the main file. `gh` missing or offline: row skipped, counted `receipts_pending`.
- Privacy contract (mirrors `outcome_receipt.py:103-110`): serialise the row, `redacted, found = _redact(...)`, then `found += scan(redacted)`. Both signals count; scanning only the redacted text could admit a detected-and-removed secret. Any finding goes to `trajectories.quarantine.jsonl` and never the main file. If the redactor is unavailable (`_redact` returns `redactor_unavailable`, :43-51), the quarantine row holds `{pr, recorded_at, reasons}` only, never the payload.
- File modes: `_append` sets 0600 only at create (:54-55). The collector must `fstat` each target before writing and refuse (exit nonzero, row not written) if the existing mode has any group/other bit, for both main and quarantine files. Do not silently chmod.
- Kill switch: `AQ_TRAJECTORY_COLLECT=0` (exits 0, writes nothing). Fail-closed for the data; the landing path is untouched.
- Observability: `aq-scoreboard` (reads `outcome-receipts.jsonl`, `aq-scoreboard:2`, `_lines` :15) gains raw counts `trajectories_collected`, `trajectories_quarantined`, `receipts_not_eligible`, `receipts_pending`. No ratios.
- Acceptance (`python3 scripts/testing/test-collect-trajectories.py`, temp `AQ_DELEGATION_DIR`): (a) eligible row written 0600 incl. an RC-then-PASS row with `rejected_rounds>0`; (b) planted `Bearer`/`/run/secrets/` string quarantined and absent from main; (c) a secret that `_redact` removes (so `scan` is clean) is still quarantined via `found`; (d) redactor missing: quarantine row has no payload; (e) pre-existing 0644 main file and 0644 quarantine file each make the collector refuse; (f) self-reviewed row skipped; (g) second run adds 0 rows; (h) kill switch writes nothing; (i) unreachable range quarantines with `range_unreachable`. Plus `aq-scoreboard --json` returns an int for `trajectories_collected`.
- Rollback: revert the PR; archive `trajectories*.jsonl` with `mv` to `.agent/archive/` (Rule 12). Add both to `.gitignore` (receipts file is currently not ignored; whether intended is UNVERIFIED, S5 does not change that).
- Activation (Rule 15): one real run after a real landing, counters visible in `aq-scoreboard`.

## 2a. Prerequisite S4b: test-pollution producer (small, before S5 activation)
- Evidence: working-tree `outcome-receipts.jsonl` (0600) holds one row, PR 77, while main PRs are numbered #765-#780; `power-gate-deferred.jsonl` (mode 0644, so also outside the 0600 convention) holds one `fixture` task row. Both are in the live `.agents/delegation/`.
- Hypothesis, UNVERIFIED: some test or manual run invokes `power_gate.py --defer-log`, `delegate-to-local` or `record_landing` without `AQ_DELEGATION_DIR`; the isolating runner (`scripts/testing/run-test-group.py` (lines 8, 49)) only protects tests run through it. Codex notes the inspected power-gate tests already use temp paths, so the producer must be traced, not assumed. Candidates to check first: `scripts/testing/test-local-power-gate.py`, `test-outcome-receipt.py`, `test-progressive-disclosure-implementation.py` (all reference these files).
- Work: (1) reproduce by running each candidate with the live files hashed before and after; (2) fix the demonstrated live-dir fallback (Rule 19: producer, not a filter); (3) `mv` the confirmed fixture rows' files to `.agent/archive/<date>-fixture-rows/` and keep a note in the PR. If no producer is found, S5 may proceed but its baseline (section 6) is marked polluted/unknown.
- Acceptance: the traced test, run twice, leaves both live files byte-identical (sha256 before/after).

## 3. Slice S6: DEFERRED, "gate/size telemetry (prototype)"; no build in this MVP
Rev 1 put a shadow router in `delegate-to-local` after the gate. That cannot observe rejected dispatches: the gate failure exits at `delegate-to-local:321-323` before `ID="$(task_id)"` (:326), and `power_gate.py` prints text, not its result dict. Observation contract a later freeze must meet:
- One evaluation: the same `power_gate.evaluate` call that decides also supplies the observation (e.g. via a JSON line it already emits or a `--observe-file` option on the gate itself). No second sensor read, no second hysteresis mutation. Gate-disabled runs emit an explicit `gate:"disabled"` observation without evaluating sensors.
- IDs for failed attempts: allocate the dispatch id before the gate (or a separate `attempt_id` joined later), so deferred dispatches carry one. Background status must be passed in explicitly.
- Nonblocking bounded recorder: no synchronous import, subprocess or unbounded file I/O on the dispatch path; bounded queue or best-effort single append with a timeout, drop-on-overload with a dropped-count. Exceptions, unwritable storage and a stalled recorder must not change exit code or status.
- Latency budget: agreed with the owner before build and tested (stalled-recorder test measures added latency against it). Dispatch exit status (5 on defer) compared against `scripts/testing/test-local-power-gate.py`.
- Predictor v0 may use gate state and prompt length only; prompt length in characters is not a token count, so no token-limit claim is made. Local lane only. No text stored. Raw counts with `n`; no accuracy figure until a reviewer-approved sample size is chosen. Live routing stays a separate owner decision.

## 4. Persona P3 integration
Not automatic. Trajectory rows are raw, per-user, local, gitignored; P3 fact files (`.agent/memory/facts/`) are git-tracked and written only by a human-reviewed step from an aggregate. S5 contains no code writing there. P3 path absent on `origin/main` (UNVERIFIED format); this draft depends on nothing from P3.

## 5. Explicitly deferred
Live routing; neural/distilled System 1 and training on trajectories (labeled supply is unmeasured, near zero); diff bodies, `rejected_attempts` text, context packet (no source); "<20ms", 90C, `vw_per_kt`; exemplar retrieval (counts in the 2,500-token cap); remote-lane telemetry, dashboard card (F5), reciprocity (F4); S6 build (section 3).

## 6. Measured baselines (working-tree files, UNVERIFIED as representative)
- Receipts: 1 row (PR 77, author claude, reviewer gemini, PASS, 0 RC rounds, recorded 2026-11-14T03:06:28Z); quarantine file absent. Likely a fixture (S4b), so eligible supply today is 0 to 1. No supply-rate forecast is made: commit rate does not give eligible-receipt rate.
- Registry: `registry.jsonl` 1994 rows, 306 classified (`effective_lane` gemini 170, local 93, codex 39, claude 4); `risk`/`complexity` `unknown` on classified rows. Relevant only to the deferred S6.
- Gate: `power-gate-deferred.jsonl` 1 row, task `fixture`: real deferrals measured = 0.
- Not baselines: tier0 failures (null by construction, `aq-land:688`), author-lane tokens (never recorded).

## 7. Open questions
1. S4b: if tracing finds no producer after the candidates in 2a, accept a "baseline unknown" S5 or block it? Default: proceed, mark unknown.
2. Should `power-gate-deferred.jsonl` be created 0600 like the receipts (currently 0644)? Default: yes, in S4b if the writer is in `power_gate.py`.
3. Collector trigger: manual only, or a user timer? Default: manual for the MVP.
