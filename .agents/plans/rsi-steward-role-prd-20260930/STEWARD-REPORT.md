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
