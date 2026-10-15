# Frontier intake report (2026-10-14)

Sources: https://github.com/thebpandey/lanes (cloned depth 1 at 0f82a46) ; https://youtu.be/J9NQTYUP6k0 (Simon Scrapes, "How the Top 1% Use Claude Code Differently", 2026-10-10) ; https://youtu.be/VxGIopUQVKo (Sharbel A., "Anthropic's Engineers Stopped Building AI Agents...", 2026-10-11). Transcripts: yt-dlp auto-subs obtained for both (in $S/vid). Claims in the videos are the creators' secondhand paraphrases of Anthropic/Boris Cherny statements; not independently verified.

## A. lanes
- Facts (gh api): MIT, 17 stars, created 2026-09-27, last push 2026-10-02, ONE commit visible in shallow clone, ~900 lines of bash/python/markdown, one author. Immature, fast-moving.
- Architecture: Claude Code skill (SKILL.md + lane-agents). Orchestrator plans, writes a brief per task (inputs, owned.txt file-ownership list, checks.sh, token caps, stop condition), each worker runs in its own git worktree; every completed lane goes to an independent reviewer (never the orchestrator) that runs lane/scope-check.sh and writes review.md with `REVISION: <sha>` + `VERDICT: CLEAN|FIX`. lane/integrate.sh is the sole merge path: refuses unless scope check passes and (diff is TRIVIAL prose <=40 lines, or review.md says CLEAN for the branch's exact head sha); `merge --no-ff`, conflicts abort with exit 3.
- Token efficiency mechanism (policy, not engine): per-task input/output caps (2k/500, 12k/4k, 24k/8k), 10-12 line worker summaries, tool results capped 1-2k tokens, event-driven completion instead of status polling, work routed to cheap external models (DeepSeek, GLM via Anthropic-compatible endpoints; Codex review). No compression/caching engine. Usage ledger is manual convention.
- Security posture: install.sh writes to ~/.local/bin, ~/.claude/agents, ~/.claude/{deepseek,glm}.json, optional systemd user timer; bin/claude-via exports ANTHROPIC_BASE_URL to api.deepseek.com and runs `claude --permission-mode bypassPermissions` against an external provider with an API token from env (and falls back to `bash -ic` to read it). model-relay refuses main checkout and worktrees containing .env, relay-guard is a PreToolUse regex allowlist hook (tests cover newline-injection cases). Net: sends repo task content to third-party APIs using API keys. Reads no secrets itself, but conflicts with our NO-API-KEYS / OAuth-only rule. I did NOT run install.sh.
- Validation: `bash tests/run.sh` run with HOME and TMPDIR redirected into $S/sandbox. First run: 10 failures, all caused by my HOME redirect (integrate.sh defaults to $HOME/.claude/skills/lanes). After symlinking that path into the sandbox: **0 failures** (about 50 checks: relay-guard injection, scope-check, secret-scan, integrate verdict/revision binding, TRIVIAL classification, conflict abort). Token-saving claims: **unvalidated** (no benchmark exists, external-provider paths need keys we do not use).

## B. Videos (theories, concretely)
J9NQTYUP6k0 (10 strategies, per creator):
1. Plan mode is redundant on new models: write brief = task + guardrails + definition of done; review after via a one-page visual/diagram of what it did and assumed.
2. Do not tune effort / "think hard" words; use recommended effort (medium).
3. Checks over plans: give a deterministic pass/fail check script from the definition of done; do not say "double check".
4. `/goal` loops until the check passes; goal = one end state + how to prove it + what must not change + turn limit; the judge (small model) sees only chat output, so vague goals end prematurely.
5. CLAUDE.md as an index (<200 lines): only un-guessable commands, deviations, repeated gotchas, boundaries; reference other files by backticked path with "when to open" (not @import, which loads always); link every file directly from CLAUDE.md (nested files only get first-100-line preview); >100-line files get a contents list; `/doctor` prompt audit.
6. Write a skill only for what Claude got wrong without one (run task with no skill first, record corrections).
7. Skills often do not help: a 450-run test of 9 popular skill packs found 7/9 no better than a same-length dummy file; use `claude plugin eval` (with vs without) and `/skill-doctor` to prune.
8. Must-hold rules become hooks (deterministic, zero tokens), not CAPS in CLAUDE.md.
9. Let Claude size its own agent team; operator sets caps and guardrails; push big research/MCP steps into sub-agents to keep main context clean.
10. Projects/routines: event/timer-triggered runs with isolated context, human only approves output.
VxGIopUQVKo: one agent plus a growing skill library beats many agents (model=CPU, agent=OS, skills=apps); SKILL.md name+description with progressive disclosure; build by interview or screen recording; find skills in marketplaces; audit third-party skills for malicious code before install.

## C. Parity map
| Technique | Status | Evidence | Rec |
|---|---|---|---|
| Worktree per task | HAVE | scripts/ai/aq-worktree, aq-worktree-reap, aq-worktree-write-guard, .agents/plans/coordination-safety-worktree-isolation, Agent isolation:worktree, role-matrix.md L121-122 | SKIP |
| Per-lane owned-path scope gate (owned.txt + scope-check) | PARTIAL (write-guard exists; per-slice owned list + diff-vs-ownership check at merge not confirmed) | aq-worktree-write-guard | PARITY: small check in integrate path (~25 lines bash), via capability-intake-free reimplementation |
| Revision-bound review verdict gating merge | HAVE | trunk protection: Review-Disposition + Reviewed-subject-sha256 + non-author Reviewed-by (MEMORY.md) | SKIP |
| Trivial-prose bypass of review, script-decided | MISSING | none found | PARITY (optional, low value; gate is already system-enforced) |
| Independent reviewer, never orchestrator | HAVE | Rules 17/18, role-matrix, reviewer-gate skill | SKIP |
| PreToolUse regex allowlist hook for relay subagents | PARTIAL | hooks exist; allowlist-per-subagent not verified | PARITY: borrow relay-guard test cases (newline/redirect injection) as regression tests |
| Per-task token caps in brief (in/out), 10-12 line summaries | PARTIAL | Rule 22, memory-cache-sop.md budget 50k; no per-slice in/out caps in brief template | PARITY: add caps field to slice brief |
| Token compression engine | HAVE (stronger) | lean-ctx, rtk, aq-session-compact | SKIP |
| Cheap external model workers (DeepSeek/GLM) | MISSING by policy | needs API keys; violates no-API-keys | SKIP |
| Event-driven completion vs polling | HAVE | Rule: no polling loops in memory-cache-sop | SKIP |
| Secret scan before push | PARTIAL | pre-archive-scan.sh, tier0 | PARITY check that tier0 scans diff base..head |
| Briefs = task + guardrails + done | HAVE | slice-authoring skill, DoD | SKIP |
| Checks over plans, deterministic check script | PARTIAL | tier0 gate; slice briefs not required to carry a runnable checks.sh | PARITY: require acceptance check command in slice template |
| /goal with end-state, proof, turn cap | PARTIAL | aq-loop, Rule 6 retry budget | PARITY: confirm goal/turn-limit usage in aq-loop docs |
| CLAUDE.md as index; path refs not @import | PARTIAL | CLAUDE.md is long, mostly inline tables; ~/.claude/CLAUDE.md uses @imports | PARITY: trim via /doctor prompt audit; owner-visible, parity-rule 16 applies to all agent files |
| Skill only for observed failures; eval with/without | MISSING | no with/without skill eval seen; many skills listed | PARITY: run `claude plugin eval` / /skill-doctor on skill set; prune |
| Hooks for must-hold rules | HAVE | rtk hook, write-guard, tier0 | SKIP |
| Capability-intake for third-party skills | HAVE | .agent/skills/capability-intake, scripts/ai/aq-capability-intake | use for any adoption |
| Frontier intake registry | HAVE | scripts/ai/aq-frontier, .agents/plans/frontier-evidence-intake/BACKLOG.jsonl | register below |

Adoption verdict for lanes itself: SKIP as dependency (single-author 5-day-old, external-API relays, writes to $HOME, not Nix-declarative). Reimplement only the three small patterns marked PARITY (scope check, caps-in-brief, relay-guard test cases). Any install would require capability-intake audit first.

## D. aq-frontier
`aq-frontier add` exists. Not run. Fields (all required): --technique --source --claim --verdict --mapping --slice --acceptance [--id]. Commands I would run (verdict vocabulary should be checked against `aq-frontier verdict -h`):
```
scripts/ai/aq-frontier add --id lanes-owned-scope-gate --technique "per-lane owned-path scope check at merge" --source https://github.com/thebpandey/lanes --claim "integrate.sh refuses merge unless changed files subset of owned.txt and review.md revision == branch head; tests/run.sh 0 failures validated 2026-10-14" --verdict adopt-pattern --mapping multi-agent-isolation --slice "scope-check in aq-worktree integrate path" --acceptance "out-of-scope diff blocks merge; test covers in-scope, out-of-scope, uncommitted"
scripts/ai/aq-frontier add --id lanes-token-caps-in-brief --technique "per-task input/output token caps + stop condition in worker brief" --source https://github.com/thebpandey/lanes --claim "caps 2k/500, 12k/4k, 24k/8k; savings unvalidated" --verdict adopt-pattern --mapping token-efficiency --slice "add caps field to slice brief template" --acceptance "slice-authoring template carries caps; aq usage ledger records actual vs cap"
scripts/ai/aq-frontier add --id yt-checks-over-plans-goal --technique "deterministic check script + /goal with end state, proof, turn cap" --source https://youtu.be/J9NQTYUP6k0 --claim "verification 2-3x quality (Boris Cherny via creator, unverified)" --verdict adopt-pattern --mapping autonomy-verification --slice "require checks command in slice brief; goal template" --acceptance "slice template rejects missing check command"
scripts/ai/aq-frontier add --id yt-skill-eval-prune --technique "evaluate skills with vs without; skills only for observed failures" --source https://youtu.be/J9NQTYUP6k0 --claim "7/9 popular skill packs no better than dummy file over 450 runs (secondhand, unverified)" --verdict adopt-pattern --mapping skill-hygiene --slice "run claude plugin eval and /skill-doctor over .agent/skills" --acceptance "report of per-skill delta; zero-delta skills archived (Rule 12)"
scripts/ai/aq-frontier add --id yt-claudemd-index --technique "CLAUDE.md as index, path refs not @import, <200 lines" --source https://youtu.be/J9NQTYUP6k0 --claim "Anthropic docs: <200 lines; nested files preview first 100 lines" --verdict adopt-pattern --mapping context-efficiency --slice "prompt audit of agent instruction files, all agents (Rule 16)" --acceptance "CLAUDE.md under 200 lines, tier0 parity check green"
```
