CONCERNS

Reviewer: Simurg@claude/sonnet (KISS, failure modes, security). Author lane = gemini.

**1. Slices (existence checked with rg/fd)**
- F1 SHRINK. `aq-context-packet` is MISSING (`aq-land` exists). Smallest: one Python script, `--paths file[:symbol]`, `ast` bodies/signatures plus graph callers, 2,500 cap, no AIDB, no exemplar. Prove by dispatching one real slice to local Qwen.
- F2 SHRINK. `outcome_receipt.py` and `OutcomeReceipt` exist nowhere in the repo; the PRD says "extend". `aq-keep-awake` and `delegate-to-local` exist. Smallest: power/thermal/load gate in `delegate-to-local` plus an append-only receipt line written by `aq-land`. Defer `vw_per_kt`, quota arbitrage (codex is out).
- F3 DEFER. Collector, router and calibration test are all MISSING; no receipt corpus exists to calibrate against. Revisit after about 30 real receipts.
- F4 DEFER. `ECOSYSTEM-RECIPROCITY.md` is MISSING and `aq-rsi` has no reciprocity subcommand. It carries outbound leakage risk and no prototype value.
- F5 SHRINK, last. Ship a CLI `aq-scoreboard` over the receipts; add the dashboard card only once the numbers are real.

**2. Failure modes and guards**
- Packet silently drops the symbol that matters: embed `degraded` plus the dropped list; refuse dispatch (nonzero exit) if the target symbol was degraded.
- Trajectory or reciprocity leakage: beyond the post-redaction scan in claude.md, store files 0600 outside the repo, and reject any absolute `/home` or `/run/secrets` path.
- Thermal/battery: an unreadable sensor means defer (fail closed); every CPU router call gets a wall-clock timeout.
- Gate gaming: `vw_per_kt` is gameable (inflate "verified work", shrink tokens). Report raw counts: tokens, tier0 first-pass, review defects.

**3. Contradictions**
- DESIGN.md line 17 and line 82 still cite `aq-approve` and a `human_gate` alert; this violates the CLI-direct directive. The PRD itself is clean.
- Codex remains in Tier 2 and F2 arbitrage; the prototype has none.
- No /tmp or reboot-wipe issue found; paths are persistent.
- "sub-20ms", "<200ms" and "30-day vw_per_kt" have no measurement plan or baseline.
- Each slice bundles 3-5 components, against "complexity only in aggregate".

**4. Frozen MVP**
- `aq-context-packet` v0. Test: 3 real files, under the cap, byte-identical across two runs, under 200ms.
- Degradation flag plus refusal. Test: a forced tiny cap gives `degraded` and a nonzero exit.
- `aq-land` runs tier0 on the touched scope before review. Test: a failing change never reaches the reviewer.
- `delegate-to-local` gate: AC or battery >= 50%, 5-min load with hysteresis, temp < 80C, unreadable sensor = defer. Test: simulated hot/unreadable sensors defer.
- Append-only receipt JSONL (real tokens) with a scan-or-quarantine step.
- `aq-scoreboard` CLI. Test: counts match a hand count over 5 real slices.
- Remove `aq-approve` from DESIGN.md.
- Deferred: F3, F4, dashboard card, arbitrage.
