# Agentic Software Factory — In-Situ Test Run Findings

Handoff report for the NixOS-Dev-Quick-Deploy development agents.

- **Date:** 2026-09-18
- **Test vehicle:** Mendocino-Coastal-Plants (real project, not a fixture)
- **Operator lane:** claude, acting as orchestrator
- **Purpose:** exercise the factory end to end on real work and record what does not work

## Environment

| Component | Version |
| --- | --- |
| aqd | 0.7.0 |
| Factory gate bundle | 1.0.0-ft1 |
| Harness HEAD | d0b814cb feat(local): record producer phase timing metadata |
| Python | 3.13.15 |
| Node / npm | v24.19.0 / 11.17.0 |
| Coordinator | 127.0.0.1:8003 |
| Switchboard | 127.0.0.1:8085 |
| Local LLM | 127.0.0.1:8080 (active.gguf) |

Target repo: Vite PWA (vanilla JS) plus a Python 3.13 data pipeline. `npm run build` passes.
No test suite, no linter, gitleaks not installed.

## Severity summary

| ID | Severity | Component | One line |
| --- | --- | --- | --- |
| FF-000 | critical | agent_intake / lifecycle | The orchestration lifecycle is a stub |
| FF-016 | critical | aq-collective | Not a multi-agent debate; returns constant 1.00 validation scores |
| FF-018 | critical | agent lanes | Only 1 of 3 implementation lanes is authenticated |
| FF-001 | high | retrofit | Installs `repo-structure.conf` as an unrendered template |
| FF-002 | high | retrofit | `{{PLACEHOLDER}}` tokens ship unrendered into the consumer repo |
| FF-003 | high | MCP retrofit_workflow | Cannot complete an installation through MCP |
| FF-004 | high | MCP retrofit_workflow | `stack` parameter hard-fails on its own documented type |
| FF-005 | high | retrofit | Canon mandates collaboration artifacts the installer never creates |
| FF-006 | high | MCP collective_task | 30 second wrapper timeout |
| FF-007 | high | delegation | `ai_coordinator_delegate` failing with `worktree_handback_failed` |
| FF-013 | high | switchboard | Token budgets make the delegation tier unusable for real slices |
| FF-017 | high | aq-collective | No progress reporting; extreme latency (corrected) |
| FF-008 | medium | MCP harness_health | Times out |
| FF-009 | medium | coordinator API | Auth inconsistent and undocumented; `/openapi.json` closed |
| FF-010 | medium | MCP coordinator_status | Truncates at 4000 chars with no override |
| FF-011 | medium | RAG reflection | Retries reduce answer confidence |
| FF-015 | medium | aq-collective | No way to tell working from hung (corrected) |
| FF-012 | medium | process | Work done before retrofit cannot be gate-protected |
| FF-014 | low | switchboard | `/v1/models` times out, `/status` absent |
| FF-020 | high | SHARED-RULES | Bounded-slice contract contradicts the mandatory pulse-log rule |
| FF-021 | high | delegation | Delegated agents run read-only by default, producing nothing |
| FF-022 | medium | PreToolUse hook | lean-ctx hook blocks delegated agents mid-task |
| FF-024 | medium | delegation | Background `codex exec` hangs on stdin and exits 144 |
| FF-019 | low | .agent/proposals | File appears without provenance |
| FF-023 | low | codex-cli | `apply_patch` rejects multi-hunk edits to one file |
| FF-025 | high | commit-msg hook | Independent-review check verifies git identity, not agent independence |
| FF-026 | high | agent_executor | Demands file edits from analysis tasks and nudges against prose |
| FF-027 | high | agent_executor | Stalls, then silently degrades the request to 512 tokens |

## Critical

### FF-000 — the orchestration lifecycle is a stub

`agent_intake` is documented as "the SINGLE ENTRY POINT for all orchestrated tasks", returning
the phase sequence INTAKE → DISCOVER → PRD → PLAN → ASSIGN → DELEGATE → VALIDATE → COMMIT.

Reproduce:
```
agent_intake(prompt="<complex multi-part task>", complexity="complex", domain="python")
  -> {"session_id":"80e0f7fb-...","current_phase":"COMMIT","domain_hint":"general","next_action":"proceed"}
lifecycle_status(session_id="80e0f7fb-...")   -> {"status":"stub_status"}
lifecycle_advance(session_id="80e0f7fb-...")  -> {"status":"stub_advanced"}
```

A brand new complex task returns `current_phase: "COMMIT"`, skipping every phase including the
PRD and delegation steps the factory is built around. Both lifecycle calls return placeholders.
The `domain: "python"` argument came back as `domain_hint: "general"`, so the domain hint is dropped.

Impact: this is the spine of the intended workflow. Without it there is no enforced progression
from PRD to plan to assignment to review, no phase context pruning, and no record that a phase
completed. Every agent must hand-roll the process, which is what the factory exists to prevent.
Worse, the stubs return success-shaped values, so a caller believes it is orchestrated when it is not.

Suggested fix: implement the lifecycle store, or make the stubs fail loudly.

### FF-016 — `aq-collective` is not a multi-agent debate and returns fabricated validation scores

Given a six-question architecture debate, the log shows:
```
collaborative_planning: plan_created: plan_id=plan-coll-... mode=parallel
collaborative_planning: contribution_added: agent_id=antigravity-lead
collaborative_planning: plan_validated: feasibility=1.00 completeness=1.00 coherence=1.00
collaborative_planning: plan_synthesized: phases=3 feasibility=1.00 completeness=1.00 coherence=1.00
agent_executor: Task coll-...-p0 executing locally: Simple task, local agent capable
```

Three problems, all visible in five log lines:
1. **One contributor.** `antigravity-lead` only. No second lane contributed, so nothing was debated.
2. **Constant scores.** All three metrics returned exactly 1.00, 0.3 seconds after plan creation,
   on a plan nothing had examined. These are constants, not measurements.
3. **Misclassification.** A six-part architecture debate was labelled "Simple task, local agent
   capable" and routed entirely to the local model. Output was three generic phases starting
   "Design the solution". None of the six questions were addressed.

Impact: the collaboration tier used for PRD and plan review does not convene multiple agents and
does not validate. An orchestrator trusting `feasibility=1.00` is trusting a hardcoded value.

Suggested fix: make the scores real or remove them; require more than one lane to contribute
before calling the result a collective plan; fix complexity classification for multi-part tasks.

### FF-018 — only one of three implementation lanes is authenticated

Project routing assigns codex to orchestrator/reviewer, qwen to implementation and test slices,
and claude to architecture. Actual lane status:

| Lane | Binary | Status |
| --- | --- | --- |
| codex | codex-cli 0.154.0 | **works** — `codex exec` returned a correct response, 6,744 tokens |
| qwen | qwen (npm global) | **dead** — "Qwen OAuth free tier was discontinued on 2026-04-15. Run /auth to switch to Coding Plan, OpenRouter, Fireworks AI, or another provider." |
| gemini | gemini 0.49.0 | **blocked** — prompts "Opening authentication page in your browser. Do you want to continue? [Y/n]" and hangs; unusable non-interactively |

Impact: the designated *implementer* lane is the dead one. Only the reviewer lane works. This
also breaks SHARED-RULES rule 10, "an author cannot accept their own work": with a single working
lane there is no independent reviewer, so the review gate cannot be satisfied honestly.

Suggested fix: re-authenticate qwen against a supported provider, add non-interactive auth for
gemini (API key via env), and have the harness health check report per-lane auth status so this
is caught before a task is assigned rather than at delegation time.

## High

### FF-001 — retrofit installs `repo-structure.conf` as an unrendered template

Installed content:
```
# Render into .factory/repo-structure.conf in the consumer repository.
required=src
required=tests
allowed_top=.factory
allowed_top=.git
...
```
The template header is still there. On any brownfield repo `hard-10-repo-structure` then fails
immediately, listing every real top-level path as undeclared (24 paths here) plus
`required path missing: tests`. Gate activation is blocked by a file the installer wrote.

Suggested fix: render this from the detector's observed tree, or ship it empty with documented opt-in.

### FF-002 — `{{PLACEHOLDER}}` tokens ship unrendered into the consumer repo

`AGENTS.md` as installed:
```
Test: {{TEST_CMD}}
Lint: {{LINT_CMD}}
Secret scan: {{SECRET_SCAN_CMD}}
```
`.agent/WORKFLOW-CANON.md` step 5 likewise instructs agents to run `{{TEST_CMD}}`, `{{LINT_CMD}}`
and `{{SECRET_SCAN_CMD}}`. Gate failures also print raw tokens:
```
UNCONFIGURED: render {{SECRET_SCAN_CMD}} or explicitly set FACTORY_SECRET_SCAN_NOT_APPLICABLE=1
UNCONFIGURED: render {{FRESHNESS_CHECK_CMD}} or explicitly set FACTORY_FRESHNESS_NOT_APPLICABLE=1
```
An agent reading its own contract file is told to execute a literal `{{TEST_CMD}}`.

Suggested fix: when a check is UNCONFIGURED, emit an explicit "not configured" sentence, never the token.

### FF-003 — `retrofit_workflow` MCP tool cannot complete an installation

The CLI requires `--confirm-retrofit <preview-digest>` to move from preview to install. The MCP
tool exposes `force` but no way to pass the digest, so every MCP call returns `operation:
retrofit-preview` and the operator must drop to the raw CLI to finish. The MCP surface is
preview-only in practice.

Suggested fix: add a `confirm_retrofit` parameter, or have `force: true` chain preview → confirm.

### FF-004 — `retrofit_workflow` `stack` parameter hard-fails on its own documented type

The MCP schema types `stack` as a free-text string. It is passed to `resolve.py --override`,
which accepts only `{python,node,rust,go,nix,generic}`:
```
stack detector failed: resolve.py: error: argument --override: invalid choice:
'vite pwa (vanilla js) + python 3.13 data pipeline + json/spreadsheet ssot'
```
Any honest description of a polyglot stack aborts the workflow. Omitting `stack` works, because
auto-detection succeeds. Note the detector also reports only `node` for a repo that is roughly
half Python, so a polyglot repo silently gets single-stack checks.

Suggested fix: constrain the parameter to the enum in the MCP schema, or map free text onto it.
Separately, let the detector return multiple stacks and compose their checks.

### FF-005 — canon mandates collaboration artifacts the installer never creates

SHARED-RULES rules 5, 6, 7 and 12 require every agent to write `.agent/collaboration/PULSE.log`,
update `.agent/collaboration/RESUME.json`, log defects to `.agent/memory/issues-backlog.md`, and
archive to `.agent/archive/`. The retrofit creates none of these four paths. A compliant agent's
first action fails on a missing directory. Created by hand in this repo.

Suggested fix: seed all four paths during retrofit.

### FF-006 — `collective_task` MCP wrapper times out at 30s

```
{"ok": false, "error": "local command timed out after 30s"}
```
A multi-agent planning debate cannot finish in 30 seconds; the underlying `aq-collective` took
over 100 seconds just to reach its first model response. The wrapper discards work in flight.

Suggested fix: raise the timeout substantially, or make it asynchronous with a pollable job handle.

### FF-007 — `ai_coordinator_delegate` failing with `worktree_handback_failed`

Surfaced by `get_hints` as a runtime signal: "ai_coordinator_delegate failed 9 times recently.
Top error: worktree_handback_failed". This is the exact path the factory uses to hand bounded
slices to cheaper agents, so the cost-saving tier is unreliable independent of FF-018.

Suggested fix: investigate the worktree handback step; it gates the whole delegation tier.

### FF-013 — switchboard token budgets make the delegation tier unusable for real slices

Across all 15 routing profiles the largest input budget is 6000 tokens (`remote-reasoning`); most
are 3500. The largest output budget is 2048 (`remote-default`, `local-coding`). The default
profile allows 1500 in and 768 out.

This project's implementation slices are seed modules containing hundreds of species records,
which cannot be emitted inside 2048 output tokens. The cheap tier can only produce very small
artifacts: one check script, one config file, one test file.

Suggested fix: raise output budgets for implementation profiles, or state explicitly that large
generated data is a pipeline job rather than an agent job, and have the orchestrator decompose
to sub-2048-token artifacts.

### FF-017 — collective runs have no progress reporting and extreme latency

**Corrected after further evidence. An earlier draft of this report said runs terminate silently.
That was wrong and is retracted.**

What actually happens:
```
subprocess.TimeoutExpired: Command '[.../aq-collective ...]' timed out after 900 seconds
```
Run 1 was killed by the *caller's* 900-second timeout, not by itself. Run 2 was still alive and
issuing local model calls more than 14 minutes after launch.

The defect is not silent death. It is that a run emits no progress, exposes no job handle, and
gives the caller no way to distinguish "still working" from "hung". I drew the wrong conclusion
from that silence, which is itself the point: the observability gap actively produces false
diagnoses. Combined with the 30-second MCP wrapper timeout (FF-006), the only way to observe a
run is to tail its log file.

Suggested fix: emit per-phase progress, return a pollable job id, write partial phase output to
disk as produced.

### FF-026 — the executor demands file edits from analysis tasks and nudges against prose

Observed on the planning debate run:
```
no-action intervention: prose-only response with 0 edits made at call 4
 — injecting one-shot edit-forcing nudge instead of completing
```
The task was explicitly an architecture debate whose deliverable is reasoning: recommendations,
dissent, and a task decomposition. Prose is the correct and only sensible output. The executor
treats a response with zero file edits as a failure state and injects a nudge to force edits
rather than accepting the answer and completing.

Impact: this plausibly explains why the collective never returns a debate. The PRD and planning
phases are exactly the phases whose output is prose, and the executor is configured to reject
prose. It also risks the worse outcome of an agent inventing file edits to satisfy the nudge.

Suggested fix: classify tasks by expected artifact type; let planning, review and analysis tasks
complete on a prose deliverable without an edit-forcing intervention.


## Medium

### FF-008 — `harness_health` times out
`harness_health(phase=0)` returned `{"error": "timed out"}`. The first diagnostic an operator
reaches for is the one that fails, pushing them to ad-hoc HTTP probing.

### FF-009 — coordinator HTTP API auth is inconsistent and undocumented
`/status` is open. `/coordinator/status`, `/openapi.json` and `/docs` all return 401. With
`/openapi.json` closed there is no way to discover the API surface from the service itself.

### FF-010 — `coordinator_status` truncates at 4000 chars with no override
The response is dominated by a 58-entry skill registry, so `provider_health`, `runtimes` and
`domain_disclosure` are cut off. The tool takes no parameters, so truncation cannot be raised or
the payload filtered. `tooling_manifest` exposes `max_result_chars`; this should too.

### FF-011 — RAG reflection retries are reducing answer confidence
From `/status` → `rag_reflection_stats`: 130 retrievals triggered 154 retries (rate 1.18).
Average confidence moved 0.501 → 0.489, an improvement delta of **-0.012**. Retries currently
cost latency and tokens while making the answer slightly worse.

Suggested fix: gate retries on a predicted-improvement signal, or cap retries per retrieval.

### FF-015 — a collective run gives no way to tell working from hung
**Corrected; the earlier claim that the run dies on launcher detach is retracted.** The process
survived detachment and kept working. The real problem is observability: over two minutes elapsed
with no output at all, which led to a false conclusion. See FF-017.


### FF-012 — work performed before retrofit cannot be gate-protected
Commit `e63f932` was authored and committed before the factory was installed, so it carries no
independent review and no gate evidence, violating SHARED-RULES rules 9 and 10. Nothing can
retroactively bring it under the gate. This is the concrete argument for installing the factory
as the **first** action in a repo. Recommend the retrofit warn when the target repo already has
commits that predate gate installation.

## Low

### FF-014 — switchboard `/v1/models` times out, `/status` absent
`/health` responds with full routing detail, `/status` returns 404, `/v1/models` times out rather
than returning or refusing. An OpenAI-compatible client pointed here would hang on model discovery.

## Delegation phase findings

A real bounded slice was delegated to the one working lane (codex) to configure the gate checks.
It succeeded on the second attempt. These findings come from that exercise.

### FF-020 — bounded-slice contract contradicts the mandatory pulse-log rule
Rule 1 says edit only the named surfaces. Rule 5 says record every write in
`.agent/collaboration/PULSE.log`. A slice whose permitted-file list omits PULSE.log makes the two
rules mutually exclusive. The implementer hit this and said so:

> "I will not update the collaboration logs because they are outside the user's explicit
> permitted-file list, which takes precedence over the shared rule's logging requirement."

It then completed the slice with no pulse entry. The audit trail survived only because the
orchestrator noticed and wrote it by hand. This is a contract bug, not an agent error. The agent
reasoned correctly and told us why.

Suggested fix: exempt collaboration and memory artifacts from permitted-file restrictions, or
require every slice brief to include them.

### FF-021 — delegated agents run read-only by default, so delegation silently produces nothing
`codex exec` defaults to a read-only sandbox. The first delegation consumed **39,482 tokens**,
produced a correct plan, then died at write time:
```
apply_patch verification failed: invalid patch: multiple operations target .factory/repo-structure.conf
patch rejected: writing is blocked by read-only sandbox; rejected by user approval settings
```
Nothing changed. Re-running the identical brief with `-s workspace-write` succeeded and cost a
further **47,823 tokens**. A delegation harness that does not set sandbox mode burns a full
slice's tokens to produce zero files.

Suggested fix: have the delegation wrapper set the sandbox policy explicitly and fail fast if the
lane cannot write.

### FF-022 — the lean-ctx PreToolUse hook blocks delegated agents mid-task
```
Command blocked by PreToolUse hook: Command should run via lean-ctx for compact output.
Do not retry the original command.
```
The hook is configured for the primary session but applies to every spawned lane. The delegated
agent lost a tool call and had to rediscover an approved invocation. It recovered, but the
interception costs tokens and could derail a weaker lane.

Suggested fix: scope the hook to the interactive session, or teach delegated lanes the approved
invocation up front.

### FF-024 — background invocation of `codex exec` hangs on stdin
`codex exec "<prompt>"` works in the foreground. The identical command as a background job printed
only `Reading additional input from stdin...` and exited 144 having done nothing, both with the
prompt as an argument and piped from a file. An orchestrator dispatching slices as background
jobs gets silent no-ops.

### FF-023 — codex `apply_patch` rejects multi-hunk edits to one file
`invalid patch: multiple operations target .factory/repo-structure.conf`. Worth knowing when
writing slice briefs that need several edits to one file.

### FF-019 — `.agent/proposals/proposals.json` appears without provenance
This file materialized in the working tree with no action by any lane in this session. Some
background harness process writes into the consumer repo's `.agent/` tree outside the retrofit.
Unattributed writes into a gated repo undermine the review contract, because a reviewer cannot
tell who authored a change.

## Delegation outcome: it does work, once configured

Worth stating plainly, because most of this report is failures. With `-s workspace-write` set and
a precise brief, the delegated lane did good work unsupervised:

- Rewrote `repo-structure.conf` for the real repo without restructuring anything
- Wrote a genuine 5-test invariant suite over all 770 catalog records
- Correctly marked the safety test `@unittest.expectedFailure` with a comment that it becomes a
  hard gate in Phase 05, rather than weakening the assertion to make it pass
- Built a working grep-based secret scanner with correct exit semantics, having been told gitleaks
  was unavailable
- Added exactly the two package.json scripts asked for and touched nothing else
- Gate went from `passed=2 warned=2 failed=4` to `passed=6 warned=2 failed=0`

The orchestrator reviewed the staged patch as non-author and recorded PASS bound to
sha256 `2a7b223f6e83e0bd1f3b47afc649e67627f952617aec47e9a42894516358c4d1`.

The lesson is that the *agent* tier is capable. What is missing is the plumbing around it:
lifecycle state, lane auth, sandbox defaults, and honest validation scores.

### FF-025 — the independent-review check verifies git identity, not agent independence
**Location:** `.factory/gate-retrofit-hooks/commit-msg`, `reviewer_is_independent()`

 The hook enforces independence by comparing the `Reviewed-by:` email against the git author email. Every agent lane in this setup commits under the same human git identity, so the author email never reflects which agent actually wrote the code. The check is satisfied by putting any different email in the trailer, and it would equally reject a genuine two-agent review if both lanes shared a configured git identity. It measures the wrong thing.

**What it does do well:** `Reviewed-subject-sha256` is bound to `git diff --cached --binary --full-index --no-ext-diff --`, so a review cannot be reused across a modified patch. That half is solid.

**Next action:** record the implementing lane explicitly, for example an `Implemented-by:` trailer written by the delegation wrapper, and compare lanes rather than git emails.
### FF-027 — the local lane stalls and silently degrades the request to 512 tokens

```
LLM call 5 failed ('LLM no-progress timeout: server silent for >120s
 (first_token_timeout=120, chunk_timeout=120; context may be too large...)'),
 retrying with 512 tokens
```
The local model went silent for over two minutes and the executor's recovery is to retry with a
512-token output budget. A planning or PRD deliverable cannot be produced in 512 tokens, so the
retry cannot succeed at the original task even if the call returns.

This compounds FF-013. Between a 2048-token ceiling on the best profile and a degradation path
that drops to 512, the local lane cannot carry a deliverable of realistic size. The executor's own
diagnostic names the likely cause, "context may be too large", pointing at the same budget problem.

Suggested fix: on a no-progress timeout, split the task or fail it explicitly. Silently shrinking
the output budget converts a slow success into a guaranteed inadequate answer.

## What worked

Worth preserving, so a fix does not regress it:

- `aqd workflows retrofit` preview/confirm digest flow is sound. The preview listed all 28 writes,
  reported `safe_to_install`, backed up `.git-config`, and preserved the existing `CLAUDE.md`.
- Existing git hooks were detected and routed before the factory hooks rather than clobbered
  (`.git/hooks -> .githooks wrappers`, `HOOK_PATH_VERIFIED`).
- `scripts/governance/gate-runner` is genuinely good: clear per-check state, actionable failure
  messages, correct exit behaviour, and it correctly refused to declare itself active while
  checks were unconfigured (`ACTIVATION_BLOCKED`). It found the real build command and passed it.
- Stack auto-detection worked when `stack` was omitted.
- `get_hints` surfaced a real runtime defect (FF-007) that was otherwise invisible.
- The role contracts (SHARED-RULES, WORKFLOW-CANON) are coherent and enforceable as written,
  with the one exception recorded as FF-020.
- **The pre-commit hook correctly blocked a commit** while the gate reported `failed=4`. The
  enforcement path works end to end: hook routing, gate run, block, and a clean pass after the
  checks were configured.
- The delegated implementation lane produced good work once given write access (see above).

## Recommended goals

1. **Implement or remove the lifecycle stubs (FF-000).** Nothing else in the factory means much
   while the spine returns placeholders that look like success. Highest priority.
2. **Make lane auth a first-class health check (FF-018).** A task should not be assignable to a
   lane that cannot authenticate. Surface per-lane auth in `harness_health`.
3. **Fix the collective or stop calling it one (FF-016).** Either convene real lanes and compute
   real validation scores, or rename it and drop the metrics.
4. **Finish retrofit rendering (FF-001, FF-002, FF-005).** A retrofit should leave a repo whose
   gate can activate, whose contract files contain no template tokens, and whose mandated
   directories exist. Today it leaves all three broken.
5. **Close the MCP/CLI capability gap (FF-003, FF-004, FF-006).** Several MCP tools cannot do
   what their CLI equivalents do, or reject their own documented input types. An agent working
   through MCP hits a wall the CLI does not have.
6. **Right-size the delegation tier (FF-013, FF-007).** Decide whether cheap agents produce code
   or only small artifacts, then set budgets to match and fix worktree handback.
