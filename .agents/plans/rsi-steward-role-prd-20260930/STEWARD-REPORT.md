# RSI Steward report (2026-09-30)

Branch `rsi/steward-20260930` (worktree `.agents/delegation/worktrees/rsi-steward-20260930`), base 43e9ccd3. Not pushed.

## Shipped
- S1 `dd0eebe8` aq-rsi CLI: report / status / pending / approve. status reports unknown (exit 2) for a missing queue; alerts on pending >24h with zero executed.
- S2 `798b0b21` aq-rsi sweep: failed units, code-scanning, aq-qa phase-0, payload-audit high; stale/missing = unknown; dedupe via rsi_lifecycle; no timers.
- S3 identity migration + intake severity fix + `rsi_lifecycle.annotate`: 21 groups recorded, 4 old incidents resolved, GitPython kept open (awaiting CI image rescan). Delegate-degradation incidents recorded (local 0.47/24h, coordinator /stats/delegate 18% all "unknown").
- S4 floor policy: 87 `==` pins -> `>=` (brief said 88; 87 found), 5 commented upper bounds, guard test.
- S5 this report (committed together with S4 because the cross-surface docs gate requires a docs file alongside runtime/ai-stack changes).
- Tooling fix (own commit): aq-integrity-scan absolute-path `.agents` exclusion made every commit staging ai-stack/ from a delegation worktree fail the logical-orphan guard (400 false orphans); now repo-relative, regression test added.

## Decisions
- Ledger env overrides (`RSI_RUNTIME_DIR`, `RSI_BACKLOG_FILE`, `RSI_WORKAROUNDS_FILE`) added to rsi_lifecycle so tests/CLIs use an isolated ledger. NOTE: codex's queued RSI state-dir slice (`.agents/plans/rsi-state-dir-partial-20260930/partial.patch`) also edits rsi_lifecycle.py; expect a small merge conflict, keep both intents.
- Trivy `note` severity normalized in the intake (it aborted the whole intake after partial writes).
- Lock-vs-requirements drift is a WARN in the floor test, not a failure (Rule 19 gate corollary).
- No coordinator /stats/delegate adapter: schema not verified and service unreachable from the worktree; the degradation is recorded as incidents instead. Adapter is a follow-up once the endpoint schema is read.

## Deferred / known gaps
- `rsi_lifecycle.resolve()` leaves the matching `[OPEN]` backlog line; 4 migrated incidents still show OPEN there.
- requirements.lock files predate raised floors (aidb: pydantic-settings, transformers, python-dotenv; nixos-docs: aiohttp, requests, lxml, gitpython). Refresh needs networked pip-compile.
- transformers>=5.10.0 / other alert-fixed floors not applied (major bump; separate repair slice, owner decision on risk).
- Sweep aq-qa source: in a worktree `.agent/qa` is absent; set `AQ_QA_PROGRESS_JSONL` to the shared checkout's file. The live file is from 2026-07-08 (reported unknown).
- Code-scanning export `~/.local/share/nixos-ai-stack/security/github-code-scanning-alerts.json` is from 2026-03-24 (reported unknown); refresh with `scripts/security/refresh-hosted-code-scanning.sh` or use intake `--fetch`.
- S3/S4/S5 of the PRD codex plan (leases + budgets, e2e codex repair, timer cutover) not started; S5 timers are owner-activated.
- tier0 QA 0.10.54 (C6c owner epoch-bump) failed once under load and passes standalone and on rerun (flaky).

## Owner sign-off commands to propose (not run)
No high-risk rows were pending in the queue visible from this worktree (queue file is under /var/lib and was not read). When rows exist, the exact form is:
`scripts/automation/prsi-orchestrator.py verify --id <row-id> --by owner --note "<reason>"` (`aq-rsi approve <row-or-incident-id>` prints it).

## Reviews queued
- Codex (after quota reset): confirmatory review of S1-S4 diff `43e9ccd3..HEAD` on rsi/steward-20260930, focus: status semantics (unknown vs healthy), sweep adapters, annotate redaction, floor bounds. Queued in AGENT-CATCHUP-QUEUE.md.
- Antigravity: same, advisory, on return.
- Local Qwen: not dispatched (slow on APU, orchestrator can request).

## Follow-up round (2026-10-01, after PR #355)
- `26dafc36` `aq-rsi reconcile`: resolves code-scanning incidents only on positive closed-alert evidence; `resolve()` now flips the `[OPEN]` backlog line to `[DONE <date>]` (the deferred gap above is closed). Live run: 18 incidents resolved from 2533 alerts; the 4 still open (setuptools, wheel, jaraco.context, transformers) match the alerts still open upstream. Fetch failure = unknown, exit 2.
- Approval binding + leases + budgets (commit after 26dafc36), default OFF behind policy `rsi.approval_binding_enabled` (`config/runtime-prsi-policy.json`: `daily_run_cap` 3, `approval_authorities` ["owner"]). `aq-rsi approve <id> --bind --scope --ttl --by` stores an approval bound to incident id + sha256 of identity + scope + expiry in `rsi-approvals.json`; dispatch skips rows with missing/expired/mismatched/insufficient-scope/unauthorized approvals; `rsi-leases.json` gives an atomic per-row lease (expiry or dead owner pid reclaims it after a crash); `rsi_runs_today` is reserved in the shared PRSI runtime state under its lock (cap 0 blocks; corrupt state fails closed). Tests: `test-rsi-gate.py` (8: concurrent claim once, expiry, crash recovery, concurrent budget, subject mismatch, scope, dispatch filter) and `test-aq-rsi.py` (--bind).
- Owner actions: (1) to enable binding, set `rsi.approval_binding_enabled: true` in the policy and run `aq-rsi approve <row> --bind --by owner` per row; (2) `--by` is a recorded identity, not authentication: it relies on the owner running the CLI, the agent must never run `--bind`. (3) Binding does not replace high-risk verifier sign-off; the command is still printed. (4) Merge note: gate state files `rsi-approvals.json`/`rsi-leases.json` live next to the incident ledger and are runtime state; add them to .gitignore if the owner wants them untracked (not done).
- Not touched: nix/, systemd units, Dockerfiles, `ai-stack/mcp-servers/*/requirements*`.
