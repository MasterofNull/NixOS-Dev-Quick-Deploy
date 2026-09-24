# Agentic Software Factory — Test Run 2 (delta against run 1)

Second in-situ run after harness changes. Handoff for the NixOS-Dev-Quick-Deploy developers.

- **Date:** 2026-09-18, later same day
- **Run 1 harness HEAD:** `d0b814cb`
- **Run 2 harness HEAD:** `cec0012d` (4 commits later)
- **Target repo:** Mendocino-Coastal-Plants, factory already installed and green from run 1
- **Repo state at start:** tree clean, gate `passed=6 warned=2 failed=0`

Run 1's report is `factory-test-run-findings.md` (28 findings). This document records only what
changed. Every check below was re-run, not assumed.

## Headline

**The redeploy could not be completed.** `aqd workflows retrofit` now refuses to run against this
repo with `blocker: "unsupported existing core.hooksPath: .githooks"` — the exact value the
retrofit itself set during run 1. `installation: {"state": "REFUSED"}`, `safe_to_install: false`.
The tool cannot re-run on a repo it successfully configured, so there is no upgrade path from
bundle 1.0.0-ft1 to the current templates.

It refused cleanly and wrote nothing, which is the correct failure mode. But refusing is all it does.

## Fixed

| ID | What changed |
| --- | --- |
| FF-001 | Brownfield layout is fixed. The retrofit no longer ships `repo-structure.conf` as a raw template over a real repo; its write set is now confined to `.factory/gate-bundle/**` plus `.agent/archive/.gitkeep`. |
| FF-002 (partial) | Existing files are now preserved rather than clobbered. 15 paths were listed as `preserved` with SHA-256s, including `.agent/collaboration/PULSE.log`, `RESUME.json`, `issues-backlog.md`, the configured hooks and the role contracts. |
| FF-005 (partial) | `.agent/archive` is now created by the installer. `.agent/collaboration/` and `.agent/memory/` still are not, so a fresh repo still cannot satisfy SHARED-RULES rules 5, 6 and 7 on first action. |

Also genuinely better: the stack detector now picks up `test` and `lint` from `package.json`
(`"test": "npm run test"`, `"lint": "npm run lint"`, both `READY`), where run 1 found neither.

## New and regressed

### R2-001 — retrofit is not idempotent and blocks its own redeploy
- Severity: **critical**
- Component: `aqd workflows retrofit`, `factory_gate_install.py`
- Detail: After a successful install, `core.hooksPath` is `.githooks`. On re-run the retrofit treats
  that as an unsupported pre-existing configuration and refuses:
  ```
  "blocker": "unsupported existing core.hooksPath: .githooks"
  "installation": {"state": "REFUSED"}
  "safe_to_install": false
  ```
  The refusal fires both for the preview and for the digest-confirmed install.
- Impact: no upgrade path. A repo that adopted the factory is frozen at whatever bundle version it
  first received. This is the defect that stopped this run.
- Suggested fix: recognise a hooksPath the factory itself installed (the receipt records it) and
  treat that as an upgrade rather than a foreign configuration.

### R2-002 — `factory-gate-status` and the new preflight report stale receipt state as truth
- Severity: **high**
- Component: `aqd workflows factory-gate-status`, `factory-gate-preflight` (FT-5)
- Detail: Both commands report this repo as unconfigured and blocked:
  ```
  "activation": "ACTIVATION_BLOCKED"
  "checks": {"commands": {"build": "npm run build"},
             "required_unconfigured": ["test: ... no safe conventional test command declared",
                                       "lint: ... no safe conventional lint command declared", ...]}
  ```
  The live repo disagrees. `scripts/governance/gate-runner --pre-commit` returns
  `passed=6 warned=2 failed=0` with `hard-40-test` and `hard-50-lint` both PASS, and
  `package.json` declares both scripts. The retrofit's own detector, run minutes earlier in the
  same toolchain, correctly reported both as `READY`.
- Cause: both commands read `.factory/gate-install.json`, a receipt written once at install time
  and never refreshed. They report history, not state.
- Impact: a readiness gate that reports a fully configured, green repo as not ready is worse than
  no gate, because CI would block on it. It also contradicts a sibling command in the same run.
- Suggested fix: have status and preflight evaluate live state, or refresh the receipt whenever
  checks change.

### R2-003 — the new preflight requires evidence the installed gate-runner never writes
- Severity: **high**
- Component: FT-5 preflight vs. gate bundle 1.0.0-ft1
- Detail: Preflight blocks on
  `MISSING_EXECUTION_EVIDENCE: {"path": ".factory/gate-run-evidence.json", "present": false}`.
  The installed `scripts/governance/gate-runner` contains zero references to that filename, so it
  cannot ever produce it. Commit `cec0012d` added 195 lines to the *template* gate-runner, but the
  repo holds the 1.0.0-ft1 runner and R2-001 prevents upgrading it.
- Impact: version skew with no escape. The new readiness check requires an artifact only the new
  runner emits, and the new runner cannot be installed.
- Suggested fix: version-gate the evidence requirement, and fix R2-001 so bundles can be upgraded.

### R2-004 — `force: true` now emits a flag the retrofit CLI rejects
- Severity: medium (regression)
- Component: MCP `retrofit_workflow`
- Detail: `retrofit_workflow(force=true)` now fails with
  `AI_LAYER_ERROR code: unknown_option detail: Unknown option: --force`.
  `--force` is accepted by `project-init`, `brownfield` and `bootstrap`, but the retrofit usage line
  is `retrofit --target <dir> --name <project> [--confirm-retrofit <preview-digest>]`. Commit
  `1f2237b1` states "force appends --force", but retrofit has no such flag. In run 1 `force` was
  inert; now it is an error.
- Suggested fix: drop `force` from the retrofit bridge, or add `--force` to the retrofit CLI.

### R2-005 — the coordinator recommends an unauthenticated lane
- Severity: high
- Component: `get_hints` prompt coaching / routing
- Detail: `get_hints` returned `"recommended_agent": "qwen"` and
  `"suggested_prompt": "... Route: qwen ..."`. The qwen lane cannot authenticate
  (see FF-018, still unfixed). The router recommends the one lane guaranteed to fail.
- Suggested fix: filter routing recommendations by live lane auth status.

### R2-006 — preflight reports the coordinator lane unavailable while it is serving
- Severity: low
- Component: FT-5 preflight
- Detail: Preflight reported
  `"lanes": {"hybrid_coordinator": {"state": "TRANSPORT_UNAVAILABLE"}}` during a session in which
  every MCP call to that same coordinator succeeded. Marked "informational only", so it does not
  block, but it is wrong.

### R2-007 — codex token cost for an identical trivial prompt rose 2.65x
- Severity: medium
- Component: codex lane
- Detail: The prompt `Reply with exactly: READY` cost 6,744 tokens in run 1 and 17,887 tokens in
  run 2. Same binary version (0.154.0), same prompt, same repo. Something now injects substantially
  more context per call. At delegation scale this is a direct cost multiplier.
- Suggested fix: identify what grew in the per-call preamble.

## Persists unchanged

Re-tested this run, same result as run 1.

| ID | Severity | Status this run |
| --- | --- | --- |
| FF-000 | critical | `agent_intake` on a new task still returns `current_phase: "COMMIT"`; `lifecycle_status` still returns `stub_status`. **New detail:** an explicit `complexity: "complex"` was downgraded to `"standard"`, and `domain: "python"` still returns `domain_hint: "general"`. |
| FF-018 | critical | codex works; qwen still "OAuth free tier was discontinued on 2026-04-15"; gemini still blocks on an interactive browser prompt. One of three lanes usable. |
| FF-007 | high | Worse, with numbers. `ai_coordinator_delegate` now reports **49.2% backend success across 65 calls, 33 backend failures, and 11.1% success in the last hour**, top error still `worktree_handback_failed`. Commit `97b063d5` did not resolve it. |
| FF-006 | high | `collective_task` still `local command timed out after 30s`. |
| FF-004 | high | MCP `stack` still typed free-text and still hard-fails on a descriptive value with the `resolve.py --override` argparse error. A valid enum value (`node`) works. |
| FF-003 | high | Live MCP schema still exposes no `confirm_retrofit`, despite `1f2237b1` adding it. The running server appears to be serving a stale schema. |
| FF-008 | medium | `harness_health(phase=0)` still returns `{"error": "timed out"}`. |
| FF-010 | medium | `coordinator_status` and `get_hints` still truncate at 4000 chars with no override. |

FF-016, FF-026 and FF-027 (collective behaviour, prose rejection, 512-token degradation) were not
re-exercised to completion this run, because FF-006 still blocks the MCP path and a direct CLI run
would repeat run 1's 15-minute inconclusive cycle. They should be retested once FF-006 is fixed.

## Recommended order

1. **R2-001** — nothing else can be delivered to an adopting repo until redeploy works.
2. **R2-003 + R2-002** — the readiness story is currently self-contradictory: one command says green,
   two say blocked, and the blocker requires an artifact that cannot be installed.
3. **FF-000** — still the spine, still stubbed, unchanged across both runs.
4. **FF-018 + R2-005** — one working lane, and the router points at a dead one.
5. **FF-007** — 11.1% success in the last hour is a hard blocker for the delegation tier.
