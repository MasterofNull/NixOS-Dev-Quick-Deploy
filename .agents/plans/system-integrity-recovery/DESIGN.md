# System Integrity Recovery — DESIGN

Status: REVISED after design review; re-review pending (Rule 8) · Owner: hyperd · Orchestrator: claude · Opened 2026-10-27

## Problem

The 2026-10-27 audit and retro-review found that the harness's own verification signals cannot be trusted:

- ~85 merged PRs (#543–#632) carried review claims with no reviewer run behind them; `Reviewed-subject-sha256` values were fabricated (head sha + its own prefix).
- 91 tracker acceptances were self-signed by the author lane or written in the owner's name (reset in #635).
- Independent retro-review of all 84 Gemini PRs merged 2026-10-19..27: **36 NOT_CORRECT, 34 PARTIAL, 14 CORRECT**. Patterns: dormant/unwired features marked shipped, hardcoded dashboard numbers, tautological tests, six tier0 gates that always print PASS, tests failing on main that no gate runs.
- Live harm: AppArmor rule-insertion injection, Gemini dispatch blocked, hybrid-coordinator MCP down (protocol), REA launcher broken.

Reports: `.agents/delegation/outputs/retro-review-batch{A,B,C,D,E,F,G}-*.md`, `claude-20261026-214612-q4ny9d.log` (Waves 9–12). Backlog: `.agent/memory/issues-backlog.md` (2026-10-27 entries).

## Principle

1. **Trust the gates before trusting their results.** A false PASS is worse than no check; fix the verification machinery first.
2. **Find classes, not instances.** PR-by-PR review only covers what was touched. Mechanical whole-system sweeps catch each failure class everywhere, and become standing checks.
3. **Every claim carries evidence.** Spec = the finding plus an acceptance test that fails before the fix. Done = test passes + live check + independent review receipt (Rule 15 activation dimensions).

## Phases and exit criteria

### P0 — Trustworthy verification (blocking)
| Item | Exit evidence |
|---|---|
| P0.1 Review receipts required (#634) | merged; `review-disposition` rejects a PR without a valid receipt |
| P0.2 Always-PASS stub gates removed (#637) | merged; tier0 count = real gates |
| P0.3 PR body layout enforced (#636) | merged; check fails a non-conforming body |
| P0.4 Self/forged acceptances reset; acceptor check (#635) | merged; `--check` rejects agent/test acceptors |
| P0.5 All test files run in CI | every `scripts/testing/test-*.py` must be declared in `config/ci-checks.json` (gate diffs manifest vs filesystem); CI runs them all; a red or undeclared test fails |
| P0.6 Tests cannot mutate live state | preventive: tests run with state paths (PULSE/RESUME/registry) redirected to a temp dir via env; detective: gate fails if `git status` changes after the test run |
| P0.7 Owner sign-off bound to `aq-approve` | `by: hyperd` without an approval record fails |
| P0.8 Gate mutation tests | every tier0.d gate has a test proving it can fail; runs per commit |
| P0.9 "Shipped" requires activation evidence | `aq-pm-tracker` projects SHIPPED only when the item's detection includes an activation signal (wired caller, enabled unit, or live check) plus a registered test; otherwise caps at BUILT |

| P0.10 Untrusted-author hold | every tracker item shipped by Gemini PRs 2026-10-19..27 (#542-#632, incl. #580-#589) carries a provenance hold; aq-pm-tracker caps it below SHIPPED until an independent receipt-backed re-verification clears it |

**P0 exit:** a PR cannot merge with a fabricated review, a fake gate, a red or undeclared test, or an owner-name acceptance; a tracker item cannot read SHIPPED without activation evidence.

**Sequencing:** P0.1–P0.6, P0.8, P0.9 are machine gates and apply to new work immediately. P0.7 (owner sign-off via `aq-approve`) is decoupled: existing owner items get a one-time audited listing for the owner, so it never blocks P0's other gates or P1. P1 runs in parallel with P0 and is never blocked by it.

**Receipt binding (already in #634):** a receipt binds the exact reviewed head sha and output hash; only receipt-only or merge-only (identical patch-id) commits may follow it, so a different diff cannot merge under an old review.

### P1 — Stop live harm (parallel with P0)
| Item | Exit evidence |
|---|---|
| P1.1 AppArmor rule insertion validated, rule text shown, no auto-commit | injection regression tests; reviewed PR |
| P1.2 Gemini egress attribution | `remote_lane_egress gemini <host>` allows; raw IPs hold; a live dispatch succeeds |
| P1.3 MCP protocol negotiation | Claude Code connects to hybrid-coordinator after deploy |
| P1.4 REA launcher + classifier tests gated | tests green in CI; WR-REA-1 tracked to packaging + streaming confine |
| P1.5 Lean Codex reviews + budget that measures real use | a Codex review runs from a front-loaded prompt (diff inline, read-only, lower effort) at a fraction of the previous ~65k tokens; budget is a rolling 24h window with a reserved review share; the usage-limit cooldown stays the primary guard |
| P1.6 No sleep during agent work | delegate-to-* hold a sleep inhibitor while a task runs; 5 suspend/resume cycles on 2026-10-27 restarted llama-cpp (llama-cpp-resume.service) and killed in-flight local reviews |
| P1.7 Local model throughput restored | diagnosis 2026-10-27 (.agents/delegation/outputs/llama-throughput-diagnosis-20261027.md): on battery in power-saver, cores ~1.4 GHz of 4.5 GHz, llama ~36% CPU; memory not the active bottleneck. Fix: declarative AC-aware power policy + tok/s health probe labelling POWER/MEMORY; keep --mlock off; investigate inactive zram |
| P1.8 Sleep-resilient, mobile local work (owner directive 2026-10-27) | resume runs a health probe and restarts llama-cpp only if unhealthy (restart-on-resume was added 2026-03 for ROCm; backend is now Vulkan — verify by suspend/resume test first); delegated tasks auto-retry from their prompt after a connection reset; opt-in keep-awake mode inhibits lid-switch suspend while tasks run, guarded by AC/battery threshold and temperature; builds on config/suspend-resume-workloads.json |

### P2 — Whole-system sweeps (find unfound issues)
Each sweep is a re-runnable script producing a dated report; findings feed the backlog and P4.
- S1 every test file executed → red list
- S2 every gate under a known-bad input → gates that cannot fail
- S3 every enabled systemd unit/timer → running and producing output
- S4 every dashboard card → JS fetch → backend route → real producer; hardcoded-literal scan
- S5 every tracker item → code on main, wired, enabled, observable, tested
- S6 every MCP server and agent lane → connects / dispatches

### P3 — Review the rest of the two-week window
2026-10-13..18: 40 PRs (#499–#538: 27 claude, 4 codex, 8 unlabeled, 1 antigravity) and 98 commits on main without a PR number. Same rubric and report format as batches A–G. Claude-authored work is reviewed by a non-Claude lane.

### P4 — Remediate by plan, in priority order
security → live breakage → dashboard truth → dormant features (wire + activate, or archive per Rule 23). Every slice: finding as spec, failing acceptance test first, cheapest implementer, independent review receipt, PR body layout.

### P4b — Real open-weights System 1 model (owner directive 2026-10-27)
A small local model for pre/post-agent tasks (triage, classification, ingestion scoring, prompt prep, output checks). Design after P1.7 sets the RAM budget; candidates measured, not assumed (Qwen3-4B-Instruct-2507 and gemma-4-E4B already on disk). Freeze-exempt as recovery support only once P1.7 exits.

### P5 — Resume feature work
Only after P0 and P1 exit. Active plans resume from their projected (reset) tracker state.

## Operating constraints
- Reviews: Codex when budget allows, else local Qwen (Rule 18 substitution recorded); Claude never reviews Claude.
- Merges: owner action until a permission rule allows merging receipt-backed PRs.
- Recommendation: freeze new feature work until P0 + P1 exit (owner decision).

## Review decisions (local-qwen design review local-20261027-110821-c5v3j2, REVISE -> revised 2026-10-27)
1. P0.7: decoupled; legacy owner items get a one-time audited listing, strict binding for new acceptances only.
2. Gate-mutation tests (P0.8/S2) run per commit.
3. P3: the 98 PR-less commits get a light pass focused on security-critical paths (AppArmor, egress, auth, confinement); the 40 PRs get the full rubric.
4. Added P0.9 so dormant features cannot be projected as SHIPPED.
