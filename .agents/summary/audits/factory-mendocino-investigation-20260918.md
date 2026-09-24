# Mendocino factory deployment investigation — 2026-09-18

Disposition: **DIAGNOSTIC_FINDINGS_RECORDED / FIXES_PENDING**. This report is not implementation acceptance.

## Scope and evidence

Harness HEAD observed: `d0b814cba4ce845d12e45936bbf91a42bde54aac`.
The shared harness checkout contains concurrent staged and unstaged work; source observations
include those working files. No staging, commit, branch switch, deployment, authentication
change, service restart, or consumer-project edit was performed by this investigation.

Consumer: `/home/hyperd/Documents/Mendocino Coastal Plants` (the spelling is significant;
another nearby directory is named `Mendocino Costal Plants`). Original operator evidence is
preserved at `.agents/drops/2026-09-18-factory-test-run-findings-mendocino.md` and in the
consumer's `.agent/workflows/factory-test-run-findings.md` and `.agent/memory/issues-backlog.md`.
Reported failures were checked against installed files, source, disposable/in-memory
reproductions, and bounded read-only localhost probes. Remote lane login or inference was
not launched, and existing gate failures were not bypassed.

The consumer receipt `.factory/gate-install.json` records bundle `1.0.0-ft1`,
`ACTIVATION_BLOCKED`, `CONFIGURATION_BLOCKED`, and `HOOK_PATH_VERIFIED`.
It selects only `npm run build` and lists unconfigured test, lint, secret scan, live-service,
and freshness checks. `hooks.state=ACTIVE` describes hook routing, not successful checks.
This distinction is real: the installer leaves blocking hooks in place while readiness is blocked.

SHA-256 comparisons show installed source bundle files `MANIFEST.json`, `repo-structure.conf.tmpl`,
`agent-scaffolding/AGENTS.md.tmpl`, and `stack-adapters/resolve.py` match the current harness
source byte for byte. Their preserved template tokens are expected in this source copy;
tokens in installed executable destinations and agent-facing instructions are the defect.

## Findings and corrected classifications

| ID | Priority | Evidence disposition | Finding / next step |
| --- | --- | --- | --- |
| FF-000 | critical | source and in-memory reproduction confirmed | Root `intake_gateway.py` overrides the imported workflow implementation. Empty phase layers advance to COMMIT without artifacts; status/advance return `stub_status`/`stub_advanced` even for a nonexistent session. Supplied complexity/domain are dropped. Restore one canonical durable lifecycle authority or return explicit unavailable errors. |
| FF-001 | high | installed-file and lint reproduction confirmed | Structure policy assumes `src` and `tests` and a small allowlist. On this project it rejects 24 existing top-level entries and missing `tests`. Render a reviewed brownfield layout policy, including factory-created paths; preserve structural enforcement rather than disable it. |
| FF-002 | high | installed-file and source confirmed | `render_values()` deliberately falls back to `{{TEST_CMD}}`, `{{LINT_CMD}}`, and other raw tokens; `rendered()` preserves them. Agent instructions suggest executing these tokens. Separate human-readable unconfigured notices from executable command configuration; keep required checks fail-closed. |
| FF-003 | high | MCP schema/handler confirmed | `retrofit_workflow` exposes no confirmation-digest parameter or `--confirm-retrofit` forwarding. Add a digest parameter and preserve explicit current-preview confirmation. Automatically treating `force` as confirmation would defeat the accepted safety contract. |
| FF-004 | high | resolver reproduction confirmed; original polyglot claim corrected | MCP accepts arbitrary stack text, resolver accepts an enum: the reported text exits 2. Constrain/document the enum. Resolver already supports multiple **marker-declared** stacks; this project has `package.json` but no root `pyproject.toml`, so Python scripts are not detected. Add explicit project metadata or a reviewed discovery extension; do not claim the detector categorically lacks polyglot support. |
| FF-005 | high | manifest/install source confirmed; consumer workaround present | Installer does not seed mandated PULSE, RESUME, issue backlog, or archive paths. These now exist in the consumer because the operator created them. Include them in the previewed, collision-preserving installation manifest. |
| FF-006 | high | MCP source confirmed | `collective_task` calls `_run_local()` with its default 30-second subprocess timeout and captured output. It cannot expose a pollable job or partial result. Prefer durable async execution/polling over an arbitrary timeout increase. |
| FF-007 | high | operator telemetry report; underlying failure not independently recovered | Nine `worktree_handback_failed` calls were reported. Source proves the local shim emits that classification on `wt_handback` failure. The category hides which validation, staging, commit-hook, ancestry, or patch-write step failed. Correlate concrete task IDs, retained worktree, hook stderr and registry terminal reason before choosing a fix. No matching error receipts were found in this checkout's examined artifacts. |
| FF-008 | medium | timeout contract confirmed; current QA request not reproduced | MCP `harness_health` is limited to 5 seconds; it invokes `/qa/check`, which can take longer or be scheduler-delayed. Measure HTTP/scheduler/QA phases and surface typed pending/error states. Do not bypass thermal admission. |
| FF-009 | medium | HTTP observation confirmed; insecurity claim unproven | Public `/status` returns 200; `/coordinator/status`, `/openapi.json`, and `/docs` return 401. Middleware explicitly allows loopback `/status` and `/control/ai-coordinator/` prefixes. The MCP status route is `/control/ai-coordinator/status`, not `/coordinator/status`. Document canonical discovery/auth behavior; verify registration behind auth before claiming missing routes. Do not open protected endpoints as a diagnostic fix. |
| FF-010 | medium | MCP source confirmed | `coordinator_status` has an empty input schema and passes the full response to a global 4,000-character formatter. The formatter truthfully marks truncation but may omit operational fields. Add bounded field selection/summary and an explicit result budget. |
| FF-011 | medium | live anomaly and accounting reproduction confirmed | Live metrics show 133 retrievals, 160 retries, confidence 0.501 → 0.490, delta -0.012. Source retains only better per-call retries, yet concurrent completion corrupts aggregate final-confidence averages. This is a measurement defect; it does not establish that retained results worsen. Retry efficiency remains a separate benchmark question. |
| FF-012 | medium | process limitation | Gates cannot attest to earlier commits retroactively. Record pre-install work as unverified and review its content through a new verification receipt. Preserve historical commits. |
| FF-013 | high | bounded-capacity mismatch; runtime hard-limit claim needs measurement | Catalog declares small profile budgets, including default input 1,500/output 768 and common output 2,048. These do not prove every CLI/local modality has the same effective cap. Bind exact profile, payload normalization, generation budget, truncation and task size before adjustment. Generate hundreds of species records through deterministic data tooling or smaller slices; do not silently raise frozen model/budget settings. |
| FF-014 | low | historical timeout not reproduced now | Current `/v1/models` returns 200 in 0.07 seconds; `/health` returns 200, `/status` returns 404. Preserve the prior timeout with timestamp/transport evidence and add a bounded discovery probe; a service need not expose `/status` if `/health` is canonical. |
| FF-015 | medium | process-death claim retracted by final operator evidence | Final report proves the process remained active; lack of job/progress visibility caused the mistaken detach-death diagnosis. Preserve the retraction and fix progress/job/outcome observability. |
| FF-016 | critical | in-memory reproduction confirmed; constant-score claim corrected | Collective seeds one synthetic `antigravity-lead` contribution without dispatching that lane, creates generic design/implement/test phases, and scores their structure as 1.00/1.00/1.00. Scores are computed heuristics, not constants or task-quality evidence. No independent debate occurred. Preserve the requested objective/questions in phase context and require actual contributor receipts before claiming multi-agent collaboration. |
| FF-017 | high | silent-death claim retracted by final operator evidence | First run was killed by the operator's 900-second timeout; second was still calling the model after 14 minutes. Retained defect: extreme latency and no progress/job handle, not spontaneous disappearance. |
| FF-018 | high | CLI failure reported; local-harness outage not established | `qwen` OAuth CLI failure is distinct from locally hosted Qwen through llama.cpp/delegate-to-local. Local llama health currently returns 200, which does not prove tool-loop competence. Gemini CLI login is also distinct from the configured Antigravity IDE OAuth lane. Inventory each actual transport/auth state and capability before assignment. Do not add Gemini API keys or replace local routing based on a CLI-name collision. |
| FF-019 | low | likely writer identified; exact incident attribution pending | `workflow/safety_control_layer.py:19–38` defines relative `.agent/proposals/proposals.json`; constructing `SafetyControlLayer` creates it from the caller's cwd. This explains how consumer files can appear without an edit by the foreground agent. Correlate the original launcher before final attribution; make state location and writer provenance explicit. |
| collective-outcome-integrity | high | additional source-confirmed finding | `execute_collaborative_task()` records subtask failures but unconditionally marks the parent COMPLETED and archives outcome success. Failed phase results can therefore become false success. Add fail/partial aggregation and an outcome receipt; verify no success archive when a required phase fails. |
| consumer-outcome-coverage | high | additional verification gap confirmed | Existing greenfield and retrofit fixtures both pass while FF-001/002/005 remain observable in a real consumer. The fixtures establish preservation, refusal and routing but do not establish usable rendered contracts or policy-compatible consumer readiness. Add outcome tests for real layouts, no unresolved agent instructions and required collaboration scaffolding. |
| FF-020 | medium | final operator contract conflict recorded | Bounded edit lists omit required collaboration log paths. Declare a narrowly scoped coordination-write capability or make the orchestrator record worker events; do not grant unrestricted extra file writes. |
| FF-021 | high | final operator sandbox failure recorded | Raw `codex exec` delegation lacked writable sandbox authority and failed after substantial token use. Verify the actual managed dispatcher sets explicit sandbox/permission capability before edits; consumer CLI failure alone does not prove every harness lane has the same defect. |
| FF-022 | medium | final operator hook interception recorded | Lean-ctx invocation requirements were not hydrated into the delegated lane; teach approved tool invocation before work rather than disable the enforcement hook. |
| FF-023 | low | final operator patch-format failure recorded | Repeated operations on one file were rejected. Use one Update File operation containing multiple hunks; multiple hunks themselves are supported. |
| FF-024 | high | final operator background stdin failure recorded | Raw background CLI waited for stdin and produced no work. Audit the managed dispatcher for explicit prompt transport and stdin closure before diagnosing its launch path. |
| FF-025 | high | final operator identity/trust limitation recorded | Git-author email differs from implementing-agent identity, and arbitrary reviewer trailers cannot establish trusted independence. Reuse explicit lane/subject-bound reviewer receipts and FT-7 backstop; lane text alone is not a trusted attestation. |
| FF-026 | high | final operator analysis/edit mismatch recorded | Planning debate triggered edit-forcing intervention after zero edits. Require artifact/intent-aware completion and planning/review tool authority; preserve coding-edit intervention where edits are actually required. |
| FF-027 | high | final operator recovery-budget limitation recorded | No-progress retry reduced output to 512 tokens. Reconcile existing frozen retry semantics with deliverable-aware typed degraded/partial outcomes in a separately reviewed local-inference slice; do not silently alter budgets from this report. |

Final operator-report reconciliation: both copies match SHA-256
`5ad9a9fa2c82aab7620ed7c2f08213699e5de3356c9baed7c3e2dcd9ac811bb0`.
The operator repaired the consumer configuration and reports four gated commits;
this does not show that reusable installer defects are fixed upstream. Two
preliminary additional findings formerly labelled FF-020/021 here were renamed
to functional identifiers above because the final operator report uses those
numbers for different findings. The historical diagnostic scope remains unchanged;
the owner subsequently authorized implementation through the canonical factory PRD.

## Reproduction evidence

1. Read-only structure check, run using the source bundle script against the real installed policy:

   `FACTORY_REPO_ROOT='/home/hyperd/Documents/Mendocino Coastal Plants' bash templates/factory-gate-bundle/repo-structure-lint --pre-commit`

   Exit 1: `required path missing: tests`, plus 24 undeclared top-level entries, including
   `.agent`, `AGENTS.md`, `package.json`, `public`, `data`, `scripts`, and existing documents.
   No build, target hook, or commit was executed. The template header alone is not proof of a
   render failure: directory placeholders were rendered, but the chosen policy is incompatible.

2. Resolver, read-only:

   `python3 templates/factory-gate-bundle/stack-adapters/resolve.py '<consumer path>'`

   Returns stacks `[node]`, build READY, test/lint/secret scan UNCONFIGURED. The reported free-text
   `--override` exits 2 with enum-choice error. `resolve.py:15–18,65–77` already constructs
   profiles for every present conventional root marker.

3. Lifecycle, isolated source-handler reproduction: AST-loaded root module with only its wildcard
   forwarding import excluded and registry/router globals unset; fake request, no HTTP POST,
   no persistence or agent dispatch. Supplied `complexity=complex`, `domain=python` yielded
   `current_phase=COMMIT`, `complexity=simple`, `domain_hint=general`, HTTP 200.
   Status/advance for `diagnostic-nonexistent` both returned HTTP 200 stubs.
   Active server imports the overriding root module at `http_server_impl.py:160`.
   This reproduces source behavior and corroborates the operator's live observations; it is not
   a new live workflow execution.

4. Planner, isolated in-memory reproduction: initialize `CollaborativePlanning` via `__new__`,
   use `PlanValidator`, and replace persistence with a no-op; create one synthetic contribution
   without suggested phases. No model, login, network, or home-state write occurs.
   Result: one contributor, phases `Design the solution` / `Implement the solution` /
   `Test the implementation`, all three scores 1.0. `check_completeness()` checks phase types,
   `check_coherence()` their order, and `check_feasibility()` accepts unassigned phases.
   An earlier constructor-based probe attempted home-cache persistence and was blocked by the
   filesystem sandbox; it was replaced with this in-memory diagnostic without escalation.

5. RAG metric reproduction: load `knowledge/rag_reflection.py` in an isolated module; two
   controlled coroutines begin with confidences 0.2 and 0.8, return unchanged results, and
   finish in reverse start order. Actual initial/final means are both 0.5; reported final mean
   is 0.2 and delta is -0.3. Both per-call improvements are 0.0. The final average uses each
   request's start-time `n` after awaiting retrieval (`rag_reflection.py:257–261,305–309`).
   Reconcile started and completed counts and paired quality samples before optimizing retries.

6. Bounded unauthenticated GET probes (3-second ceiling; sandbox required explicit localhost
   access): coordinator `/status` 200; `/coordinator/status`, `/openapi.json`, `/docs` 401;
   switchboard `/health` 200, `/status` 404, `/v1/models` 200; llama `/health` 200.
   These establish response behavior at inspection time, not full integration or auth eligibility.

7. Existing disposable-fixture suites both exit 0:

   - `python3 scripts/testing/test-factory-gate-retrofit.py`: preview_read_only,
     confirmation_enforced, originals_preserved, hooks_composed all true.
   - `python3 scripts/testing/test-factory-gate-install.py`: hooks_block_bad_commit,
     tracker_discovered, collision_preserved, unconfigured_blocked all true.

## Bounded follow-up queue for dev agents

These are proposed implementation boundaries from diagnosis, not dispatches or final approval.
Keep one root cause per reviewed commit; use disposable consumers rather than editing this
user project to discover installer semantics.

1. **Rendered consumer policy** (FF-001): installer + structure-policy fixture. Preserve observed
   brownfield layout through the preview digest and explicitly define handling of generated
   paths. Prove declared existing paths pass, an undeclared new path fails, and stale layout
   confirmation refuses before writes. Include all installer-created root paths.
2. **Command/contract rendering** (FF-002): keep check state separate from command text; installed
   agent docs show actionable configuration gaps with no unresolved tokens. Unconfigured required
   executable checks must still block. Preserve the pristine source bundle for recovery.
3. **Collaboration scaffolding** (FF-005): add exact previewed paths with initial valid JSON and
   collision preservation. Prove first pulse/resume writes work and existing consumer state is
   unchanged. Do not infer a mandated directory is absent after the operator has repaired it.
4. **MCP retrofit parity** (FF-003/004): schema enum, exact digest parameter/forwarding, fixture
   tests proving missing/stale confirmation does not mutate and `force` cannot bypass consent.
5. **Truthful collective results** (FF-016 / collective-outcome-integrity): actual contributor receipts, objective-preserving
   plan, honest scope of structural scores, and required-phase failure aggregation. This needs
   an architect/reviewer before implementation because it affects orchestration authority.
6. **RAG accounting** (FF-011): completed-count/paired confidence accounting with deterministic
   reverse-completion and partial-in-flight tests. Benchmark retry utility only after metrics
   are correct; do not tune retries based on corrupted averages.
7. **Handback diagnosis** (FF-007): recover exact task IDs and retained worktree/hook receipts;
   identify the first failing step. Keep failed artifacts and classify uncertainty until proven.
8. **Operational MCP results** (FF-006/008/010/015/017): progress/job/terminal receipt and bounded
   status projections through existing authorities. Capture timeout, scheduler delay and signal
   independently. Preserve thermal and auth policies.
9. **Transport-specific lane readiness** (FF-018): separate qwen CLI, local inference/tool loop,
   Gemini CLI and Antigravity IDE paths. Test the configured path, not whichever same-name binary
   exists. Surface typed unavailable/auth-required states before assignment.
10. **Proposal provenance** (FF-019): confirm invocation, explicit state root and write event;
    no unsolicited writes into consumer cwd during read-only diagnostics.

FF-009/012/013/014 require documentation, correlation or measured task-shaping decisions first;
they are not authority to weaken authentication, rewrite history, increase model budgets or
force configuration gaps to green. Consumer-outcome-coverage is the shared regression acceptance condition for
the relevant fixes. Consumer readiness and later real deployment verification remain separate.
