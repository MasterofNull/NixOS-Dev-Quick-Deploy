# Codex — architect / PRD review
Evidence: draft read from main checkout because absent here; six unit definitions and rsi_lifecycle.py read from this worktree. Static review only; deployed behavior unverified.

1. Boundary and authority
- Approve the steward as the sole incident triage/repair scheduler, reusing existing dispatch and gates; do not create another autonomous executor.
- Separate permission to prepare an isolated patch from permission to integrate, activate, restart, or resolve; CLI approval must bind incident, exact subject, scope, action, expiry, and authority.
- Existing ai-prsi-orchestrator explicitly runs identify → approve-low-risk → execute; preserve only previously authorized deterministic policy decisions, never let the repair agent approve itself.
- A validated patch is repair_ready, not resolved. Resolution requires authorized integration/activation where necessary and a fresh reproduction proving recovery; change the draft's end-to-end acceptance accordingly.
- Owner interaction stays CLI-first; remote Codex proof precedes local enablement. Keep verifier, budget, independent acceptance, and trunk protection; add no API keys.

2. Consolidation decision
- Keep ai-stack-health-monitor (15-minute aq-qa producer) and disk-health-monitor (privileged SMART/NVMe producer); ingest their evidence without duplicating probes or inheriting disk privileges.
- Fold ai-auto-remediate's 15-minute repair trigger and ai-gap-auto-remediate's daily Ralph/aider trigger into steward scheduling; retain useful detectors, retire their independent autonomous repair entrypoints after parity proof.
- Fold ai-prsi-orchestrator's hourly decision cycle into the same scheduling authority; retain reusable deterministic policy/execution functions and distinct job cadences.
- Reuse ai-prsi-rsi-dispatch as bounded repair worker; replace its five-minute backstop with the steward sweep. Retarget its path trigger to enqueue/wake the same scheduler, never a competing dispatch route.
- Retire old triggers only in a deliberate cutover with old/new mutual exclusion, preserved queued work, and a documented operator rollback; do not disable producer coverage first.

3. Minimal independently shippable MVP slices
- S1: Freeze authority/state contracts and add aq-rsi report/status/pending over the existing ledger. Acceptance: measured report <2s, repeated reports dedupe, no model/network call on intake, existing commands remain compatible.
- S2: Add observation-only sweep adapters for failed units, code-scanning, and phase-0 results. Acceptance: two real sweeps create no duplicates; missing/stale sources show unknown, not healthy; CLI exposes age/count/skip reasons and >24h pending-with-zero-execution alert.
- S3: Add CLI approval binding, atomic ownership leases, and shared durable budget reservations around existing dispatch; disabled by default. Acceptance: concurrent triggers claim once, crash/restart recovers safely, expired approval and exhausted budgets block, sandbox denial remains visible.
- S4: Prove one owner-approved Codex repair end-to-end in an isolated worktree. Acceptance: real patch plus required regression/tier0 evidence and independent acceptance; authorized application and live recovery precede resolved; cancellation leaves no orphan worker.
- S5: Owner-activated timer cutover. Acceptance: effective units demonstrate one scheduler, both producers still run, queued work survives cutover/restart, and aq-qa exercises the integration path; CLI verifies terminal outcomes and stuck-loop alerting.

4. Failure modes and required controls
- Runaway repairs: per-incident retry ceiling/cooldown, one active repair initially, bounded child lifetime, durable daily cost/runtime limits reserved before launch, and a kill switch. Steward failures must record locally without recursively invoking repairs.
- Duplicate incidents: lifecycle identity hashes producer/path/authority/raw error, so timestamps and changing paths fragment incidents and different producers never coalesce. Define stable source keys and cross-source correlation; serialize intake and claims across worktrees.
- Ledger durability: lifecycle root is script-relative, potentially producing separate worktree ledgers; use a canonical resolver, never symlinks. Corrupt JSON, full disk, and the 1,000-incident cap must fail visibly; explicitly archive resolved evidence.
- Resolution consistency: resolve() updates JSON but leaves backlog OPEN; subsequent failure reopens the incident. Distinguish stale replay from new recurrence and project lifecycle state consistently before sweeping backlog entries.
- Noise: require persistence/freshness, classify skipped/inconclusive disk probes as unknown, and honor active human/agent ownership with expiring leases; warning volume alone must not authorize repair.
- Sandbox: prove Codex credential discovery without copying secrets, executable PATH, worktree/git metadata writes, and child-process cleanup under the actual unit. Writable .git is powerful; isolation needs enforced scope and no shared-checkout integration authority.

5. Cut from MVP
- Cut local tuning, autonomous merge/deploy/restarts, dashboard approval UI, broad historical free-text backlog ingestion, and health-spider/extra scanning adapters beyond the three acceptance sources.
- Reuse existing bridges, pending CLI, skip telemetry, and dispatch rather than rebuilding them; retain CLI observability. Document the owner-directed dashboard exception explicitly.
VERDICT: PLAN_READY_WITH_FOLLOWUPS — Freeze exact numeric budgets and approval/state semantics before execution; require live recovery, not patch production, for resolved.
