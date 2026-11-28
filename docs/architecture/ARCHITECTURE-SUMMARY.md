# Architecture summary for external reviewers (rev 5.1)

Status of this page: the contract guard is shipped by slice S1 (the Rust checker, the tier0 check and the two CI workflows); everything else below is a PLAN. "Enforced" means a gate fails on it today; "planned" means designed in `DESIGN.md` and not yet enforced; "today" means observed in the repository. Each section says which applies.
## The problem in plain words

About 30 components make decisions, and several decisions have more than one owner (model routing, which lane is available, who may change a pull request branch, whether a review was independent, health repair, loops, deploys, memory, learning). Three recovery decisions (pending intents, workflow checkpoints, approvals) have no owner at all. Ownership today lives in prose and per-plan lists; the registry that should hold it (`config/system-state-authorities.yaml`) lists ten rows, all marked split-brain with expired deadlines, and no required check enforces it.

## The design in five contexts

| Context | Owns | Single decision owner (planned) |
|---|---|---|
| K1 Work orchestration | dispatch, per-model availability, recovery of intents and checkpoints, retry budgets | the coordinator |
| K2 Model execution | choosing a model route, then running it | coordinator chooses; switchboard executes and returns a receipt |
| K3 Trust and integration | review independence, landing, approvals, owner waivers, contract and gate rules | review verifier, `aq-land`, coordinator approval store |
| K4 Host configuration | declared host state, activation, secrets, third-party pins and upstream patches | Nix options, `aq-update`, `scripts/upstream/REGISTER.json` |
| K5 Evidence, memory, learning | health evidence, memory writes, lessons | evidence reducer, MemoryBroker; learning only proposes |

No new service is added. Contexts talk through versioned contracts under `contracts/`; one registry (`system-state-authorities.yaml`) says who owns what.

## How it is enforced (shipped in slice S1; the required-check setting in GitHub is an owner act)

A Rust checker (`crates/contract-validator`, binary `harness-contracts`) reads that registry and fails a change that adds an uncontracted import, subprocess call, HTTP call, event or dynamic call across a boundary. Enforced today: the pre-commit gate (`tier0.d/check-contracts.sh`, always on, fails closed) and the CI workflow `contracts-boundaries`, which runs the checker built from the trusted base branch over the pull request as data, so a pull request cannot weaken its own checker. A second, unprivileged workflow runs the candidate's own checker on a known-bad corpus read from the base branch. Making `contracts-boundaries` a required status check is a repository setting the owner applies. Existing violations are recorded as dated exceptions; any new one fails from day one. Not enforced yet: the single-owner writer rules (the existing Python checker covers them only in part) and every slice after S1.

## Hard constraints and where each stands today

| Constraint | Today | Plan |
|---|---|---|
| C1 no paid or hosted model API required | partly violated (default reasoning route is a hosted model; local review of trust-critical changes is refused) | local default route; offline journeys; owner-waived local landing that never counts as a review |
| C2 no npm or Node | violated (Node in every profile, npm CLIs, web-UI build, `npx` launchers) | Node-free supported install; the Claude/Codex/Gemini CLIs move to an optional add-on |
| C3 Nix-native and pinned | partly (one package pinned by hash only, one placeholder hash) | every supported-install component pinned in `flake.lock` or a fixed-output hash |
| C4 modest hardware, offline | no profile fits 16 GB | `lite` profile, budgets measured on a 16 GB machine (figures unverified until measured) |
| C5 licence compatible with AGPL plus commercial licence | no policy | invoking an unmodified binary is fine; linking or vendoring needs a compatible licence or owner waiver; unresolved = not passing |

## Build versus adopt

Keep our components for now. nh (a Rust NixOS rebuild helper) gets one bounded spike inside `aq-update` with a sunset. LangGraph is deferred. OpenClaw and devenv are reference-only (OpenClaw needs Node and closes none of our overlaps). LiteLLM, deploy-rs and colmena stay as keep-custom or later options. Each decision gets an ADR.

## Counting ownership honestly

A 28-row decision table seeds the count. Two separate numbers are reported, because they measure different things. Overlapping rows: at least 7 verified, 4 more carried and 5 unverified (the tool prints these). Writer total: the sum over decisions of max(0, independent writers minus 1); it is unknown until every row has a verified writer list (17 rows lack one today), and no upper bound is claimed. Orphans: at least 6 verified; the new row and the five unverified rows could add up to 6. The target is zero overlap and zero orphan for the MVP rows at the exit audit, computed by `harness-contracts decisions --count`, never typed.

## Order of work

S0 freeze, S1 contract guard, S2 authenticated review and owner waiver, S1b single landing queue, S4 per-model availability, S4a recovery owners, S3 routing owner, S1c upstream register, S1d Node-free closure and pin and licence checks, S13 `lite` profile (plus a lease-enforcement probe, with a contingent S13b), S12 exit audit (journeys J1-J8, including three that run fully offline). Deploy, health, branch-lock, memory, loops and learning follow.

## What reviewers should challenge

Whether the 28 rows are the right decisions; whether the guard can truly cover dynamic calls; whether the `lite` budgets are achievable; whether an owner waiver is an acceptable local-only substitute for independent review.

Details: `DESIGN.md`; consolidation record: `REVIEW-R5.md`.
