# Enable dormant features, batch B (10 items)

Date: 2026-11-19
Task ID: HF-DORMANT-BATCH-B-20261119
Branch: feat/enable-dormant-batch-b (from origin/main ee125bfa5)

## Objective
- Owner 2026-11-19: "many of our system features and tools are still disabled"; every change is meant to be live at the next rebuild. Inventory: `.agents/delegation/outputs/dormant-features-inventory-20261119.md` section "Batches (B)". Rule: enable, validate end to end, test, fix; hold only what is unsafe without the owner, with a recommendation.
- Result: 3 enabled, 1 enabled+wired (S5 collector), 2 fixed/removed (decorative flags), 1 root-cause fix (ai-prompt-eval), 3 held. Per-item table in "Activation attestation".
- Finding that changes the picture: aq-decide has been running in shadow inside the code since DEC-S3 (3996 decisions in `~/.local/state/aq-decide/decisions.jsonl`, last row today), because `AQ_DECIDE` defaults to on and `dispatch.classify_task_type` calls it. The Nix flags were the dormant part. The shadow log was also unmeasurable: it never stored the caller's own answer, so `aq-decide shadow-report` printed `agreement_rate 0.0` over 2837 shadow rows. Fixed.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator Simurg@claude/opus-5.5#da0ef470)
- Session ID: Simurg@claude/sonnet (batch B implementer). No review, merge or push by this lane.

## Delegation Decision
- Sonnet 5.5 implementer per Rule 17; independent review is the orchestrator's to route (never this lane).
- Coordination: branch feat/rebuild-enablement-20261119 edits `nix/hosts/hyperd/default.nix` plus its own plan/evidence files. This branch touches none of those; profile entries live in a distinct block of `nix/modules/profiles/ai-dev.nix` (after the agentAuth lines) and do not touch `activationAutoRevert`, `agenticToolchain` or `deploy-options*`. Checked with `git -C .../rebuild-enablement diff origin/main --stat` before commit.

## Commands Executed
```bash
git worktree add -b feat/enable-dormant-batch-b .agents/delegation/worktrees/dormant-batch-b origin/main
nice -n 19 nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.mySystem.aiStack --apply '...'   # ON/OFF proof
nice -n 19 nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.services --apply 's: {pe = ...SuccessExitStatus; wr = ...ExecStartPost;}'
nice -n 19 python3 scripts/testing/test-<name>.py   # serial, see Validation Evidence
scripts/governance/tier0-validation-gate.sh --pre-commit   # once, alone
```

## Validation Evidence
nix eval (hyperd-ai-dev, this worktree):
```
{"aq":true,"bit":false,"emb":false,"hp":false,"mode":"shadow","rag":"off","tp":"shadow","train":false,"wdb":false}
systemd.services: ai-prompt-eval SuccessExitStatus = "75"; ai-weekly-report ExecStartPost = "-python3 .../scripts/ai/aq-skill-eval"
tmpfiles: d /var/lib/aq-decide 0755 root root -, d /var/lib/aq-decide/state 0700 root root -
```
Tests (all run serially under nice 19): `test-collect-trajectories.py` (18, incl. 3 new: PR-788-shaped paths clean, real blobs still caught, aq-land wiring), `test-prompt-eval-transport-guard.py` (extended: deferral after 3 failures exits 75 with no score written; DEFER_AFTER=0 keeps exit 1), `test-skill-eval.py` (3, incl. the `--prune-candidates` regression and the weekly-report wiring), `test-aq-decide-shadow-incumbent.py` (6 new: incumbent logged, bad incumbent ignored, report agreement uses it, dispatch passes it, profile stages shadow, held options stay off, dead flags gone), `test-aq-decide-s5-s6/s8/s9-s10.py`, `test-outcome-receipt.py`, `test-aq-land-outcome.py`, `test-functional-prompt-eval.py` all pass. tier0 summary: see the commit body / final report.

## Activation attestation (Rule 15), per item
Dimensions: integrated / ON / validated e2e / observable / intervenable / PM-tracked.

1. aqDecide (core engine) - ENABLED in SHADOW. `aqDecide.enable`, `mode=shadow`, `integrations.taskProfile.mode=shadow` (ai-dev.nix, mkDefault). Integrated: `dispatch.classify_task_type` (live) and coordinator `POST /decide`. ON: in-code since DEC-S3; Nix state dirs and mode now declared. Validated: nix eval above; shadow-report over live log. Observable: `aq-decide shadow-report` now reports `compared_decisions` and a real agreement rate (needs rebuild + new traffic to populate `incumbent`). Intervenable: `AQ_DECIDE=0` kill switch, flip mode to `off`. Resource: in-process 0.7 ms p50, no service, no RAM beyond a 2^16 sparse model. Outward effects: none (local log, 0600). Limitation: the Nix `mode`/`integrations.*` options have no consumer yet (only taskProfile has a call site and it is in-code shadow); retryEscalate/rag/approvals/egress stay `off` because nothing calls them. Follow-up: wire mode into the call sites when a second integration gets a caller (otherwise Rule 23 says delete the unused option branches).
2. aqDecide embedder + train.timer - HELD. Embedder: `llama-cpp-aqdecide` serves a model but no fetch unit exists for `bge-small` (design 8.1 step 2 not built), and DESIGN says T1 is "not before the shadow data justifies it"; an external HF download is outward-facing. train.timer: option has no consumer. Recommend: enable only after 150 labelled rows/class (DESIGN 4.3) and a fetch unit; ~37 MB model, CPU `-ngl 0`, ~100 MB RSS.
3. workflowDeviationBroker - HELD. Its own design packet (C1B, "Immediate C2 release gate") says it "cannot be enabled until" the C2 slice lands: Phase-0 e2e check, command-center projections, wrapper failure hooks, dogfood canary. No C2 code exists (no aq-qa check, only `aq-workflow-deviation` CLI). Enabling now would add a socket nothing writes to and no check reads. Recommend: schedule the C2 slice; enabling is then one line (`workflowDeviationBroker.enable = lib.mkDefault true`, needs the explicit primary-user uid, which the host already sets).
4. headroomProxy - HELD. `nix/modules/services/headroom-proxy.nix` documents its Python env as INCOMPLETE (headroom-ai, litellm>=1.86.2, magika, sqlite-vec are not in nixpkgs-25.11). Enabling also redirects switchboard `llamaUrl` to :8787 (switchboard.nix:26), so a broken proxy would take down every local request. Recommend: finish packaging first, then A/B latency on the 5 tok/s lane.
5. S5 trajectory collector - ENABLED (wired). Root cause of the PR 788 quarantine fixed in `outcome_receipt.scan`: lowercase/upper single-case slash paths (`agent/PROJECT-DEPLOY-VALIDATION-PRD`) exceeded the 4.0-bit entropy heuristic only by length; they are exempt, real tokens (mixed case, `+`, `=`) still caught. Wired: `aq-land` runs the collector for the landed PR right after the outcome receipt, non-fatal (WARN), 120 s cap, `AQ_TRAJECTORY_COLLECT=0` kill switch. Collector `OSError` now exits 2 with one line instead of a traceback. Validated: new tests; `test-aq-land-outcome.py`. Observable: `trajectories.jsonl` / `.quarantine.jsonl` in the delegation dir; `aq-scoreboard` reads them. Outward: none. PR 788 itself stays in the quarantine file (settled PRs are not re-evaluated); a copy of that row is archived at `.agent/archive/20261117-trajectories-quarantine-pr788-fp.jsonl`. To collect it, remove its row from `trajectories.quarantine.jsonl` (archive, Rule 12) and run `scripts/data/collect-verified-trajectories.py --pr 788` (owner or orchestrator call).
6. aq-skill-eval - WIRED. Fixed a real bug (`args.prune-candidates` raised AttributeError, so the flag never worked). Called weekly from `ai-weekly-report` via `ExecStartPost` (read-only, `-` prefix so it never fails the report); output lands in the journal. Observable: `journalctl -u ai-weekly-report`. Current output: 66 skills, 2 prune candidates (`auto-generated` has no SKILL.md, `template-skill` placeholder), left for the owner per Rule 12.
7. cross-encoder (`AI_CROSS_ENCODER_ENABLED`) - HELD. The consumer exists (`query_expansion.py`) but `sentence_transformers` is not in any Nix env and the model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) would download from HF at runtime; no measurement exists of the added CPU latency on this box. Recommend: add the dependency declaratively, run a paired before/after latency probe, then a profile flag.
8. bitnet - HELD. Options only (`options.nix:1683`); no service, package or model exist, so enabling is a no-op. Recommend: keep as roadmap or delete the option block (Rule 23) in a later slice; owner call.
9. Decorative flags - REMOVED. `QUERY_EXPANSION_ENABLED`, `MULTI_TURN_QUERY_EXPANSION` (no consumer, per 2026-10-29-ci-activation-wave1) and `TRADING_ENABLE_CHECKPOINTS` + `checkpoint_dir` (`get_config()` has no caller; no checkpoint code) deleted from code, `feature-defaults.yaml`, the two audit shell arrays and the docs that told users to set them. `AI_LLM_EXPANSION_ENABLED` (the live consumer) is untouched. Test asserts they stay gone.
10. ai-prompt-eval failed unit - ROOT-CAUSE FIX. Journal: 07:29 run (the 26-timer herd, load5 about 32) timed out all 11 cases at 300 s each until systemd killed it at 3600 s. The stagger fix (2026-11-18-timer-stagger) removes the herd; the remaining producer defect is that the eval kept burning one full timeout per case on a busy single slot. `aq-prompt-eval` now defers after `AQ_PROMPT_EVAL_DEFER_AFTER` (3) consecutive transport failures, writes no scores, exits 75; the unit has `SuccessExitStatus=75` so a deferral is retried by the next timer instead of leaving a failed unit and a QA phase-0 alert. Trade-off (Rule 19): a persistently busy host would defer silently; the journal line `DEFER eval deferred...` is the signal and the leaderboard `last_evaluated` date goes stale. The current failed state clears with `systemctl reset-failed ai-prompt-eval` (owner act) or the next rebuild.

## Rollback Plan
- `git revert` the commit; rebuild. Fast switches: `AQ_DECIDE=0`; `AQ_TRAJECTORY_COLLECT=0`; `mySystem.aiStack.aqDecide.enable = false` in host config (mkDefault, so the host wins); `AQ_PROMPT_EVAL_DEFER_AFTER=0` restores the old behaviour.

## Residual Risk
- Held items (2, 3, 4, 7, 8) are not enabled; each has a stated unblocker above. This is not a claim that batch B is fully active.
- aq-land now spawns a subprocess after merge; failure only warns. Adds up to the collector runtime (git/gh numstat) to each landing.
- The `incumbent` field only exists in rows written after the rebuild; the existing 2837 shadow rows stay uncomparable.
- Rebuild needed for: ai-dev.nix flags, ai-prompt-eval unit, weekly report unit. Script changes (aq-land, collector, aq-decide, dispatch) take effect on checkout sync.

## Post-rebuild validation steps (owner terminal)
1. `systemctl show ai-prompt-eval -p SuccessExitStatus` shows 75; then `sudo systemctl reset-failed ai-prompt-eval` and confirm QA phase 0 turns green (`aq-qa 0`).
2. `ls -ld /var/lib/aq-decide /var/lib/aq-decide/state` exist (0755/0700 root).
3. After some dispatches: `scripts/ai/aq-decide shadow-report --question task_profile` shows `compared_decisions` > 0 and a numeric `agreement_rate`.
4. After the next `aq-land`: `scripts/ai/aq-scoreboard` or `tail -1 .agents/delegation/trajectories.jsonl` shows the new landing, no "WARN trajectory" on stderr.
5. After Sunday 08:00: `journalctl -u ai-weekly-report | grep "Evaluated"` shows the skill-eval summary.

## Hint Feedback
- aq-hints was not consulted; locations came from `rg` over nix/, scripts/ and the plan docs named in the inventory. No hint feedback to submit.
