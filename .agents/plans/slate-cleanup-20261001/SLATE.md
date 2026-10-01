# Slate cleanup — 2026-10-01

Goal (owner): clean slate before resuming AQ-OS refactor — no ignored breaks, bugs, or non-functioning services/tools/plugins/MCP.

## Sources (measured, not remembered)
- Backlog: 269 open-ish entries. Evidence triage of 76 (critical/in-flight + security/token highs): `TRIAGE-EVIDENCE.md`. Shallow passes (`TRIAGE-A/B.md`) superseded.
- Live: aq-qa phase 0 = 186 pass / 2 fail (llama-cpp startup loop) / 10 skip; 0 failed systemd units.
- RSI ledger: `aq-rsi status` (steward working the queue).
- Code scanning: 7 open (fixes on PR #355, clear on rescan after merge).
- MCP: 9 connected; semgrep now via `.mcp.json` (approval pending); playwright quarantined by design.

## Waves
1. **S-effort LIVE, no owner** (dispatched 2026-10-01): aq-agent-loop task-id collision; delegate-to-local false launch ack; pre-commit `git diff --cached --check`; CI skill-bundle smoke assertion; Trivy SARIF upload per category; antigravity route preflight signal; QPPR zero-budget barrier test (1/39 red).
2. **M-effort LIVE**: codex/gemini background shell prompt reparse + lost errors (port claude fix a6502bdd); claude blocking-mode pid/terminal reconciliation; registry writers transactional (no truncate-before-lock); aq-approve pre-effect fence + actor auth; cancel TERM→wait→KILL→confirm; claude delegate daily cap/lock; m2a CAS mandatory revision + exclusive temp; token/lane telemetry; review-convergence typed receipts; gitleaks allowlist narrowing + packaging.
3. **L / owner**: host-side dispatch broker (sandbox parent death); dashboard secret surface (LoadCredential, drop groups, narrow AppArmor) — rebuild; history secret-scan triage + rotation decision (owner); microSD read-back test (owner).
4. **Unverified medium/low (~118)**: evidence triage pass, then fold into waves.
5. **Bookkeeping**: mark the 36 STALE-FIXED + 3 OBSOLETE keys DONE with their evidence.

Design-debt (12) stays with its plans (Foundation C/L2B/B2/HERDR/etc.) — not counted as defects.

## Owner decision 2026-10-01 — executable pins
MCP servers / tool-authority executables: exact reviewed pins, auto-bumped by the RSI steward after scan + test (owner sign-off only for majors). Libraries: floors. New steward slice: "executable pin watcher" (release check -> intake scan -> focused test -> pin bump commit, never unreviewed).
