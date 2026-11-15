# Independent Flagship Review — NixOS AI Harness

**Reviewer:** Independent Flagship Seat (Gemini 4 Argon, High Effort)
**Date:** 2026-11-13
**Scope:** Canonical instructions (`CLAUDE.md`, `AGENTS.md`, `LOCAL-AGENT.md`), `UNIFIED-PROGRAM-PLAN.md`, `PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md` + `DESIGN.md` + `FREEZE.md`, `PROJECT-COLLECTIVE-PERSONA-PRD.md` + P3 rev 3 `DESIGN.md`, `factory-hook-composition-20261112` + `sota-factory-parity-20261112`, `PULSE.log` (lines 940–1091), `issues-backlog.md` (lines 9200–9355), `AGENT-CATCHUP-QUEUE.md`.
**Verification note:** Terminal execution timed out in the sandbox, so `git log --oneline -60` and exact `~181` plan-directory count were not run directly; commit hashes and counts below come from `PULSE.log`, `UNIFIED-PROGRAM-PLAN.md`, and `issues-backlog.md`.

---

## 1. Verdict

The project's foundational engineering—declarative NixOS services, cross-family code review (`aq-land`), and deterministic pre-commit checks (`tier0`)—genuinely serves the owner's goals and catches real bugs before merge. However, the project is currently drowning in self-referential process machinery: ~181 plan directories, five overlapping definitions of "AQ-OS", and complex multi-table/cryptographic architectures designed for enterprise multi-tenant problems that a single-owner laptop does not have. Most of today's agent effort went into fighting harness-inflicted friction (false quota lockouts, worktree guards blocking commands containing the substring `"git"`, designs lost in `/tmp`, and unactivated "shadow" code) rather than increasing local inference capability. **The single most important change is an immediate freeze on new governance/architecture frameworks and a ruthless pruning of dormant plans and broken wrapper heuristics until every merged feature is live, activated, and measured.**

---

## 2. Goals Check: Tensions and Resolutions

The owner's hardware and subscription reality (one AMD Renoir laptop with 27 GB usable RAM, 12 GPU layers max, Qwen3.6-35B at ~5 tok/s and 4k–8k context, plus pooled Claude/Codex/Gemini OAuth subscriptions) is clear and well-bounded. Several standing goals, however, pull directly against each other:

1. **"Keep It Simple Stupid (KISS)" vs. Enterprise Governance Machinery**
   - **The Tension:** The owner wants discrete, simple, robust modules. Yet `CLAUDE.md` packs 23 Behavioral Rules and 8 dense canon blocks into 197 lines (`LOCAL-AGENT.md` is at 200/200 lines, `issues-backlog.md:9242`), and plans like `.agents/plans/factory-hook-composition-20261112/DESIGN.md` specify content-addressed prewarm caches, canonical preview hashes, and custom `reference-transaction` observers just to run git hooks.
   - **Resolution:** Apply KISS to the *harness itself*. If a governance mechanism requires its own schema, ledger, and multi-round review to exist, it violates KISS. Use stock tools (`git`, `flock`, `pytest`, `nix flake check`) and delete custom meta-layers.

2. **"Never Skip Local / Local Does More" vs. Measured Hardware & Model Limits**
   - **The Tension:** At ~5 tok/s and an 8k context ceiling, Qwen3.6-35B takes ~5 minutes to read 1.5k tokens and emit 500 tokens. Today it missed two real bugs in P2 that Codex caught (`PULSE.log:1043`), refused prompts >8k tokens, and truncated its own debate seat mid-sentence (`"thermal zone cpu"`, `issues-backlog.md:9344`) while reporting success.
   - **Resolution:** Stop forcing local Qwen into multi-file code review or open-ended architectural debate where it burns laptop thermals and produces silent false-positives or truncated text. Route local strictly to **narrow, single-function edits, AST/JSON transforms, commit-message/fact extraction, and deterministic test generation** where `tier0` or a schema validator proves correctness in milliseconds.

3. **"Human Out of the Loop by Default" vs. "Owner Decisions Asked in CLI"**
   - **The Tension:** Moving away from `aq-approve` to direct CLI numbered prompts removes a tool, but if background/headless agents or memory-collapse routines raise frequent blocking questions, the owner becomes a synchronous bottleneck—or prompts hang in non-interactive shells.
   - **Resolution:** Enforce a strict split: **interactive CLI sessions** ask the owner directly when hitting a reserved boundary; **headless/background runs** must never block on stdin—they either proceed with a safe logged default (`PROJECT-COLLECTIVE-PERSONA-PRD.md:90`) or abort the single slice cleanly and print the question for the next interactive turn.

4. **Rule 15/23 (Activated, No Dormant Code) vs. "Shadow-Complete" Foundation Tracks**
   - **The Tension:** `UNIFIED-PROGRAM-PLAN.md:48-58` celebrates Foundation B1 (`L1A`, `L2A`, `L2B-A`, `L2B-B`) and Foundation C (`:71`) as "SHADOW-COMPLETE" or "SHADOW-BUILD IN PROGRESS (default-OFF, unactivated)" with "no live callers yet." Shipping weeks of uncalled code with dashboard cards reading "shadow" violates the spirit of Rule 15 and Rule 23.
   - **Resolution:** Stop building "shadow" layers. Wire `L2B-B` (`normalize_endpoint_payload`) and the `F2.5` scheduler into live `switchboard`/`coordinator` traffic now, or archive them.

---

## 3. Stop / Start / Continue

### STOP
- **Stop writing new umbrella PRDs and overlapping program plans.** You have four historical versions of AQ-OS (`UNIFIED-PROGRAM-PLAN.md:32`), a `sota-factory-parity-20261112` bundle (4 PRDs, R01–R12), and now a 5-pillar `PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md` (`F1`–`F5`) authored on the same day. They re-describe the same receipts, gates, and distillation loops under different names.
- **Stop building uncalled "shadow" infrastructure and inspect-only stubs.** `L2B-B` has no live callers (`UNIFIED-PROGRAM-PLAN.md:48`); `F2` scheduler is built and dormant (`:40`); PR `#771` (hook composition slice 1) merged with "Nothing activated" (`PULSE.log:1084`); P2 instance labels merged in `#767`/`#769` but nothing exports `AQ_INSTANCE_MODEL` (`scripts/ai/lib/instance_label.py:35`), so `agent_slot()` falls back to legacy strings.
- **Stop using naive substring guards and brittle error classifiers in wrapper scripts.** The worktree guard trips when the word `"git"` appears anywhere in a command string, including Python log text (`issues-backlog.md:9324`). `aq-land` classifies any Codex transport blip (`"Reconnecting... 5/5"`) as a provider quota error (`issues-backlog.md:9278`). `delegate-to-codex` reported its own 250k local cap as "budget exhausted," tricking orchestrators into thinking OpenAI was down (`issues-backlog.md:9265`).
- **Stop creating worktrees or design drafts under `/tmp`.** Codex wrote the accepted `factory-hook-composition` design in `/tmp/aq-hook-composition-20261112`, which was wiped on the 11:28 reboot (`PULSE.log:1049`, `issues-backlog.md:9280`) and only survived by luck inside a local review log.

### START
- **Start enforcing `finish_reason == "length"` checks on local inference.** `delegate-to-local` currently marks truncated responses as completed (`issues-backlog.md:9344`). Any response hitting `max_tokens` without an EOS token must exit non-zero (`TRUNCATED`) so incomplete reviews or code edits are never accepted.
- **Start validating file existence in PRDs/designs before review.** In `PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md:91`, Slice F2 claimed to extend `scripts/ai/lib/outcome_receipt.py`, which did not exist (`claude-kiss.md:7`). A 10-line check in `tier0` should fail any plan citing non-existent repo paths not explicitly marked `[NEW]`.
- **Start fixing live daemon permission errors before designing new coordinator endpoints.** `ai-hybrid-coordinator` is actively failing in journal logs with `EACCES` on `/var/lib/ai-stack/model-profile.json` and `/var/log/nixos-ai-stack/query-gaps.tmp`, and `ai-mcp-integrity-check.service` is in a failed systemd state (`issues-backlog.md:9247, 9327`).
- **Start using a single active work queue.** Replace the 1,266-line narrative `AGENT-CATCHUP-QUEUE.md` (which still carries open entries from July/August, lines 69–99) with a bounded JSON/Markdown table of <=10 live items; archive everything older than 14 days.

### CONTINUE
- **Continue mandatory cross-family independent review via `aq-land`.** Today alone, cross-lane review caught 4 real defects in P2 (Codex catching `PERSONA`-env dependent verification, blank label bypass, and test env leak: `PULSE.log:1043-1044`) and 4 real blockers in P3 (Gemini catching hidden last-write-wins in `consensus_manager.py:77-84` and AppArmor `/home/** wx` blocks: `AGENT-CATCHUP-QUEUE.md:1200-1203`). This is the highest-ROI mechanism in the repo.
- **Continue the KISS red-team seat (`claude-kiss.md`) on every plan.** The 33-line `claude-kiss.md` review of `frugal-sota-leadership` cut 60% of the speculative scope (deferring F3, F4, dashboard cards, and gameable `vw_per_kt` ratios) before implementation started (`FREEZE.md:12-20`).
- **Continue keeping heavy CI in-house (`issues-backlog.md:39`).** Running `tier0-validation-gate.sh` locally on CPU/Nix store and keeping GitHub Actions to a <5s receipt/courtesy check saved hosted runner starvation (`issues-backlog.md:9221`).

---

## 4. Verdict on Active Plans

### 1. Frugal SOTA Leadership (`frugal-sota-leadership-20261113`) — **SHRINK TO FROZEN MVP (S1–S4), KILL THE REST**
The original 5-pillar PRD (`PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md`) is heavy on buzzwords ("AQ-OS", "System 1 / System 2 Co-Evolution", "VW/kT", "Reciprocity Bridge") and duplicates `UNIFIED-PROGRAM-PLAN.md`. However, the stripped-down **Frozen MVP (`FREEZE.md`)**—`S1` `aq-context-packet` (<=2,500 tokens, CPU-only AST/callers), `S2` running `tier0` on touched files in `aq-land` *before* spending cloud review tokens, `S3` power/thermal/load gating in `delegate-to-local`, and `S4` an append-only JSONL outcome receipt + `aq-scoreboard` CLI—is practical and directly useful. **Smallest version worth building:** Finish landing S1–S4, wire `aq-context-packet` into `delegate-to-local` so local Qwen actually receives <=2,500-token packets in production, and **kill** F3 (System 1 router/distillation), F4 (reciprocity packets), and F5 (dashboard scoreboard card) until `aq-scoreboard` has 100+ real slice receipts.

### 2. Collective Persona "Simurg" P3 (`persona-p3-collapse-20261113/DESIGN.md` rev 3, NEW: not on main) — **SHRINK RADICALLY**
P1 (`#765`) and P2 (`#767`, `#769`) are merged, though P2 is dormant because `AQ_INSTANCE_MODEL` is never set. P3 rev 3 (`DESIGN.md`) is much cleaner than rev 1/2, but it still adds a new HTTP route (`POST /api/memory/delta`), a new Postgres schema (`collapse_facts` with 5 state transitions), Qdrant duplicate-check bypasses (`memory_manager.py:354`), and offline spooling in `.agent/memory/pending-deltas/`—all while `ai-hybrid-coordinator` already has live `EACCES` and silent exception-swallowing bugs (`issues-backlog.md:9326-9327`). **Smallest version worth building:** First, export `AQ_INSTANCE_MODEL` and `AQ_INSTANCE_SESSION` in the delegate wrappers so P2 actually works. For P3, skip Postgres and Qdrant entirely: write structured facts to a git-tracked JSONL or Markdown file (`.agent/memory/facts/<scope>.md`) with `(subject, claim, instance, evidence)`. When two branches or lanes write different claims for the same `subject`, a simple 50-line Python script in `tier0` / `aq-session-start` detects the key collision and prompts the owner in the CLI (`1) keep A, 2) keep B, 3) keep both`). Zero daemons, zero DB migrations, 100% git-auditable.

### 3. Factory Hook Composition (`factory-hook-composition-20261112`) — **KILL / ARCHIVE**
Read `.agents/delegation/outputs/factory-hook-composition-20261112-DESIGN.recovered.md`: 351 lines of cryptographic ceremony (`prewarm-inputs/v1`, `cache-manifest/v1`, symlink/hardlink/FIFO scanners, `reference-transaction` hooks, and explicitly refusing linked git worktrees in §1 line 25) just to compose `.githooks/pre-commit` with `.pre-commit-config.yaml`. Worse, **every agent in this repo is required to work in a linked git worktree** (`CLAUDE.md:160`), which this design explicitly refuses to support! And Rule 8c (`factory-gate-preflight`) already blocked Persona P2 until the orchestrator had to rule that Rule 8c doesn't apply to harness work (`AGENT-CATCHUP-QUEUE.md:1164-1183`). **Smallest version worth building:** None. Delete Rule 8c from `CLAUDE.md`, keep `#771`'s simple refusal or call needed linters directly from `.githooks/pre-commit` (which is already active and works in worktrees), and archive `factory-hook-composition-20261112`.

### 4. Unified Program Plan & SOTA Factory Parity (`UNIFIED-PROGRAM-PLAN.md`, `sota-factory-parity-20261112`) — **PAUSE & CONSOLIDATE**
`UNIFIED-PROGRAM-PLAN.md` tracks Foundations A, B1, B2, B3, C, Products D–G, and Track V across four reconciled AQ-OS PRDs; `sota-factory-parity-20261112` adds P1–P4 (R01–R12) on top. In reality, B1 and C are "shadow-complete" (dormant), F2.5 scheduler wiring is dormant, and ~181 plan directories sit in `.agents/plans/`. **Smallest version worth building:** Freeze all new Foundation/Track plans. Replace `UNIFIED-PROGRAM-PLAN.md` with a 50-line `ROADMAP.md` that lists only (a) what is live today, (b) the 3 active slices allowed at one time, and (c) the dormant built code (`L2B-B`, `F2.5`, `C2-SCI`) that must be either wired into live traffic or archived within 30 days.

---

## 5. The Harness Itself: Cost vs. Return

**Is the governance load proportionate for a one-owner laptop project?** **No.** It is roughly 5x too heavy. You have built safety controls against adversarial insiders (cryptographic capability leases, offline Ed25519 epoch signing, hash-bound package freezes, 6-file canon compilers) when the actual failure modes hurting you are mundane software bugs: shell scripts matching `"git"` as a substring, `/tmp` directories wiped on reboot, `EACCES` on `/var/log`, and LLMs truncating JSON.

### Costs More Than It Returns (Cut or Simplify)
1. **The 200-line / 24KB 6-file Canon Sync (`Rule 16` + `check-instruction-budget`):** Every rule tweak requires recompiling 6 agent files and fighting the 200-line ceiling (`LOCAL-AGENT.md` is at 200/200, `issues-backlog.md:9242`). **Fix:** Put shared rules in `AGENTS.md` only; make `CLAUDE.md`, `GEMINI.md`, `CODEX.md`, and `LOCAL-AGENT.md` 40-line lane-specific overlays that reference `AGENTS.md`.
2. **Rule 8c (`factory-gate-preflight`) & `.plan-classification.json` gates:** Pure bureaucratic friction that stalls worktrees (`AGENT-CATCHUP-QUEUE.md:1166`, `PULSE.log:1074`) without catching code bugs.
3. **Unstructured dual/triple state logging (`PULSE.log` + `RESUME.json` + `HANDOFF.md` + `AGENT-CATCHUP-QUEUE.md`):** Agents spend 3–5 tool calls per turn updating four overlapping state files (`PULSE.log:1054-1060`). Since `aq-event` already projects `PULSE` and `RESUME` (`UNIFIED-PROGRAM-PLAN.md:49`), stop manual multi-file checkpointing; emit one event via `aq-event` and kill `HANDOFF.md`.

### Missing or Under-Engineered (Build / Harden)
1. **Worktree-safe shell & path guards:** Narrow the worktree guard to actual git-mutation subcommands (`git commit|push|checkout|reset` in the wrong dir) instead of matching `"git"` anywhere in argv (`issues-backlog.md:9324`), and hard-block `/tmp/*` as a worktree or plan path in `delegate-to-*`.
2. **Live Activation Audit Gate:** A check that fails if a merged feature's env var (like `AQ_INSTANCE_MODEL`) or call site has zero live invocations after 48 hours.
3. **Local Output Completeness Check:** Rejecting `finish_reason == "length"` or malformed output in `delegate-to-local` before writing a receipt.

---

## 6. Assessment of the Orchestrator's 7 Opinions

1. **(1) Make delivery-pipeline friction the next wave instead of new pillars:** **AGREE** — fixing the worktree `"git"` substring bug, `/tmp` worktrees, `aq-land` path/quota bugs, and daemon `EACCES` errors will yield immediate daily velocity.
2. **(2) Cap active plans at 2–3 and activate before starting new PRDs:** **MODIFY** — cap active plans at **2** (one reliability/friction track, one feature track) and archive the ~175 dormant directories under `.agents/plans/` into `.agent/archive/`.
3. **(3) Re-scope persona P3 to git-tracked fact files where a merge conflict is the conflict and the agent asks the owner, instead of a Postgres/Qdrant ledger:** **MODIFY** — strongly agree with dropping Postgres/Qdrant for P3, but don't rely on raw git line-merge conflicts (adjacent appends conflict on unrelated facts); use a keyed JSONL/YAML file `.agent/memory/facts.jsonl` where a 40-line script flags duplicate `(scope, subject)` keys with differing claims and prompts the owner in CLI.
4. **(4) Defer System 1 distillation until the S4 scoreboard has weeks of real counts, and use local only for narrow checkable tasks:** **AGREE** — training or routing on synthetic/empty corpora is theatre; collect 100+ real verified slices first and restrict local Qwen to<2.5k-token checkable tasks.
5. **(5) Add a plan reality check (every cited path exists or is marked NEW; no marketing language) and commit plans immediately:** **AGREE** — this would have caught the nonexistent `outcome_receipt.py` in `PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD.md` and prevented the `/tmp` reboot wipe of `factory-hook-composition`.
6. **(6) Make P2 labels live:** **AGREE** — it is a 10-line fix to export `AQ_INSTANCE_MODEL` and `AQ_INSTANCE_SESSION` in `delegate-to-{claude,codex,gemini,local}` and the interactive shell init.
7. **(7) Walk the 33 orphaned `aq-approve` inbox items once in the CLI:** **MODIFY** — do not walk 33 stale items one by one in the CLI; have an agent batch-triage them first (auto-closing stale health alerts already resolved in `issues-backlog.md` and grouping the rest into <=5 yes/no category decisions for the owner).

---

## 7. Top 10 Highest-Leverage Actions for the Next Two Weeks

| Rank | Action | Expected Effect | Cost | How to Measure |
|---|---|---|---|---|
| **1** | **Fix the 5 acute pipeline paper-cuts:** (a) narrow worktree `"git"` substring guard (`issues-backlog.md:9324`), (b) refuse `/tmp` worktrees (`:9280`), (c) `os.path.abspath` in `aq-land` (`:9245`), (d) separate transport retry from 429 quota in `aq-land` (`:9278`), (e) refresh `sudo -v` before step 8b in `aq-deploy-current` (`:9263`). | Eliminates ~80% of false agent stalls, PR churn, and lost worktrees observed on 2026-11-13. | ~4 hours (1 slice) | Zero recurrence of these 5 error classes over the next 20 landed PRs in `PULSE.log`. |
| **2** | **Wire `AQ_INSTANCE_MODEL` & `AQ_INSTANCE_SESSION` into all delegate wrappers and session start.** | Turns Persona P2 (`#767`, `#769`) from dormant code into live provenance across all 4 lanes. | ~1 hour | 100% of new `PULSE.log` lines and review receipts show `Simurg@<lane>/<model>#<session>`. |
| **3** | **Finish and activate Frugal MVP `S1`–`S4` (`FREEZE.md`), then wire `aq-context-packet` into `delegate-to-local`.** | Cuts pre-review cloud token waste (`S2`), protects laptop thermals (`S3`), bounds local context to <=2,500 tokens (`S1`), and starts honest measurement (`S4`). | ~6 hours (in flight) | `aq-scoreboard` outputs real token/defect counts over 10 consecutive slices; `delegate-to-local` payloads never exceed 2,500 tokens. |
| **4** | **Harden `delegate-to-local` against silent truncation (`finish_reason == "length"`) and right-size `max_tokens`.** | Stops local Qwen from returning half-finished reviews/code marked as `PASS` (`issues-backlog.md:9344`). | ~2 hours | Test with a forced 50-token cap exits non-zero (`TRUNCATED`); zero mid-sentence local outputs in `.agents/delegation/outputs/`. |
| **5** | **Fix liveNixOS service failures (`ai-hybrid-coordinator` `EACCES` on `/var/lib/ai-stack/model-profile.json` & `/var/log/nixos-ai-stack/query-gaps.tmp`; `ai-mcp-integrity-check.service` failure).** | Restores clean `aq-qa 0` health checks (`0.1.2`) and stops silent telemetry/memory drops (`issues-backlog.md:9247, 9327`). | ~3 hours + 1 owner rebuild | `systemctl --failed` shows 0 units; `aq-qa 0` passes 100%; zero `EACCES` in `journalctl -u ai-hybrid-coordinator`. |
| **6** | **Implement P3 Memory Collapse as a git-tracked `.agent/memory/facts.jsonl` + CLI conflict prompt (drop Postgres/Qdrant ledger).** | Delivers cross-lane fact sharing and owner conflict resolution with 1/5th the code and zero daemon/AppArmor failure modes. | ~4 hours | E2E test: two conflicting `(scope, subject)` facts trigger the CLI 1/2/3 prompt at `aq-session-start` and resolve cleanly in git. |
| **7** | **Kill `factory-hook-composition-20261112` and remove Rule 8c (`factory-gate-preflight`) from agent files.** | Removes a 351-line design that doesn't even support linked worktrees and unblocks harness slices from false `INSTALLATION_ABSENT` stalls. | ~1 hour | `rg "factory-gate-preflight" CLAUDE.md AGENTS.md .agent/` returns 0 hits; hook-composition archived. |
| **8** | **Batch-drain the 33 orphaned `aq-approve` items into <=5 CLI category questions and retire the `aq-approve` queue.** | Completes the owner's 2026-11-13 "no `aq-approve`" directive without leaving 33 ghost items or forcing 33 manual prompts. | ~1 hour | `aq-approve` pending count = 0; retired from `tier0` and session-start scripts. |
| **9** | **Add a `tier0` Plan Reality Check (`check-plan-paths.py`) and archive ~175 inactive `.agents/plans/*` directories.** | Prevents agents from planning against imaginary files (`outcome_receipt.py`) and clears 4 months of planning clutter. | ~2 hours | `ls .agents/plans/` shows <=5 directories; staging a plan with an unmarked non-existent path fails `tier0`. |
| **10** | **Activate or archive the "Shadow-Complete" Foundation B1 (`L2B-B`) and `F2.5` scheduler code.** | Resolves Rule 23 (no dormant code) on the two largest uncalled subsystems in `UNIFIED-PROGRAM-PLAN.md:40, 48`. | ~6 hours | Either live `switchboard`/`coordinator` traffic routes through `normalize_endpoint_payload` and `F2` scheduler, or the modules are moved to `.agent/archive/`. |

---

## 8. What the Owner Did Not Ask About But Should Know

1. **Two orchestrators (`Simurg@claude/opus-5.5` and `Simurg@codex/root` / `Simurg@gemini`) were operating concurrently today with overlapping mental models.** Look at `PULSE.log:1070-1073`: at `17:44`, Gemini marked `attention-recovery-retirement-DESIGN.md` as `PLAN_READY`; two minutes later (`01:46 UTC` = `17:46 PST`), `Simurg@codex/root` logged a `coordination-blocker` disputing Gemini's `PLAN_READY` claim and pointing to its own `/tmp/coord-attention-recovery-design-20261113.md`. While Gemini reconciled it at `17:56` (`PULSE.log:1076`), running multiple top-level orchestrators simultaneously on the same repo creates race conditions on `RESUME.json`, `PENDING.json`, and design authority. **Rule:** Have **one** active orchestrator session at a time; all other lanes run strictly as dispatched sub-agents (implementers or reviewers) in isolated worktrees.
2. **Your `issues-backlog.md` (9,355 lines) and `AGENT-CATCHUP-QUEUE.md` (1,266 lines) are becoming write-only graveyards.** Automated RSI sweeps dump repeated health-monitor alerts (`rsi-f73f403...`, `rsi-400fae1...`, `rsi-66e6ba1...`) into `issues-backlog.md` every 15 minutes when a phase-0 check blips, then mark them `[DONE]` 5 minutes later (`issues-backlog.md:9328-9355`). This buries high-severity architectural bugs under hundreds of lines of automated log noise. Separate transient health-monitor state from the human/agent engineering backlog.
3. **Security & privacy on trajectory corpora (`trajectories.jsonl`):** Even if you defer F3 distillation, `S4` (`FREEZE.md:16`) begins logging outcome receipts. Do not store raw prompt packets or diffs in a repo-tracked or world-readable file; store them `0600` under `/var/lib/ai-stack/` and keep only aggregate token/defect counters in the repo (`claude-kiss.md:14`).
