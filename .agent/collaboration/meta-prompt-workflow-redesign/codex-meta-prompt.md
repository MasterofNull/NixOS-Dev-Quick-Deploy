---
doc_type: collaboration-brief
title: Codex meta-prompt — proof-obligation workflow redesign
status: draft
owner: hyperd
date: 2026-08-21
lane: independent-rigor-verification
---

# Codex independent meta-prompt: make “done” a verified state

Redesign this harness's workflows, loops, roles, and governance at the root. Make ordinary work materially simpler, but make system-critical, security-adjacent, failure-prone, and validation-infrastructure work substantially harder to misclassify or falsely declare complete.

Do not optimize for fewer documents in isolation. Optimize for fewer defect escapes, fewer silent scope changes, cheaper owner steering, and a short path from a claim to the evidence that proves it. Treat every narrative status as untrusted until a machine-checkable record and an independent reviewer bind it to an exact subject.

## Start from the actual failure, not the ceremony story

The triggering batch did not merely omit PRD and communication ceremony. It shipped as “done” after tests and tier0, yet independent review found **12 defects, six HIGH-or-worse**:

- two direct security-boundary failures: shell metacharacters reached `shell=True`, and `write_region` bypassed the validated workspace write boundary;
- replay keys collided across behaviorally distinct requests, so replay could certify the wrong behavior;
- strict replay could silently fall through to live network calls;
- an agent loop had no hard termination bound despite exposing a `max_tool_calls` setting;
- generated GBNF still admitted malformed JSON and did not faithfully implement schemas;
- command-artifact cleanup corrupted legitimate commands;
- retries silently changed inference behavior by dropping `task_type`;
- line-range writes lacked stale-context protection and atomicity;
- the new regression suites were not discovered by the normal gate;
- cassette output lacked adequate content/path protection; and
- commit-scope/trailer rules were violated.

Some focused tests passed because they tested the intended happy path. Tier0 passed because the relevant new tests were not registered in it. One test even encoded a replay-key collision as desired behavior. Therefore, **“test-covered,” “single-file,” “env-gated,” and “reversible” are not evidence of low risk**. They describe implementation shape or recovery convenience, not the authority changed or the failure modes introduced.

## Root-cause hypothesis to test

The root cause is a **claim-to-proof gap** reinforced by conflicted roles:

1. the producing loop could choose its own risk label, choose the tests that defined success, and announce completion;
2. gates checked that commands passed, not that the commands exercised the changed invariants or were part of the normal gate;
3. risk was inferred from visible size and path names instead of changed authority, boundary semantics, dependency impact, and failure history;
4. “done” was a narrative state, not an exact-hash acceptance state; and
5. duplicated logs and ceremonies created activity evidence without guaranteeing correctness evidence.

Uniform-heavy process may encourage skipping, as Claude argues, but that is not sufficient to explain this batch. A lighter Tier 2 would have accelerated several of these escapes because many were bounded, single-file, env-controlled, and nominally test-covered. Redesign the verification contract before relaxing ceremony.

## Reject Claude's proposed tier boundaries

Explicitly challenge these premises in Claude's proposal:

- **Reversibility is not a risk discount.** A kill switch can limit recovery time after detection; it does not prevent secret exposure, out-of-workspace writes, shell execution, corrupted training evidence, or false replay certification before detection.
- **Small diffs are not low-risk diffs.** A one-line parser, auth, sandbox, retry, replay, grammar, or gate change can alter the system's effective authority.
- **“Test-covered” is circular unless test adequacy and gate discovery are independently verified.** A passing test can encode the bug, omit negative cases, or never run in the required gate.
- **Path allowlists alone are gameable and incomplete.** New helpers, call-site changes, configuration defaults, test-discovery edits, and indirection can change a critical boundary outside a familiar directory.
- **Tier 0 is drawn too narrowly.** It must include validation/replay systems, agent termination and budgets, parsers/grammars, tool execution and filesystem mutation, retry/fallback semantics, model-request identity, test/gate infrastructure, and any code that can turn fail-closed behavior into fail-open behavior.
- **A tier declaration is necessary but not the universal minimum gate.** A self-declared label plus passing tests would not have caught this batch. Any executable behavior change needs independent semantic acceptance before “done.”

## Replace ceremony tiers with cumulative proof obligations

Design a small number of cumulative lanes. The highest triggered obligation wins; uncertainty escalates. Names may change, but preserve these boundaries:

### Lane A — clerical, no semantic effect

Eligible only for comments, prose, spelling, formatting, generated snapshots with verified provenance, or metadata that cannot affect execution, policy, packaging, test selection, routing, activation, or operator decisions.

Minimum gate: machine-confirm no semantic surface changed; validate formatting/links/schema as applicable; publish one owner-visible change record. If semantic neutrality cannot be proved automatically, use Lane B.

### Lane B — bounded behavioral change

This is the default for executable code, tests, configuration, prompts, model parameters, scripts, and operational documentation. “Single-file,” “one-line,” “env-gated,” and “easy to revert” remain Lane B, not Lane A.

Minimum gate: frozen change contract; focused positive and negative tests; proof that those tests are discovered by the normal gate; full applicable gate; independent semantic review of the exact diff and evidence; exact subject hash; no completion state until an independent `PASS` binds that hash.

### Lane C — critical or failure-prone boundary

Automatically triggered by changed authority or high-consequence invariants, including security/auth/secrets; shell/process execution; filesystem mutation or path resolution; sandbox/AppArmor/network boundaries; fail-open/fail-closed transitions; parsers/grammars/serialization; replay, caching, identity, and evaluation truth; retries/fallbacks; unbounded loops and resource budgets; activation/deployment; data loss or irreversible state; gate/test-discovery/reviewer machinery; known recurring defect classes; or broad/shared runtime dependencies.

Minimum gate: Lane B plus a written threat/failure model; explicit invariants and counterexamples; adversarial tests derived independently from the implementation; live or faithful replay proof where appropriate; two distinct review functions, at least one independent of the producing loop and one owning verification; owner authorization before activation or exposure. A reviewer who changes the subject invalidates prior acceptance and returns it to implementation.

Do not make “multi-agent consensus” the goal. Two agents repeating the same assumptions are not stronger evidence. Require **independent challenge and reproduced evidence**, with identities and exact reviewed subject recorded.

## Make classification un-gameable

Specify an implementable classifier with these properties:

1. **Classify twice:** provisionally from declared intent before work, then authoritatively from the final diff, dependency/consumer map, runtime authority changes, and validation-surface changes.
2. **Use maximum-risk composition:** a batch inherits the highest obligation triggered by any file, call path, capability, or invariant. Splitting commits must not lower the obligation for coupled changes.
3. **Detect semantics, not only paths:** combine protected paths with imports/callers, sensitive API use (`shell=True`, subprocess, filesystem writes, auth, network, secret reads), changed defaults, exception/fallback behavior, loop bounds, schema/parser logic, and test-discovery/gate configuration.
4. **Treat new or unknown surfaces conservatively:** a new helper inherits the highest risk of its consumers. Unknown classification escalates; it never defaults down.
5. **Forbid producer downgrades:** the implementer may raise risk but may not lower an automatically triggered lane. Downward overrides require an independent reviewer or owner, a reason code, and a permanent audit record.
6. **Protect the protector:** edits to the classifier, its rules, test registration, validation gates, evidence store, review policy, or completion-state machinery are automatically Lane C.
7. **Reclassify on scope drift:** undeclared files, new dependencies, changed acceptance criteria, or post-review edits invalidate the prior declaration and acceptance hash.
8. **Measure escapes:** feed independently found post-acceptance defects back into trigger rules and focused regression obligations. Repeated defect families become Lane C automatically.

Produce concrete pseudocode or a schema for this classifier and show how it classifies every defect family from the 12-finding batch. If any of those changes can land in the lightest lane, the design fails.

## Define one completion protocol

Replace loose status prose with a state machine such as:

`DECLARED → CLASSIFIED → IMPLEMENTED → VERIFIED → ACCEPTED → ACTIVATED`

Require evidence for each transition. At minimum, the record must contain scope, computed lane and triggers, changed capabilities/invariants, acceptance criteria, exact subject hash, exact validation commands and results, test-discovery proof, reviewer identity and independence, verdict, activation authority, exclusions, and unresolved risks.

“Tests pass,” “tier0 pass,” “reviewed,” “committed,” and “deployed” are facts, not synonyms for `ACCEPTED`. A producing lane cannot grant its own terminal acceptance. A changed hash cannot inherit a prior `PASS`. A test that is not invoked by the declared normal gate cannot satisfy the gate.

## Simplify aggressively, but delete the right things

Propose deletion or consolidation of:

- narrative PRD/PLAN ceremony for Lane A and routine Lane B work; replace it with one short structured change contract;
- overlapping `PULSE`, `RESUME`, steps, ledger, catch-up, and handoff facts; write one append-only event stream and derive human views from it;
- permanent model-to-role assignments and ornate role taxonomies; retain only four separable functions: declare/classify, implement, verify/accept, and authorize activation;
- rules that have no executable check, review question, or explicit owner decision; either encode them, attach them to a gate, or delete them;
- duplicated dashboards and per-subsystem ornamental telemetry.

Do **not** delete independent review, exact-subject binding, regression-test discovery, failure-mode analysis, or owner activation authority in the name of speed. Simplification must remove duplicated representation, not remove the only control that detects semantic defects.

Keep observability compact and decision-oriented: coverage of required gates, bypass/downgrade attempts, review yield, escaped-defect rate by lane and subsystem, stale/unaccepted work, activation state, and cycle time. If a metric does not change a routing, review, owner, or remediation decision, challenge its existence.

## Keep the owner in the loop cheaply

Design one owner-facing cycle feed generated from the canonical event record. Each active slice should fit on one line or expandable card:

`objective | computed lane + triggers | scope/capability change | producer | verifier | current state | next irreversible action | blockers/exclusions`

Notify the owner immediately only for Lane C declaration, automatic escalation, scope drift, attempted downgrade/bypass, failed independent review, and activation authorization. Lane A/B updates remain visible but non-blocking unless the owner vetoes or raises the lane. The owner should not need to reconcile PULSE, RESUME, PRDs, catch-up queues, commits, and chat transcripts to learn what is happening.

## Required redesign output

Return a concrete, deletion-oriented architecture proposal containing:

1. the final lane/proof-obligation matrix and precise automatic triggers;
2. the universal change-record schema and completion state machine;
3. exact independent-review and exact-hash invalidation rules;
4. test-adequacy and normal-gate-discovery requirements;
5. the owner feed and notification policy;
6. roles/artifacts/rules/telemetry to delete, merge, or retain;
7. enforcement points in the harness, with fail-closed behavior and migration order;
8. a walkthrough of all 12 observed defect classes showing which trigger and proof would have caught each one;
9. explicit tradeoffs: added latency, false-positive escalation, reviewer availability, and safe degraded behavior; and
10. measurable acceptance criteria for the redesign, including zero silent downgrades, zero `ACCEPTED` transitions without an independent exact-hash `PASS`, 100% required-test discovery, and tracked escaped-defect rate.

Prefer a small executable kernel over another long policy document. The redesign succeeds only if the fast path is genuinely cheap for non-semantic work, the middle path always includes independent semantic proof for executable changes, and critical boundaries cannot be waved down by calling them small, reversible, env-gated, or tested.
