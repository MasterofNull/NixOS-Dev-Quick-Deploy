# QPPR A2 REVISED candidate — binding acceptance verdict

**Reviewer identity:** `claude-subagent-qppr-a2-revised-acceptance-reviewer`
**Model:** Claude Opus 4.8 (claude-opus-4-8), fresh session — did not implement A2, did not
perform the first A2 acceptance (`claude-subagent-qppr-a2-acceptance-reviewer`, REQUEST_REVISION),
not the orchestrator, not an A2 rebind reviewer.
**Date:** 2026-07-20
**Authority:** owner `[acceptance-lane-directive]` PULSE.log line 331 (2026-07-20) — binding acceptance
of the staged QPPR A2 five-file slice redirected from codex-wait to fresh Claude flagship. CONFIRMED.
**Criteria SSOT:** `A2-REVISED-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md` (seven criteria, executed exactly).

## Recomputed hashes (SHA-256, working tree)

| Op | Path | Expected | Recomputed | Match |
|---|---|---|---|---|
| MODIFY | `assets/dashboard.js` | `ab241847…9e283b7` | `ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7` | ✅ |
| MODIFY | `scripts/testing/test-dashboard-qa-provider-probe.py` | `ce89a3cc…0ec8bde6` | `ce89a3cc5878e5c3cede353f35f7a5bdb1485bc6d3a936560a45d07f0ec8bde6` | ✅ |
| FROZEN | `dashboard/backend/api/services/qa_runner.py` | `8e49fa82…6326cbb7` | `8e49fa8296ed882a71a94b185f814085a44d16879dab804521ad026e6326cbb7` | ✅ |
| FROZEN | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf…2db8aa46` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` | ✅ |
| FROZEN | `dashboard.html` | `af9d8c81…8f84beae` | `af9d8c81e30f63321f01efd189416a6d4786489932485f889d82484e8f84beae` | ✅ |

All five match. The three FROZEN hashes are byte-identical to those recorded in the first acceptance
(`A2-CANDIDATE-ACCEPTANCE.md`) — unchanged by this revision.

## Per-criterion evidence

**1 — Hashes / freeze integrity: PASS.** All five recompute exactly. FROZEN three verified byte-identical
to first-accepted values. `git diff --cached --name-only` shows the A2 five plus the separate
delegate-codex quota slice (`.gitignore`, `scripts/ai/delegate-to-codex`,
`scripts/testing/test-delegate-codex-quota-precheck.sh`) — not conflated (see criterion 7). Only the two
MODIFY files changed within the A2 slice.

**2 — §4.2 fix correct in the bytes: PASS.** `dashboard.js:3900-3904` sets
`_qaProbeActive = p.availability === "current" && !["idle","terminal","unavailable"].includes(p.lifecycle_state ?? "unavailable")`.
Cadence `dashboard.js:3950` = `setTimeout(_qaProbePollOnce, _qaProbeActive ? 1000 : 2000)`. Therefore
1s ONLY when availability is `current` AND lifecycle_state ∉ {idle,terminal,unavailable}; 2s for idle,
terminal, unavailable, and stale (stale ⇒ availability ≠ current ⇒ inactive ⇒ 2s) — exactly per design
§4.2. Single-flight `_qaProbeInFlight` guard (`3908`), prior-controller abort (`3910-3914`),
`new AbortController()` + `setTimeout(() => ctrl.abort(), 750)` (`3915-3917`), visibility+lens gating
`!document.hidden && activeLens === "operations"` (`3880-3882`), and setText-only rendering (`3884-3905`,
no innerHTML) all present and unchanged.

**3 — R3 test genuinely closes the gap: PASS.** `test_dashboard_js_poller_cadence_semantics`
(`test:292-352`) extracts the real `_qaProbeRenderState` body verbatim from `dashboard.js` (`test:307`),
executes it under node against 8 representative fixtures (`test:314-323, 328-343`), and asserts the actual
resulting `_qaProbeActive` flag per state (`test:349-350`) — not the `"? 1000 : 2000"` substring. It also
asserts the old availability-blind predicate substring is absent (`test:309-312`). The fixture set
(idle→False, terminal→False, `stale+running`→False, `unavailable`→False, `current+running`/`current+starting`→True)
would fail against the old buggy predicate that polled idle/non-terminal-stale at 1s. Gap genuinely closed.

**4 — node dependency adjudication: PASS (with observation).** The R3 test hard-requires node
(`test:325-326` asserts `shutil.which("node") is not None`; it does NOT skip gracefully). Adjudication
resolves on the criterion's FIRST disjunct: node is a genuinely **declared, guaranteed** Nix package —
`nix/modules/core/base.nix:46` places `nodejs` in system packages (present on every host built from this
flake), reinforced by `nix/data/profile-system-packages.nix` and `nix/home/base.nix:375,518`. Confirmed
live: `node v24.16.0` at `~/.nix-profile/bin/node`. Additionally the test is NOT wired into the Tier-0
gate or any CI workflow (no reference in `scripts/governance/` or `.github/`) — it is a reviewer/manual
suite run on this NixOS host where node is guaranteed. Not a portability defect in the environments where
it runs. OBSERVATION (non-blocking): the test hard-fails rather than skipping, diverging from Tier-0's own
node handling which gracefully skips (`tier0-validation-gate.sh:292-294`); if this test is ever added to a
node-optional CI lane, converting the hard assert to a graceful skip would match the harness pattern.

**5 — Rest of accepted behavior unaffected: PASS.** Backend reader (`qa_runner.py`), route
(`aistack.py`), and card (`dashboard.html`) are the FROZEN three, byte-identical — projection stays a
read-only reader, never authority. No change outside the two MODIFY files.

**6 — Fresh re-runs: PASS.**
- `python3 scripts/testing/test-dashboard-qa-provider-probe.py` → PASS (offline, exit 0, all 19 checks).
- `py_compile` on the test → OK.
- `git diff --cached --check` on the two MODIFY paths → clean (no whitespace/conflict markers).
- Secret-scan on the two MODIFY diffs → no matches.
- Regression suites: `test-dashboard-qa-singleflight.py` PASS, `test-dashboard-qa-runner-runtime-env.py`
  PASS, `test-dashboard-compat-routes.py` PASS (21 routes).
- Runtime-surface adjacency `git log 3396f9df..HEAD`: two `docs(...)` governance commits (30f3f70b,
  28bff4a4); only non-doc file touched is `.claude/CLAUDE.md` (agent-instruction/governance, exempt). No
  A2 target file and no A1 heartbeat surface touched by intervening commits.

**7 — No prohibited action / no conflation: PASS.** Review was read-only except this verdict artifact and
the closing pulse. No subject edits, no staging/commit/Tier-0/delegation. The three delegate-codex quota
files staged alongside are a separate slice and were not evaluated as part of A2.

## Verdict

VERDICT: PASS
