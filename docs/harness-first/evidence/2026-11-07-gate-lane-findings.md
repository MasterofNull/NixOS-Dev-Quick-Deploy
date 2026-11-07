# 2026-11-07 gate-lane-findings

## Objective
Fix the highest-value findings of the 2026-11-06 gate sweep (`2026-11-06-sweep-gates.md`) and lane sweep (`2026-11-06-sweep-lanes.md`, branch feat/sweep-lanes). A gate must fail on bad input and nothing here weakens one. The review gate and trust paths are not changed beyond the listed lane items (retired-lane grants and egress allowlist).

## Workflow/Session IDs
Branch fix/gate-and-lane-findings, date 2026-11-07. Staged, not committed.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded slice with regression tests).

## Commands Executed
- `scripts/governance/sweep-gates.py --exercise --json` before and after (note: its `--exercise` probes clone committed HEAD, so probe-based findings cannot clear until this is committed; static findings reflect the working tree)
- `python3 scripts/testing/test-gate-lane-findings.py` on the fixed tree (all pass) and on `git archive HEAD` of the old tree (19 FAIL)
- `scripts/testing/test-tier0-gate-placement.py`, `test-tier0d-gate-mutation.py` (36/36), `test-ci-checks-manifest.py`, `test-check-frontier-fold.py`, `test-lane-eligibility.py`, `test-agent-agnostic-router.py`, `test-remote-lane-egress.py`, `test-agent-mcp-client-projection.py`: pass
- `tier0.d/check-ci-test-coverage.sh`, `check-ci-manifest-coverage.sh`, `check-instruction-budget.sh`, `check-lane-hook-parity.sh`: pass. tier0 and run-ci-checks (full) were not run, as instructed.

## Validation Evidence

Sweep class counts (gates per class, this tree, --exercise):

| Class | Before | After |
|---|---|---|
| CANNOT_FAIL | 3 | 3 (probe-based; clears once committed, see above; remaining unit gate_deploy_batch_size is item 3) |
| FAIL_OPEN | 35 | 25 (ten tier0 language gates cleared) |
| MASKED_IN_CI | 6 | 6 |
| NO_BAD_INPUT_TEST | 93 | 90 (four new manifest wrappers appear as ci-check units without a named bad-input test) |
| UNCOVERED | 42 | 35 |

### Gate items
1. `tier0.d/check-frontier-fold` never ran (tier0 globbed `*.sh`; file is Python). Renamed to `check-frontier-fold.py`; tier0 now loops `*.sh` and `*.py` (python3 for the latter); README, mutation-suite map and its test updated. Run on the tree: PASS (no scheduled backlog items), so no real failure was hiding.
2. `collect_changed_files` no longer ends in `|| true`. No `origin/main` (or a failed diff) scans every tracked file with a WARN; if `git ls-files` also fails the run is terminated (callers read it through process substitution, so a return code would be lost). Pre-commit and doc-only behaviour unchanged (tested: staged only, empty when nothing staged, only the diff when origin/main resolves).
3. `gate_deploy_batch_size`: NOT changed, decision needed. Its text is an explicit advisory ("recommend 3-5 before deploy"), it calls `pass` on both branches, and the call site is `gate_deploy_batch_size || true`. No policy in the repo sets a minimum batch (searched docs, config, scripts), so any hard threshold would be invented. Decision: keep advisory (then the sweep entry is a known false positive to exempt) or ratify a minimum.
4. Hooks. `pre-merge-commit` (safety guard) now exits 1 with a clear message when `check-mergeable.sh` is missing. `pre-push`: its runner (`scripts/governance/quick-deploy-lint.sh`) was already fail-closed; the one silent path was the explicit `PRE_PUSH_CI_PARITY=1` opt-in, which passed when its runners were absent; it now fails. `post-checkout` and `post-merge` stay advisory (they only refresh context caches and gate nothing); comment added. Not changed: `pre-push` passes with a WARNING when gitleaks is not on PATH (documented; CI scans after the push).
5. Unreferenced scripts (13):
   - Wired into the manifest (`config/ci-checks.json`) and run by the `syntax` job in test.yml, all pass: `check-doc-lifecycle-hygiene.py`, `check-doc-frontmatter.py --all`, `check-workflow-script-refs.sh`, `check-agent-context-tooling.sh`, `check-context-bootstrap.sh`, `check-aq-integrity-logical-baseline.py`. `check-workflow-script-refs.sh` first failed on the tree: a false positive on `scripts/testing/test-*` in a workflow job name; fixed in the checker (glob mentions skipped), tested both ways.
   - Fails on the tree, a real finding, not wired: `check-flake-age.sh` (3 locked inputs under 48 h: enable-container-tests 37 h, nixified-ai 37 h, nixos-hardware 47 h; time-based, clears on its own, and by Rule 19 belongs in `--maintenance`/pre-deploy, not pre-commit). Decision: wire into `--pre-deploy` or accept it as maintenance.
   - Fails on the tree, stale: `validate-phase-5.2.sh` (checks `lib/search/__init__.py` and other paths that no longer exist). Decision: archive with reason "phase 5.2 deliverables relocated" or repair.
   - Need the live stack (not run, not wired): `verify-dashboard-apis.py` (:8889), `check-knowledge-base-breadth.sh` (AIDB), `validate-deployment-monitoring-alerting.sh`, `validate-query-agent-storage-learning.sh` (end-to-end scenarios that write state). Decision: list as `ci_exempt` with class live-service, or add to a `--maintenance` stage.
   - Host diagnostic, not a gate: `scripts/governance/verify-profile-cleanup.sh` (exits 0 when the home-manager profile is absent). Decision: archive or exempt.
   Nothing was deleted.

### Lane items
6. `rea` MCP. Root cause: nothing declares or installs a `rea` executable. The launcher `scripts/ai/mcp-rea-sandboxed` and the intake record exist, but no Nix package, home-manager entry or PATH provides `rea` (`which rea` empty; no `rea` in nix/). The npm package is `@morluto/rea` (the `rea` name on npm is something else). Reading its 0.1.0 tarball: it is "reverse-engineering automation for Hopper Disassembler", requires macOS 12+ and the proprietary Hopper application, and its tool names do not include the allowlist in the intake record (`analyze_javascript_application`, etc. do not appear). The recorded integrity pin `sha256-47DEQpj8...` matches neither the tarball sha256 (`eb917afe...`) nor npm's sha512. So packaging it in Nix would not give a working server on this host and the intake premises are wrong. No Nix change made; nothing silently dropped. Decision for the owner: re-open the intake and set the candidate to blocked/disabled (and remove `rea` from `.mcp.json`, `.gemini/settings.json`, `ai-stack/continue/config.json`, and Codex if present), or name a Linux-capable replacement.
7. Retired Antigravity lane. `config/lane-eligibility-registry.json`: research and reviewer grants withdrawn through `aq-lane-eligibility revoke` (non-hard), `retired` marker added; the implementer hard block is kept because `aq-role-route` has a hardcoded backstop for it and `test-lane-eligibility.py` asserts it. A hard block on research/reviewer would have blocked the whole shared `gemini` routing lane (any hard block wins), so it was not used; gemini keeps its own research/reviewer grants (verified). `config/remote-lane-egress.json`: `antigravity` and `agy` allowlists emptied (any traffic labelled with them is a hold) and marked retired; lane keys kept because `LANES` in `scripts/ai/lib/remote_lane_egress.py` still names them. Readers checked: `aq-lane-eligibility`, `aq-role-route`, `remote_lane_egress.py`; their tests pass. Historical registry rows were not edited.
8. semgrep for Codex. Real oversight: catalog `semgrep-mcp` lists codex in `agent_access`, repo `.mcp.json` and Gemini carry it, but the Codex projection in `nix/home/base.nix` (`reconcileAgentMcpClients`, yq transform on `~/.codex/config.toml`) did not. Added `mcp_servers.semgrep` there (approval mode prompt, tracing off) and an assertion to `test-agent-mcp-client-projection.py`. `~/.codex` not touched.

### Rebuild items
- Item 8 is a Nix (Home Manager activation) change: takes effect at the next rebuild/`home-manager` switch; until then Codex still lacks semgrep.
- Everything else is checkout-only.

### Regression tests
`scripts/testing/test-gate-lane-findings.py` (registered as `gate-lane-findings-tests`, run by the manifest-tests job): 29 checks covering items 1, 2, 4, the workflow-refs fix, item 7, item 8 and the manifest wiring. Run against `git archive HEAD` it fails 19 of them; on the fixed tree it passes all.

## Rollback Plan
Revert the staged changes. The tier0.d rename reverts with the loop edit; the registry edits revert by restoring the two config files.
