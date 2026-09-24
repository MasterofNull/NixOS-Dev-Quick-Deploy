---
doc_type: prd
id: factory-gate-templates
title: Factory Gate/Check Template Reproduction — greenfield + brownfield injection
status: active
owner: hyperd
priority: P0-critical
phase: "Agentic Collaborative Software Factory — output apparatus"
evidence_required: a new (greenfield) and an existing (brownfield) target repo, after the factory starts on it, carry a WORKING gate bundle (git hooks fire, a tier0-style gate runs + blocks, a projected PM tracker, review-before-commit trunk protection, agent scaffolding) adapted to the target's stack; the gates are enforced + validated by EVERY agent lane (Claude, Codex, local, Antigravity), not one; the gate policy is RISK-TIERED (security/vulnerability/stability/core-piece changes require higher review depth, validation rigor, and locking); the bundle self-tests; installs are non-destructive on brownfield; aq-qa phase 0 + tier0 pass on THIS repo.
---

# Factory Gate/Check Template Reproduction PRD

## Problem
A true software factory stamps its own quality apparatus into everything it produces. Ours does not yet.
Our gates/checks/discipline — the tier0 validation gate + `tier0.d/` extensions, `.githooks` (commit-msg
trunk protection binding review-subject-sha256, pre-commit), `repo-structure-lint`, the PM-tracker standard
(editorial `tracker.json` → projected gantt/kanban, gated), the review-before-commit + role-contract
discipline, the QA-phase framework, and the canonical behavioral-rules scaffolding (CLAUDE.md/AGENTS.md) —
live ONLY in THIS repo. The greenfield (`project-init`) and brownfield workflows are thin PLANNING flows
(produce a PRD + slice plans) and do not install any of it; `bootstrap_agent_project` (mcp-bridge-hybrid)
copies agent-instruction scaffolding (CLAUDE.md/commands/.agent) but NOT the enforcement gates. So a project
the factory creates or adopts gets no reproducible checks, gates, or PM discipline — the factory's core value
does not propagate to its output.

## Goal
Codify the gate/check apparatus as a reproducible, **stack-adaptable template bundle**, and wire the
greenfield + brownfield workflows to INSTALL + ACTIVATE it into every project the factory starts working on —
so new and existing projects gain working checks, gates, trunk-protection, PM projection, and agent
scaffolding, adapted to their language/stack. Two cross-cutting requirements govern the whole bundle
(owner-directed): the gates are **enforced + validated by ALL agent lanes, not just one**; and the gate
policy is **risk-tiered** — core/security/vulnerability/stability-critical changes get higher review depth,
validation rigor, locking, and workflow controls than routine ones. This applies to THIS factory now AND to
every reproduced project.

## Cross-cutting requirement A — all-agent enforcement (not just Claude)
The gates must bind every lane (Claude, Codex, local/Qwen, Antigravity/Gemini) identically:
- **Lane-independent enforcement:** every authorized lane uses the same mandatory git hooks
  (`commit-msg`/`pre-commit`/`pre-push`) fire for any committer regardless of which agent produced the work;
  the gate-runner is invoked by the shared commit flow, not a per-agent convenience. An agent cannot commit
  to a protected branch through the authorized flow without satisfying trunk protection + tier0.
  Hooks are cooperative local enforcement, not a tamper-resistant security boundary against
  an agent running as the same OS user: that user can disable hooks or forge trailer text.
  FT-7 must distinguish hook-path parity from trusted reviewer attestation and add the
  required CI/protected-branch or broker backstop before claiming unbypassable enforcement.
- **Instruction parity (Rule 16):** the review/validation/risk-tier discipline is written into EVERY agent
  instruction file (CLAUDE.md, `.agent/CODEX.md`, `.agent/LOCAL-AGENT.md`, `.agent/GEMINI.md`,
  `.agent/WORKFLOW-CANON.md`) from the same templated source — never one lane in isolation.
- **Cross-lane validation:** a check proves every agent lane actually honors the gates (parity-matrix
  coverage + a probe that a commit from any lane hits the same hooks/tier0), so "all agents enforce it" is
  measured, not assumed. The reproduced bundle carries the same all-agent guarantee for the target's agents.

## Cross-cutting requirement B — risk-tiered gates (core/security get more)
A change/plan/PRD is classified by risk, and required rigor scales with the tier. Compose on the existing
risk machinery (`scripts/automation/prsi-orchestrator.py` `_risk()` low/medium/high; the credential
`R0..R3`-style classes; `config/prsi/high-risk-approval-rubric.json`) — do not invent a parallel scheme.
- **Signals → tier:** security surface (auth, crypto, secrets, capability/lease/gate/enforcement code),
  vulnerability exposure, stability/blast-radius (core kernel/spine, shared modules, migrations),
  network/egress, irreversibility. Touching a "core piece" (Foundation kernel, lease/gate authority, the
  gate framework itself, schema/migrations) forces the top tier.
- **Tier → gate policy (escalating):** LOW → single independent review + tier0. MEDIUM → independent review +
  broader validation. HIGH/CORE → multiple independent reviewers (distinct lanes), deeper validation
  (adversarial/hermetic proof), **locking** (design freeze + hash-bound single-use activation, the C-series
  discipline), and stronger workflow controls (staged subject-hash binding, owner-confirm on live enforcement
  activation even under a standing gate-lift). The tier is recorded on the change + enforced by the gate,
  never self-lowered (anti-gaming, Rule 19).
- **Where it plugs in:** the gate-runner reads the change's classified tier and selects the required
  reviewer count/independence, validation set, and lock/freeze requirement; trunk protection escalates its
  Reviewed-by requirements by tier. Reproduced into target projects with a stack-appropriate default map.

## Design
### The gate bundle (what gets codified — the PORTABLE framework, not this repo's specifics)
Separate universal FRAMEWORK from repo-specific content:
- **Universal (templated verbatim, lightly parameterized):** a gate-runner (tier0-style: discover + run a
  `checks.d/` set, WARN vs HARD classes, `--pre-commit`/`--pre-deploy` modes, live-vs-freshness corollary);
  `.githooks/commit-msg` trunk protection (terminal Review-Disposition + Reviewed-subject-sha256 binding the
  staged patch + non-author Reviewed-by) + `pre-commit` runner; a repo-structure lint; the PM-tracker
  standard (`tracker.json` schema + projector + `check-pm-tracker`); the canonical behavioral rules +
  role-contracts + review-before-commit + issue-logging/PULSE/RESUME scaffolding (CLAUDE.md/AGENTS.md
  templates with placeholders); a bundle self-test.
- **Stack-adaptive (chosen per target):** the concrete baseline checks — build/test/lint/secret-scan/format
  commands — resolved from the target's detected stack (Python/Node/Rust/Go/Nix/generic), plus a starter
  `checks.d/` set. The FRAMEWORK is universal; the CHECK CONTENT adapts.
- **Explicitly NOT copied:** this repo's NixOS modules, `aq-*` CLIs, ports, model config, domain PRDs.

### Greenfield (`project-init` / `bootstrap_agent_project`)
After the PRD + plans step, install the bundle into the new project: `git init` if needed, install
`.githooks` + `core.hooksPath`, drop the gate-runner + a stack-appropriate `checks.d/` baseline, the
PM-tracker standard, and the parameterized agent scaffolding; run the bundle self-test so the gates are
proven live (Rule 15 — installed ≠ dormant), not just copied.

### Brownfield (`brownfield` / `retrofit_workflow`)
Retrofit into an existing repo NON-DESTRUCTIVELY: detect stack + existing config; install hooks without
clobbering existing ones (merge/append, back up via Rule-12 archive); add the gate-runner + adapt checks to
the existing layout; add the tracker standard; never overwrite the project's own CI/config silently; report
a diff-preview + require confirmation for anything it would replace.

### Factory-start precondition
When the collaborative factory begins working on a project (greenfield OR brownfield), a bootstrap step
ensures the bundle is present + passing before slice work proceeds — the gates guard the factory's own work
on that project from turn one.

## Slices (each: independent non-author review, tier0 gate, trunk envelope; PM tracker)
- **FT-1 — codify the portable gate bundle:** extract the universal framework into a versioned template dir
  (e.g. `templates/factory-gate-bundle/`) with placeholders + a manifest listing what installs where + a
  self-test. No behavior change to THIS repo (source-of-truth stays; the template is a derived, tested copy).
- **FT-2 — stack adapters:** stack-detection + per-stack check profiles (Python/Node/Rust/Go/Nix/generic)
  resolving concrete build/test/lint/secret-scan commands into the gate-runner.
- **FT-3 — greenfield injection:** extend `project-init`/`bootstrap_agent_project` to install + self-test the
  bundle into a new project; add an end-to-end proof (scaffold a throwaway repo, confirm hooks fire + gate
  blocks a bad commit).
- **FT-4 — brownfield retrofit:** non-destructive install into an existing repo (detect, merge-not-clobber,
  confirm-before-replace, Rule-12 backups); end-to-end proof against a fixture existing repo.
- **FT-5 — factory-start precondition + docs:** wire the "ensure gates present+passing" step into the
  factory's project-start path; parity-update the agent instruction files (Rule 16); ACTIVATION-AUDIT.
- **FT-6 — risk-tiered gate policy (cross-cutting B):** a risk classifier (compose on PRSI `_risk()` +
  `high-risk-approval-rubric.json`) tags each change/plan/PRD by security/vulnerability/stability/core-piece
  signals; a tier→policy map the gate-runner + trunk-protection consult to escalate reviewer count/
  independence, validation set, and locking (freeze + hash-bound activation) for HIGH/CORE. Recorded on the
  change, never self-lowered (anti-gaming). Applied to THIS repo first, then templated into the bundle. This
  is foundational — FT-1's bundle carries the tier hooks; FT-6 fills the classifier + policy map.
- **FT-7 — all-agent enforcement + cross-lane validation (cross-cutting A):** ensure the gates bind every
  lane (lane-independent hooks + gate-runner in the shared commit flow), the discipline is parity-written
  into all agent instruction files from one templated source, and a check PROVES each lane hits the same
  hooks/tier0 (not assumed). Applied to THIS repo first, then reproduced for the target's agent set.

## Constraints
Compose on the existing `bootstrap_agent_project` scaffold (Rule 20, don't rebuild). Brownfield installs are
non-destructive + confirm-gated. Installed gates must RUN in the target (Rule 15 — prove with a self-test /
bad-commit-blocked probe, not a dormant copy). The template's trunk-protection + tracker discipline mirror
this repo's SSOTs; a change to a gate here should have a clear path to re-derive the template (avoid drift —
FT-1 records the derivation source so the template can be refreshed, not hand-maintained). Ports/paths/stack
commands parameterized, never hardcoded. This repo remains the SSOT for the gates; the bundle is a derived,
version-stamped, self-tested reproduction.

## Authorized implementation continuation — factory capability replication

Owner authorization: 2026-09-18. Module, API, branch and test names describe their
function. Consumer project names belong only in provenance/evidence references.
This continuation extends this PRD and FT dependencies; it does not establish a
second policy engine or a competing roadmap.

The intended product is a portable project configuration connected to a shared,
versioned factory engine. Gate installation is only one capability. Projects
must have scoped access to delegation, durable lifecycle/checkpoints, memory,
issue capture, operational visibility, independent review, CI and explicitly
configured deployment. Hardware, secrets, accounts, ports and user project data
are not copied blindly from the source harness.

Implementation order (owner-approved):

1. Deployment contract corrections: adapt legitimate consumer layout, render
   unconfigured command states truthfully, preview and seed required collaboration
   paths, and expose confirmation/stack parity through MCP. Preserve existing
   confirmation, backups, layout controls and fail-closed required checks.
2. FT-5 start readiness: source/config/hash-bound executable readiness and visible
   blockers before target-safe project/slice dispatch. Hook routing alone is not
   passing target execution evidence.
3. Shared-engine project integration: reuse existing registry, target resolution,
   capability leases, workflow/memory/event services and dashboard APIs. Bind
   project identity/root/capabilities explicitly; surface unavailable transports
   before assignment. No duplicate per-project coordinator or memory authority.
4. Lifecycle/collective correctness: converge on the existing durable workflow
   authority, retain original objectives and analysis versus coding intent,
   require actual contributor receipts, aggregate failed required phases, and
   persist progress/outcomes across timeout, detach and suspend/resume.
5. FT-6/7 and portable CI/CD: risk-appropriate independent review and trusted
   backstops, tested source templates, separately verified GitHub protection and
   authorized deployment. Local hooks do not establish remote enforcement.
6. Consumer acceptance: a real bounded feature passes plan, implementation,
   independent review, commit, CI, configured deploy and health checks; also prove
   unavailable-lane handling, failed-task truthfulness and interruption recovery.
7. Guided/self-improvement closure: anomaly -> evidence -> bounded proposal ->
   authorized candidate -> independent acceptance -> canonical engine/template
   update -> consumer regression -> measured revalidation. Learning does not
   grant a candidate authority to weaken its own gates or silently deploy itself.

Use `.agents/plans/factory-gate-templates/DEPLOYMENT-CONTRACT-IMPLEMENTATION.md`
for the first executable boundary. Freeze each small subject, route a non-author
review, and record implementation, validation, acceptance and activation as
separate states. Findings requiring judgment are queued for their next slice;
security, data-loss and authority defects block activation.

Run-3 release correction (2026-09-19): a compatible upgrade is not safe merely
because the factory recognizes its prior receipt. Before stages 3–7 activate,
upgrade must preserve locally configured managed checks/layout policy, preview and
back up every managed path it replaces, and prove recovery without relying on Git.
Ambiguous ownership fails closed. Evidence files must not make a clean consumer
dirty. The unchanged placeholder intake/status spine is stage-4's first authority
consolidation slice; see
`.agents/plans/factory-gate-templates/LIFECYCLE-AUTHORITY-CONSOLIDATION.md`.
