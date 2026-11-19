# Enable dormant features, batch A: evidence (2026-11-19)

Owner rule 2026-11-19: a dormant feature found is enabled, validated end to end, tested, and what enabling breaks is fixed.
Inventory: `.agents/delegation/outputs/dormant-features-inventory-20261119.md`. Author lane: Simurg@claude/sonnet.

## 1. Objective
Activate five batch-A items: aq-scoreboard (S4), aq-context-packet (S1), the failed ai-prompt-eval.service, the unlabeled PULSE writer in aq-local-training-loop, and read-only verification of activationAutoRevert.

## 2. Workflow/Session IDs
Branch `feat/enable-dormant-batch-a` from origin/main, worktree `.agents/delegation/worktrees/dormant-batch-a`. Orchestrator Simurg@claude/opus-5.5#da0ef470. Timer stagger and GitHub settings are out of scope (own branch / owner decision).

## 3. Delegation Decision
Bounded implementer slice per Rule 17 (Sonnet override). Review by a non-author lane is the orchestrator's to route (aq-land); this slice does not self-review.

## 4. Commands Executed
- `scripts/ai/aq-scoreboard` made +x; `scripts/ai` is already on PATH for every sibling aq-* tool, so no Nix change.
- `aq-land` records `tier0` (checkpoint `tier0`/`tier0_head`) after tier0 passes in `stage_commit` and `gate_committed`; `record_outcome` passes it only when `tier0_head` equals the landed head (hardcoded `tier0=None` at old line 714 was the producer of the null).
- `lib/outcome_receipt.py`: when the registry row has no `tokens_in/out` (no delegate ever fills them), read codex's `tokens used N` from the run's output log and store `{"in": null, "out": null, "total": N}`; `aq-scoreboard` sums and prints `total`.
- `delegate-to-local`: for repo files named in the prompt (max 3, `<400 KB`, prompt `<8000` chars) append `aq-context-packet` output; fail-open (any error leaves the prompt as is); kill switch `AQ_CONTEXT_PACKET=0`.
- `aq-prompt-eval`: consecutive-transport-error breaker (`AQ_PROMPT_EVAL_MAX_CONSECUTIVE_ERRORS`, default 3) and run deadline (`AQ_PROMPT_EVAL_DEADLINE_S`, default 3000 < unit TimeoutStartSec 3600); aborted runs exit 1 and never write a partial score.
- `aq-local-training-loop._pulse`: label via `agent_slot(..., model=$AQ_INSTANCE_MODEL or "local", session=<run time>)`.

## 5. Validation Evidence
- Item 1, live: `aq-scoreboard --dir <live delegation dir>` runs and prints the 5 existing receipts (all `tier0: null`, tokens unknown, written before this fix; the log is append-only, so they are not rewritten). Producer proven against the live registry and real codex logs in a temp dir: `Tokens codex: in=0 out=0 total=40781 (no in/out split) (known runs 1, unknown runs 1)` and receipt `"tier0": "pass"`. Gemini token counts stay unknown: the gemini CLI log carries none (limitation).
- Item 2, live: `delegate-to-local --mode direct ... --prompt "review scripts/ai/aq-scoreboard briefly"` against a dead llama port printed `Context packet attached: 1 file(s)`. Preflight then refused for size with and without the packet (measured 10933 vs 10894 with `AQ_CONTEXT_PACKET=0`; the byte upper bound is already over 8192 for any direct prompt), so the packet adds about 40 tokens here and was not the cause.
- Item 3, diagnosis (journal, 2026-11-18 07:29-08:29): every LLM call hit the 300 s client timeout (`ERROR ... timed out` x12), the run ground on until `TimeoutStartSec=3600` killed it (`Result: timeout`). Cause: the single-slot llama.cpp was saturated by the 07:29 timer herd (load5 32, 80 C); abandoned requests kept the slot busy. Proof the script is sound when the backend is free: manual `python3 scripts/ai/aq-prompt-eval --dry-run --id query_expansion_nixos` at 20:03 PST, 3/3 PASS (19.9 s to 81.8 s per call), overall 100%.
- Item 4: `test-training-loop-pulse-label.py` PASS (`[Simurg@local/local#121750] [run]`); old live lines show the bare `[aq-local-training-loop]`.
- Item 5, read-only: `systemctl cat activation-auto-revert.timer` and `list-unit-files 'activation-auto*'` find nothing on the running system, and `/run/current-system/etc/systemd/system` has no `*revert*` unit. The module (`nix/modules/services/activation-auto-revert-guard.nix:90`) defines both under `mkIf cfg.enable`, so the effective deployed value is false. `nix/hosts/hyperd/deploy-options.local.nix:18` forces true but is gitignored (`.gitignore:162`) and imported through `builtins.pathExists` (`flake.nix:273`), so a flake build from a git tree does not see it. `nixos-option` cannot resolve the path in this repo.
- Tests (all PASS): `test-outcome-receipt` (6), `test-aq-land-outcome` (4), `test-aq-land` (72), `test-collect-trajectories` (15), `test-aq-context-packet`, `test-delegate-local-context-packet` (4), `test-prompt-eval-transport-guard` (2 checks), `test-training-loop-pulse-label`, `test-training-loop-trust-gates`.

## 6. Rollback Plan
Revert the commit. Runtime kill switches: `AQ_CONTEXT_PACKET=0`; `AQ_PROMPT_EVAL_MAX_CONSECUTIVE_ERRORS=999 AQ_PROMPT_EVAL_DEADLINE_S=99999`. Receipts and registry are append-only and untouched.

## 7. Residual Risk
- ai-prompt-eval can still fail when llama is saturated; it now fails in about 15 min, frees the slot, and the timer retries. The herd itself is the timer-stagger branch's job. Unit stays failed until the owner resets it.
- The packet can push a near-limit local prompt over the preflight cap (it refuses with exit 3, never launches); the kill switch removes it.
- Codex token totals have no in/out split; gemini and local have none at all.
- Item 5 needs an owner decision: wire the local file into the build or commit the option declaratively.

## 8. Hint Feedback
Inventory pointer "aq-land ~714" was accurate for tier0 but the tokens null had a second producer (registry rows are created with `tokens_in/out: null` and nothing updates them).

## Activation attestation (Rule 15)
| Item | Integrated | ON | Validated e2e | Observable | Intervenable | PM-tracked |
|---|---|---|---|---|---|---|
| aq-scoreboard + receipts | +x, on PATH, fed by aq-land | yes (runs every landing) | yes, live registry + real codex log | scoreboard output | read-only CLI | deferral: tracker projects status; no hand edit |
| aq-context-packet | delegate-to-local | yes, default | yes, real shim run | `Context packet attached` line | `AQ_CONTEXT_PACKET=0` | as above |
| ai-prompt-eval | script fixed | timer unchanged | manual run PASS; unit needs owner reset + rebuild-free restart (script is read from the checkout) | journal ABORT line | env vars | as above |
| training-loop PULSE label | yes | yes | test + format | PULSE.log | `PERSONA=0` | as above |
| activationAutoRevert | n/a | NOT ON (effective false) | verified read-only | n/a | owner decision | deferred to owner, 2026-11-19 |
