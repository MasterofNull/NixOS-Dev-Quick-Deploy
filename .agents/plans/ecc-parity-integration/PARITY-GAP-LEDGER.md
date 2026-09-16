# ECC → AQ-OS parity and gap ledger

Status: Gate A plan-ready; implementation outcomes remain unactivated  
Upstream: `affaan-m/ECC@8321021c54d670126ce3b2969d5deb880b4b0c2a`  
Existing source: Antigravity clean clone recorded in `MULTIPASS-REVIEW-PLAN.md`

This ledger separates upstream presence, source-verified behavior, local outcome
parity, and activation eligibility. A matching filename, prompt, report, or file
count is not feature parity. Upstream source remains untrusted reference data.

## Coverage baseline

The pin contains 3,716 tracked artifacts: 68 root agent definitions, 292 skill
roots, 94 root command definitions, 6 hook artifacts, 289 scripts, 320 tests and
28 `.github` artifacts. These are inventory counts, not 799 independent features
and not proof that every artifact has been semantically reviewed. Coverage states
are `cataloged`, `partial`, `full`, or `adversarially-verified`.

Antigravity's ten-pass report is a useful hypothesis index. Its recommendations
remain advisory until checked against pinned source, tests, local implementation,
permissions and measured behavior.

## Corrected outcome matrix

| Domain | Source-backed observation | AQ-OS outcome today | Verdict | Queue disposition |
|---|---|---|---|---|
| OS/runtime isolation | ECC is primarily Node/Markdown/Rust application tooling with dynamic child-process surfaces. | Declarative NixOS, systemd, AppArmor and capability intake provide stronger host lifecycle controls. | stronger-local | Do not import a competing runtime authority. Extract only bounded application patterns. |
| Agents/personas | 68 prompt definitions exist; selected language/build checklists are real, but representative bodies still need semantic sampling. | AQ-OS has 4 authority roles, 4 orthogonal agent types, 16 domain instruction files and dynamic lane routing. | partial / architecture-different | Admit demand-backed checklists as lazy skills/profiles, not 25 always-present personas. |
| Skills | 292 skill roots exist. Exact-name overlap is not semantic evidence; committed AQ-OS has 66 project skill manifests plus externally installed skills. | AQ-OS already covers workflow, security, systems, testing, context, collaboration and specialized domains under different names. | unknown-by-name; partial-by-outcome | Cluster by outcome, deduplicate, then intake only gaps with tests and owners. Never bulk-copy 292 skills. |
| Commands and session state | 94 command files exist. Checkpoint/resume/quality/security commands combine prompts with filesystem, Git, formatter or package-runner authority. | AQ-OS has `aq-session-start`, atomic resume/pulse/handoff, tier0 and capability intake. | mostly stronger-local; selected partials | Consider scoped resume ranking and check-only formatter adapters. Reject destructive checkpoint and unpinned `npx` behavior. |
| Lifecycle hooks | Seven event classes are configured through dynamic Node bootstraps, inherited environment/cwd and mixed fail-open/fail-closed behavior. The formatting stop hook is explicitly nonblocking and narrower than reported. | AQ-OS already has in-process deny-closed capability leases, executor guards, tool safety/rate/confirmation controls and Git hooks, but lacks one normalized cross-provider event contract. | partial | Design a typed, budgeted adapter around existing admission gates; no direct hook activation. |
| Memory/learning | The vault has bounded/no-follow/secret-refusing reads and completeness diagnostics. Its autonomous observer can write/promote/prune agent artifacts without confirmation. | Three-tier memory, AIDB/RAG, trust labels, budget registry and governed self-improvement already exist. | stronger-local authority; partial diagnostics | Add bounded per-record recall completeness visibility natively. Reject autonomous promotion lifecycle. |
| Eval/verification | ECC has strict envelopes, canaries and hash-chained/fsynced receipts, but deliberately refuses candidate execution without an OS containment backend. | AQ-OS has real bwrap/firejail execution support plus static candidate evaluation, QA, dogfood and independent review. | complementary partials | Build one hermetic protocol binding artifact digest, containment config, actual outcome and reviewed promotion. Do not count ledger integrity as behavior execution. |
| Orchestration/worktrees | ECC exposes worktree/tmux orchestration and control-plane surfaces. | AQ-OS already has `WorkspaceManager` worktree lifecycle/conflict/merge support, coordinator, claims and drop zones; owner-selected collaboration remains shared-directory file/section claims. | partial operational hardening | Harden existing merge policy, Tier-0 integration and operator UX. Do not create a parallel `aq-worktree`. |
| Multi-harness projection | Session adapters normalize local state, while sync/install scripts back up then broadly write harness homes, configs, prompts, agents and hooks. | AQ-OS has guarded project installers/receipts but known provider projection drift. | partial; upstream mutation unsuitable | Compile provider projections from a canonical contract through AQ-OS's existing guarded installer authority. Do not import home-mutating sync scripts. |
| Security scanner | Commands reference external `ecc-agentshield`/`npx`, but the pinned ECC tree contains roadmap/examples rather than scanner implementation source. | Semgrep MCP, OSV, Trivy, Syft/Grype and security gates already exist under governed intake. | report claim unsupported; external capability approval-blocked | Do not claim or ingest an in-tree scanner. Compare separately pinned external candidate coverage only through a new intake if still needed. |
| Observability/UI | ECC has a static searchable capability dashboard plus operational surfaces mainly in `ecc2`. | AQ-OS already exposes discovery/shared-skill APIs and has a stronger operational dashboard policy. | partial UX | Bind existing APIs into a searchable catalog panel; do not create another discovery backend. |
| CI/CD | ECC CI pins major Actions by SHA, disables install lifecycle scripts, validates workflow security, tests packed artifacts and publishes with provenance/OIDC; repository protection remains unverified. | Local CI is substantial but has known nonblocking scans, mutable action refs and no proven GitHub protection/environment controls. | genuine local gap | Create portable opt-in CI and separately approval-gated CD templates with pinned actions, least privilege, provenance and rollback. |

## Security and supply-chain pass

The pinned tree is `a7489fb4da00fc7b4995df3a3c59c018d08a3807`.
The read-only pass covered package/locks/license/security, installer/update/hook
code, CI/release workflows and focused tests. Overall disposition remains
**disabled/reference-only**.

- `hooks/hooks.json` uses inline Node root discovery and inherited environment
  with handler timeouts up to five minutes. The global Git hook installer can
  overwrite `core.hooksPath` after copying a backup. These conflict with FT3/FT4's
  target-local, collision-refusing composition model.
- The installer contains useful concepts: explicit hook consent, plan/apply
  separation, symlink refusal, user-content preservation, settings locking and
  partial-state checkpoints. `auto-update.js`, however, executes the installed
  repository's installer with inherited environment and lacks a signed artifact
  boundary. Reuse concepts, not execution lifecycle or source.
- Root JavaScript direct dependencies are pinned and MIT-licensed at the root,
  with Yarn and npm locks. The Python subproject has minimum-range Anthropic and
  OpenAI dependencies without a Python lock, so provider, secret and mutable
  dependency surfaces are not SBOM-complete.
- Inspected tests substantiate hook consent, package-free planning, auto-update
  state/root checks, privileged-workflow/cache protections and lifecycle safety.
  They were not executed and do not establish whole-system security assurance.

## Memory, learning, eval and projection pass

- The ECC memory vault uses create-only mode-0700 Markdown records, no-follow
  and symlink checks, secret-pattern refusal and bounded scans (5,000 files /
  16 MiB). It explicitly reports malformed, skipped and truncated records, and
  refuses direct-ID results when the scan is incomplete. The transferable gap is
  operator-visible recall completeness, not another vault or MCP authority.
- `continuous-learning-v2` explicitly asks an agent to create/update instincts
  without confirmation and can prune/archive observations or promote generated
  skills, commands and agents. Cooldown locking is not authority control. This
  conflicts with AQ-OS intent locks, capability leases and independent review.
- ECC eval receipts provide strict schemas, secret canaries, canonical SHA-256
  chains, append locking/fsync and offline verification. Its gate permanently
  rejects candidate execution without verified OS containment. AQ-OS has actual
  bwrap/firejail support, but its candidate evaluator is also static. The native
  opportunity is to join containment execution with digest-bound evidence and a
  reviewed promotion decision.
- ECC session adapters and sync scripts are useful interoperability references,
  but their broad home-directory and configuration writes are not acceptable
  projection authority for AQ-OS.

## Orchestration, control-plane and UI pass

- ECC's control pane is a loopback HTTP server that can mutate work-item claims
  and spawn allowlisted commands with inherited environment unless read-only.
  Host/origin checks and timeouts are mitigations, not an authority model. Any
  AQ-OS UI must call its existing claim/task/coordinator SSOTs and must never add
  browser-to-spawn authority or a second mutable claim store.
- ECC's worktree/tmux tooling is a useful local launcher with dry-run planning,
  but execute mode shells out to Git/tmux and mutates workspace state. AQ-OS's
  measurable gap is only durable, dashboard-visible provision → claim → heartbeat
  → teardown/recovery proof around its existing `WorkspaceManager`.
- ECC loop/orchestration status and observability readiness are primarily local
  transcript, plan and structural checks. AQ-OS live Phase-0 QA is stronger. A
  useful native slice would correlate coordinator/workspace recovery state across
  one live QA integration check and the current dashboard.
- ECC's web dashboard is primarily a static repository catalog; its readiness
  dashboard combines repo/Git/GitHub assertions. AQ-OS should expose
  declared-versus-live adapter/MCP status with explicit `UNVERIFIED` entries,
  using its existing discovery and dashboard services.
- `ecc2` is a separate Rust operational plane whose source presence and release
  documentation do not prove deployed behavior. No AQ-OS gap is accepted without
  an isolated runtime comparison covering authentication, resource bounds,
  persistence/restart and QA/dashboard evidence.

## Confirmed high-value candidates

1. **Canonical multi-harness projection compiler** — one typed source contract,
   provider-specific outputs, drift detection, collision refusal, secret omission,
   preview/confirm and rollback. This addresses real local projection drift.
2. **Typed lifecycle event adapter** — normalized pre/post/failure/compact/stop
   events with per-handler authority, timeout, fail policy, telemetry and loop
   budgets. It must wrap existing AQ-OS authorities, not replace them.
3. **Capability taxonomy and resolver** — map task requirements to existing
   skills, domain instructions and agents; expose true uncovered outcomes before
   proposing new skills/personas.
4. **Portable CI/CD enforcement pack** — greenfield and guarded brownfield
   adoption with pinned dependencies, minimal permissions, fork-safe secret
   isolation, required checks, artifacts/provenance, environment approval and
   owner-controlled rollback.
5. **Eval dimension expansion** — test completion truth, silent failures,
   cancellation/suspend recovery, permission denial, resource budgets and
   provider projection parity through existing QA/dogfood authorities.

## Adversarial corrections to the Antigravity report

The existing report is retained as advisory input with SHA-256
`d979f33368ef5731be4a1d7b24dc20e1fe43d38418a83aae481161ddacbee4fe`,
but cannot drive bulk intake without these corrections:

- “16 harnesses” has no declared consistent counting rule; the adapter registry
  exposes 15 IDs across 14 collapsed families.
- AQ-OS does not have “~10 commands”: committed source contains 159 tracked
  `scripts/ai/aq-*` CLIs. The narrower IDE slash-command UX gap is real.
- AQ-OS does not have only five broad roles; its canonical role/type/domain
  architecture is richer and deliberately differs from persona-file counts.
- ECC's reported skill-category totals are not source-derived: only three skill
  manifests declare a `category` field.
- AQ-OS is not post-hoc-only: capability leases and executor/tool registry gates
  mediate actions before execution.
- AQ-OS already implements worktree management, continuous learning, memory
  redaction, canonical projection, evals, regression alerts and discovery APIs.
- The claimed ECC relevance example is inaccurate (`flake.nix` is not a detected
  stack marker), and AgentShield source is outside the pinned ECC subject.

Correct opportunity statements are therefore: extend canonical projection
breadth; unify provider lifecycle events around existing gates; admit only
demand-backed specialist checklists; harden existing worktree/operator paths;
expose existing discovery APIs in searchable UI; benchmark specific eval receipt
and replay semantics; and project only high-frequency CLI UX.

## Agent and skill semantic cluster pass

All 292 skill and 68 agent manifests were cataloged by filename/frontmatter and
description. Representative bodies were read for build/review, security, eval,
orchestration, memory, accessibility, local inference/MLOps and GitHub/devops.
This is cluster-level evidence, not a claim that every body/dependency/test was
fully audited.

- Build/review specialization is a partial outcome gap, but AQ-OS governance is
  stronger. Add language checklists only when measured failure demand warrants.
- Security admission, orchestration bounds and memory retention controls are
  stronger locally. External scanners, authenticated mutations and autonomous
  learning remain approval-blocked.
- Accessibility-specific review is the clearest low-authority candidate: extract
  a rubric, then connect it to existing UI tests without granting browser/write
  authority implicitly.
- Structured evaluator rubrics may complement existing evals; benchmark criteria
  and scoring rather than importing another harness authority.
- GitHub untrusted-content handling is already an equivalent policy outcome.
  Write actions remain explicitly approval-gated.
- The catalog includes many business, financial, creative, persona and framework
  variants that are not core factory gaps without a present demand signal.

## Explicit non-candidates

- Bulk copying all agents, commands or skills to satisfy inventory counts.
- Running ECC installers, auto-update, hooks, `npx`, scanners or sync commands.
- Importing a second memory, orchestration, review, deployment or policy SSOT.
- Arbitrary home-directory session ingestion or automatic Git stash/clear.
- Worktree orchestration that contradicts the owner's shared-directory,
  file/section-claim collaboration model.
- Enabling write, network, secret or account authority from prompt claims alone.

## Evidence still required before queue freeze

- Per-component dependency/license/SBOM review remains required only if later
  slices propose copying or executing upstream code; current native slices do not.
- Cataloged-only upstream material remains unknown and cannot justify intake.
- P0-A has a dispatchable baseline/acceptance brief; later slice baselines must be
  measured immediately before their implementation claims.
- Independent review of this ledger, meta-prompt, PRD delta and frozen plan.
