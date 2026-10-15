# aq-decide DEC-S1: library, config, CLI (shadow) (2026-10-15)

## Objective
Implement DEC-S1 of `.agents/plans/aq-decide/DESIGN.md` (frozen v2.1): the decision contract (Jev-parity request `{state, questions}` -> typed answers with probabilities, confidence, `outcome: decided|abstain|error`, closed-enum `reason_code`), the 1500-char state cap, T0a deterministic rules, T0b exact cache (writes only by rule or owner), T0.5 hashed TF-IDF + linear model trained on seed data only and run in shadow only, and structured decision logging. Advisory + friction only (owner D1); no HTTP endpoint, no learned head, no egress coupling, no remote labelling.

Files: `scripts/ai/lib/aq_decide.py`, `scripts/ai/aq-decide` (CLI: decide|shadow|explain|bench), `config/aq-decide.json`, `config/aq-decide/seeds/{task_profile,retrieve_needed}.jsonl`, `tests/unit/test_aq_decide.py`.

## Workflow/Session IDs
Branch `feat/aq-decide-dec-s1`, worktree `.agents/delegation/worktrees/dec-s1`, base origin/main. Plan `.agents/plans/aq-decide/` (tracker item DEC-S1). Delegated slice from the orchestrator session (Claude Sonnet 5.5 implementer). Staged, not committed.

## Delegation Decision
Bounded single-slice implementation by the Sonnet implementer lane (Rule 17), seed formatting done inline (small). Independent review is the orchestrator's to route (Rule 18).

## Commands Executed
- `git fetch`; `git worktree add -b feat/aq-decide-dec-s1 ... origin/main`
- `python3 -m pytest tests/unit/test_aq_decide.py -q -s`
- `python3 scripts/ai/aq-decide bench --n 2000` (both seeded questions); `aq-decide shadow|explain`
- `python3 scripts/ai/aq-pm-tracker .agents/plans/aq-decide --check`

## Validation Evidence
- Unit tests: 35 passed. Cover: contract shape/probabilities (choice, noul), request validation, bad-request returns error not exception, unknown/type-mismatch/score-deferred, request cannot redefine question, enum/int/bool feature validation and unlisted-field drop, closed-enum reason_code (format + registry), abstain on no match and on low confidence, hard-rule > owner-cache > soft-rule > config-order precedence, kill switch (`AQ_DECIDE=0` -> abstain `DISABLED`, nothing logged), cache exactness and config-version invalidation, cache refuses any writer other than rule/owner and any tier T0.5, shadow output never feeds cache and never appears in the response, cap boundaries 400/1500/1501/4000 (cap, marker, `truncated`, log `TRUNCATED` flag), control-char stripping, egress payload schema (no free text; enum/int validation; free text never logged), security-class config can never list or emit an unsafe-direction option or take free text, log fields/redaction/0600 perms, log failure never raises, T0.5 refuses non-seed rows, T0.5 deterministic, T0.5 latency, CLI decide + kill switch.
- T0.5 in-process latency (pure stdlib, single decision, text capped at 1500 chars), `aq-decide bench --n 2000`: task_profile p50 0.265 / p95 0.483 / p99 0.726 / max 1.02 ms; retrieve_needed p50 0.225 / p95 0.403 / p99 0.448 ms. Test run (n=200, 200-1500 chars): p50 0.161 / p95 0.236 / p99 0.247 ms. Acceptance p99 <= 3 ms met. Ambient host load not controlled; treat as +/-50% (design 2.7). Model train at startup from 42 seed rows: about 0.3 s.
- Tracker: `PASS: aq-decide/tracker.json valid + projects`. Subject `feat(aq-decide): DEC-S1 library, config, CLI (shadow)` matches DEC-S1 `commit_match` `feat\(aq-decide\): .*(library|DEC-S1)`.
- Not validated: any live path (none exists in this slice); T0.5 quality (seeds are hand-written implementer examples, fit test is on its own seeds only and is not a quality claim; at 42 rows it is far below the 4.3 gates, so it is shadow-only by construction).

## Review Fixes (independent review, HIGH/MED/LOW)
- HIGH forged cache line (`owner-cache.jsonl` is agent-writable, key is publicly computable): fixed. Security-class questions never read or write T0b in S1; loaded entries must carry a `question`, answer in that question's options, tier owner/T0a, non-security question, else rejected and counted (`cache.rejected`); every tier's answer is asserted in options and not in `unsafe_options` for security-class (else error INTERNAL); cache file 0600, state dir 0700. HMAC signing not added: no existing key mechanism usable from this slice without the service-owned dir; integrity for non-security questions depends on DEC-S2.
- TRACKED LIMITATION: non-security questions (`task_profile`, `retrieve_needed`) still accept a forged in-options cache answer from the agent-writable state dir. Acceptable only while they are advisory/shadow with no live consumer. Before any advise/enforce use, DEC-S2 must move the cache to a Nix-declared service-owned dir or HMAC-sign entries. Also: pre-existing cache files keep their old mode (only newly created files are 0600). Rejected loaded entries are exposed as `cache_rejected` in `Decider.counters`, `aq-decide stats` and `aq-decide explain`.
- MED: `writer="owner"` is a string-level guard only. DEC-S2 requirement: owner writes only via the aq-approve / `_resolve_actor`-authenticated path, and the state dir moves to a Nix-declared service-owned dir.
- LOW: Unicode Cf (bidi, zero-width) stripped from text; redaction extended for AWS AKIA/ASIA keys, JWTs, URL credentials.

## Rollback Plan
`AQ_DECIDE=0` makes every answer abstain `DISABLED`. Nothing imports the module yet; revert the commit to remove it. Decision log and owner cache live under `AQ_DECIDE_STATE_DIR` (default `$XDG_STATE_HOME/aq-decide`), created on first use, 0700/0600.

## Residual Risk
- Rule 15 dimensions: library/CLI not yet on a live path, not enabled, no dashboard/alert; dated deferral to DEC-S3 (first integration, shadow beside `classify_task_type`) and DEC-S2 (Nix options, tmpfiles for the state dir, health check, counters export). Operator intervention today is the env kill switch only.
- State dir is a user-state default, not Nix-declared (Rule 13): DEC-S2 must declare it via tmpfiles for the service; the default is only for CLI/tests.
- Seeds are implementer-written synthetic text (design 4.4 allows seeds/synthetic); no harvested rows, nothing sent remote.
- Logged `text_redacted` (<=300 chars after regex redaction of keys/tokens/hex/emails/home paths) is stored for `log_text: true` questions only; regex redaction is best-effort, not a guarantee. Egress questions never log text.
- Counters are in-process (`Decider.counters`, log_failed only); Prometheus-style export is DEC-S2.
- Not implemented per scope: `max_tier`/`deadline_ms` request fields (all tiers are in-process and sub-ms), `score` type, HTTP endpoint, ECE/calibration.

## Hint Feedback
No aq-hints consulted (design doc was the full spec). Hint gap: no hint pointed at where unit tests for `scripts/ai/lib` live (`tests/unit/`).
