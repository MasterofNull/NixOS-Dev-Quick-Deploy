# Agentic Software Factory — Test Run 3 (delta against run 2)

Third in-situ run after harness changes. Handoff for the NixOS-Dev-Quick-Deploy developers.

- **Date:** 2026-09-18/19
- **Run 2 harness HEAD:** `cec0012d`
- **Run 3 harness HEAD:** `a6502bdd` (4 commits later)
- **Target repo:** Mendocino-Coastal-Plants, factory installed from run 1, gate green at start
- **Repo state at start:** tree clean, gate `passed=6 warned=2 failed=0`

## Headline

**The redeploy completed.** R2-001 is fixed. The retrofit now recognises its own prior install and
takes an upgrade path:

```
"blocker": null        "safe_to_install": true        "upgrade": true
"installation": {"state": "INSTALLED"}
```

**But the upgrade broke the gate it was upgrading.** It overwrote a working, passing secret-scan
check with an unrendered `{{SECRET_SCAN_CMD}}` placeholder, taking the repo from
`passed=6 failed=0` to `passed=5 failed=1`. It backed up one file (`.git-config`) while overwriting
twenty-one. Recovery was possible only because the repo was under git.

So: the upgrade path exists now, and it is not yet safe to run on a configured repo.

## Fixed

| ID | Severity | Evidence |
| --- | --- | --- |
| R2-001 | critical | Retrofit is idempotent. `upgrade: true`, `blocker: null`, install reached `INSTALLED`. The redeploy that blocked run 2 now succeeds. |
| R2-003 | high | The new `gate-runner` writes `.factory/gate-run-evidence.json`. The preflight's `MISSING_EXECUTION_EVIDENCE` blocker clears once the gate passes. Note the write is gated on `fail_count == 0`, so a failing gate produces no evidence — worth documenting, since it reads as a missing file rather than a failing gate. |
| R2-005 | high | `get_hints` now returns `"recommended_agent": "codex"`. It no longer routes to the unauthenticated qwen lane. |
| R2-007 | medium | codex cost for the identical trivial prompt fell from 17,887 tokens to 5,860, below even run 1's 6,744. |
| FF-024 | medium | Background `codex exec` works. It returned the expected output with exit 0 instead of hanging on stdin. Commit `a6502bdd` resolved it. |
| R2-002 | partial | `factory-gate-status` now reports live commands: `{"build": "npm run build", "lint": "npm run lint", "test": "npm run test"}`. The stale "test/lint not declared" entries are gone. The residual half is below as R3-004. |

## New and regressed

### R3-001 — the upgrade destroys custom check configuration and breaks a green gate
- Severity: **high** (regression)
- Component: `aqd workflows retrofit` upgrade path
- Detail: The upgrade rewrote `scripts/governance/checks.d/hard-20-secret-scan.sh`, replacing a
  working scanner with a placeholder:
  ```diff
  -command_template='if git grep -nIE -e "AKIA[0-9A-Z]{16}" -e "BEGIN [A-Z ]*PRIVATE KEY" ... fi'
  +command_template='{{SECRET_SCAN_CMD}}'
  ```
  Gate before: `passed=6 warned=2 failed=0`. Gate after: `passed=5 warned=2 failed=1`.
  The renderer re-derived `test` and `lint` correctly from live detection, so it only destroys
  configuration it cannot itself reproduce — which is exactly the configuration a human or agent
  had to write by hand.
- Impact: upgrading the factory takes a compliant repo out of compliance, silently. The commit
  hook then blocks all work until someone notices and restores the file.
- Suggested fix: treat a rendered check whose template no longer matches as preserved, the way
  the role contracts and collaboration artifacts already are. If it must be replaced, say so in
  the preview output.

### R3-002 — the upgrade backs up one file while overwriting twenty-one
- Severity: **high**
- Component: `.factory/gate-backups/<digest>/`
- Detail: The backup directory for this upgrade contains exactly one file, `.git-config`. The
  preview listed 21 writes outside `.factory/gate-bundle/`, including every check script, the
  gate runner, `repo-structure.conf`, all three hooks and `pm-tracker`. None were backed up.
  Combined with R3-001, a destroyed check is unrecoverable from the factory's own backups.
- Suggested fix: back up every path in the write set before writing, not just git config.

### R3-003 — `repo-structure.conf` regains its template header and silently drops assertions
- Severity: medium
- Component: repo-structure renderer
- Detail: The rewritten file again opens with `# Render into .factory/repo-structure.conf in the
  target repository.`, the FF-001 symptom. More importantly it dropped all three `required=`
  lines (`src`, `scripts`, `data`) that the previous configuration asserted, and dropped
  `allowed_top` entries for `.git`, `.codex` and `docker-compose.yml`. The check still passes, so
  the weakening is invisible: the gate no longer verifies that `src`, `scripts` or `data` exist.
- Suggested fix: carry forward existing `required=` assertions on upgrade; a gate that gets
  weaker without telling anyone is worse than one that fails loudly.

### R3-004 — readiness probes for gitleaks instead of reading the configured check
- Severity: medium (residual half of R2-002)
- Component: `factory-gate-preflight`, `factory-gate-status`
- Detail: With the working scanner restored and the live gate reporting
  `PASS: hard-20-secret-scan` and `Summary: passed=6 warned=2 failed=0`, preflight still returns:
  ```
  ready: False   state: BLOCKED
  CHECKS_UNCONFIGURED - secret_scan: node: required tool unavailable: gitleaks
  ACTIVATION_BLOCKED - receipt_activation='ACTIVATION_BLOCKED'
  ```
  The detector asks "is gitleaks installed" rather than "is the secret_scan check configured and
  passing". A repo with a working non-gitleaks scanner can never report ready. The second blocker
  shows the receipt is still consulted for activation state even though commands are now live.
- Suggested fix: derive check readiness from the rendered check, not from tool probing, and
  recompute activation rather than reading it from the install receipt.
### R3-005 — the gate evidence artifact makes a clean tree impossible
- Severity: medium
- Component: `.factory/gate-run-evidence.json`, `gate-runner`
- Detail: The evidence file stamps `generated_at` on every gate run, and the pre-commit hook runs
  the gate, so the file is rewritten *during* every commit. The tree is dirty again the instant a
  commit completes, with a perpetual one-line timestamp diff. The `evidence_digest` itself is
  stable; only the timestamp churns.
- Impact: a repo tracking this file can never reach a clean tree, breaking "commit the slice, then
  verify clean" as a workflow step, and it will confuse CI.
- Workaround applied here: added to `.gitignore`; the file still exists on disk for the preflight.
- Suggested fix: have the installer gitignore it, or drop `generated_at` so identical runs produce
  identical content.

## Persists unchanged

| ID | Severity | Status this run |
| --- | --- | --- |
| FF-000 | critical | Third identical result. `agent_intake` on a new task returns `current_phase: "COMMIT"`; `lifecycle_status` returns `stub_status`. Explicit `complexity: "complex"` still downgraded to `"standard"`; `domain: "python"` still returns `domain_hint: "general"`. |
| FF-018 | critical | codex works. qwen still "OAuth free tier was discontinued on 2026-04-15". gemini still blocks on an interactive browser prompt. One of three lanes usable, three runs running. |
| FF-007 | high | **Degrading run over run.** Run 2: 49.2% success / 65 calls / 11.1% last hour. Run 3: **36.4% success / 77 calls / 49 backend failures / 9.1% last hour**, 18 recent failures, top error still `worktree_handback_failed`. |
| FF-006 | high | `collective_task` still `local command timed out after 30s`. |
| FF-003 | high | Live MCP schema still exposes no `confirm_retrofit`, after two commits (`1f2237b1`, `9cbd0a8c`) claiming to add it. The running server appears to serve a stale schema; a restart may be all that is needed. |
| FF-004 | high | MCP `stack` still typed free-text and still hard-fails on a descriptive value. |
| R2-004 | medium | `force: true` still emits `--force`, still rejected: `Unknown option: --force`. |
| FF-008 | medium | `harness_health(phase=0)` still `{"error": "timed out"}`, three runs running. |
| FF-010 | medium | `coordinator_status` and `get_hints` still truncate at 4000 chars with no override. |
| R2-006 | low | Preflight still reports `hybrid_coordinator: TRANSPORT_UNAVAILABLE` while that coordinator is serving every MCP call in the session. |

FF-016, FF-026 and FF-027 remain unexercised, still blocked behind FF-006.

## Trajectory

Three runs in, the pattern is clear. The **deployment mechanics** are converging: idempotency,
preservation, evidence, background dispatch and routing all got fixed on schedule. The
**orchestration spine** has not moved at all: the lifecycle has been a stub in all three runs, two
of three lanes have never authenticated, and delegation reliability has fallen from 49.2% to 36.4%.

The risk now is that deployment keeps improving while the thing being deployed stays unusable.

## Recommended order

1. **R3-001 + R3-002** — upgrade currently breaks working repos and cannot restore them. This is
   the direct consequence of fixing R2-001, and it lands on every repo that adopts the factory.
2. **FF-007** — 36.4% and falling. The delegation tier is the factory's cost model.
3. **FF-000** — three runs, unchanged. Everything above it is scaffolding around a stub.
4. **FF-018** — one working lane means rule 10, "an author cannot accept their own work", still
   cannot be satisfied honestly.
5. **FF-003 / R2-004** — likely one MCP server restart plus dropping `force` from the bridge.
6. **R3-003 + R3-004** — silent gate weakening, and a readiness check that cannot see a working
   non-gitleaks scanner.
