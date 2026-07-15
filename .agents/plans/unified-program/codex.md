# Codex ratification review — unified-program

**Subject commit:** `aa2e4452b72667d176403013b738b01fd08d15f4`
**Review posture:** independent; I did not read `claude.md`, `local.md`, or `antigravity.md`.

## Executive finding

The unified spine and parent architecture are directionally sound, but Track V and Check Kernel are not implementation-ready. The package needs four bounded corrections before activation: (1) make the CheckSpec transition backward-compatible with the live focused-CI registry, (2) define `ck.finding.v1`, (3) name the authority and schema for verifier-written acceptance records, and (4) add a dry-run/security oracle for VF-1. These are contract defects, not objections to the program direction.

## Subject scores and defects

### Subject 1 — Unified Program Plan: 7/10 — REQUEST_REVISION

Strength: the precedence map and traceability matrix finally give the four corpora, L-series, and Track V one navigable projection without pretending the projection is authority (`UNIFIED-PROGRAM-PLAN.md` §§1, 3–4).

Defects:

1. The authority map describes Track V as `VF-1…VF-8` at §1 line 24, while §4 line 103 and the VF PRD define nine slices. This is a direct completeness error in the top-level index.
2. Q2 allows state-spine adjudication to be deferred until after B2 evidence (§6 line 129), but B2 is explicitly gated on that adjudication (§3 line 59). The only safe sequence is: select one authority vertical and ratify its shadow hypothesis first, then collect B2 evidence; evidence may decide expansion, not retroactively authorize the first writer path.
3. The sequence says L2B-A finishes and immediately proceeds to L2B-B (§7 line 141), while VF fast slices begin after activation (§7 lines 147–149) and the VF document only says “L2B close or proven non-overlap.” L2B-B is the live payload/adoption slice and VF-1 extends task/result dispatch contracts. The projection must state whether “L2B close” means A only or A+B; my disposition is A+B before VF-1, unless an exact surface/hash non-overlap package proves otherwise.
4. Track V is called a layer that “gates all” (§3 line 66), yet VF-3—the component that makes verifier results authoritative—lands after VF-2 and VF-9 in the VF phasing. Before VF-3, fast-path claims remain reports. The plan must distinguish warn-only learning slices from acceptance-enforcing slices.
5. The state ledger count behind CK was already stale at the subject boundary: commit `aa2e4452` contains 98 registry checks, while the in-flight L2B-A work adds the current 99th. The plan/CK migration must bind to the post-L2B registry snapshot, not a floating count.

### Subject 2 — Verified Factory PRD: 6/10 — REQUEST_REVISION

Strength: risk-proportional gates, zero-inference oracles, and report-versus-record separation directly address measured failures (`PROJECT-VERIFIED-FACTORY-PRD.md` §§1–2).

Defects:

1. VF declares “no new authoritative writer” (§3 lines 56–58), but VF-3 requires acceptance/status records to be writable only through a verifier (§4 lines 108–115). The PRD does not name the existing authority, record schema, transition rule, recovery owner, or CAS/replay behavior. “Verifier path” is not an authority contract. VF-3 must remain warn/report-only until that authority is named or a separately authorized state-spine slice supplies it.
2. VF-1’s oracle block has an underspecified `cmd` (§4 lines 88–94): string versus argv, working directory, environment allowlist, artifact path containment, network profile, output cap, timeout termination semantics, and shell-metacharacter policy are absent. A sealed command can still be unsafe or non-reproducible.
3. VF-1 acceptance demonstrates enforce refusal but does not require a dry-run proving warn-mode classification, zero side effects, deterministic refusal reason, waiver behavior, timeout cleanup, and dashboard telemetry. Add a frozen fixture matrix and a live dry-run before the one-week promotion clock starts.
4. VF-3 requires output hash + lineage but no canonical outcome/finding schema is named. CK later refers to undefined `ck.finding.v1`; neither document defines how oracle output, truncation, artifact hashes, exit status, and verifier identity compose into a subject-bound verdict.
5. VF-4 says sealed cases are unreadable by implementers (§4 lines 118–126), while the bank contains the executable oracle and minimal repro context that implementers need to converge. Separate readable task/oracle material from sealed answers/canaries instead of sealing the whole case.
6. VF-5 says no live routing mutation this cycle (§4 lines 128–135), while A3 proposes interim manual mutation. If A3 is accepted, it is a substantive VF-5 amendment requiring a named routing authority, owner gate, diff/evidence record, rollback, expiry, and no model self-promotion.

#### VF versus L2B disposition

L2B-A currently edits `config/validation-check-registry.json`, Phase-0, dashboard health, schemas, and transport/result evidence surfaces. L2B-B is separately authorized live payload/parser adoption. Therefore:

- finish and independently accept L2B-A first;
- finish L2B-B before VF-1 because both affect dispatch/request/result behavior, unless a frozen exact-surface non-overlap package proves VF-1 touches only backlog schema and warn-only dispatch metadata;
- VF-7 may be prepared after L2B-A, but adoption by hash-bearing governance/verifier paths waits for a separately bound slice;
- CK compatibility work must consume the post-L2B registry snapshot (99 checks at review time), not rewrite the registry while L2B owns it;
- VF-3 cannot be promoted ahead of its record-authority/schema decision merely to satisfy phasing.

### Subject 3 — Check Kernel PRD: 5/10 — REQUEST_REVISION

The one-kernel goal is correct, but the rollout order and compatibility claim are presently unproven.

#### Focused-CI compatibility evidence

At subject commit `aa2e4452`, `config/validation-check-registry.json` has 98 checks; the active L2B-A diff adds the 99th. The current shape is not the proposed CheckSpec shape:

- all current commands are argv arrays;
- 97/99 current entries have `trigger_paths`; two have neither `trigger_paths` nor `timeout_seconds` and use `timeout_secs` instead;
- 94/99 have the legacy `tier`, whose values mean `behavioral|structural|security`, not VF risk `T0|T1|T2`; five have no tier;
- one check relies on both `always_run` and `pass_staged_files`;
- `run-focused-ci-checks.sh` lines 74–85 hard-require `id`, `description`, legacy `trigger_paths`, `command`, and flat `timeout_seconds`; lines 107–132 implement prefix matching and staged-file append; lines 180–228 emit the existing diagnostic result shape.

Therefore the CK §3.1 example cannot replace existing objects without breakage. `trigger.paths` would be ignored, `budget.timeout_s` would become unlimited, `enforce: warn` and `surfaces` would be ignored, and repurposing `tier` would erase the current structural/behavioral classification. The in-file `schema` object is descriptive metadata, not a validating JSON Schema, and no `ck.finding.v1` schema exists in `config/schemas/`.

A safe extension is possible, but only additively:

1. Land a versioned external registry/CheckSpec JSON Schema plus a compatibility normalizer that accepts legacy v1 keys and canonical v2 keys.
2. Keep `description`, argv `command`, `trigger_paths`, `timeout_seconds`, `always_run`, `pass_staged_files`, `enabled`, and `require_tool` operational until all 99 entries migrate.
3. Do not overload `tier`; use `check_class` for the old structural/behavioral/security concept and `risk_tier` for T0/T1/T2, or perform an explicit two-field migration.
4. Define `ck.finding.v1` and the run-result envelope before dashboard or VF-3 integration.
5. Prove parity by executing the same staged-path fixture matrix through legacy and normalized paths and comparing selected check IDs, argv, timeout, exit classification, and JSON diagnostics.

Migration size: one compatibility slice (runner/normalizer, external schema, fixtures/tests, registry version metadata) followed by a 99-entry data migration. Mechanically this is roughly 7–8 new canonical fields per entry, but owner/class/risk/surface/output assignments are semantic decisions, not a blind rewrite. Budget it as 4 batches of about 25 entries with parity evidence per batch. Resolve the five missing legacy tiers, two missing triggers/flat timeouts, and the one always-run/pass-staged special case explicitly. Do not combine this with migration of the 19 tier0 gates or 80 governance scripts.

#### CK §9 answers

**(a) Interim runner:** minimal `aq check` compatibility runner first, not direct reuse of focused-CI as the CK-1 kernel. The focused-CI implementation is a valuable execution backend and parity oracle, but it cannot express profiles, warn/enforce, `--fix`, nested budgets, classes, or structured findings. A thin `aq check` normalizer can delegate legacy execution to focused-CI while providing the new contract; this closes the CK-1/CK-2 circular dependency (§5 lines 127–131 and §6 lines 144–147).

**(b) Ratchet unit:** module, with directory as a fallback grouping only where no module boundary exists. Directory ratchets are too coarse in mixed `scripts/`, `assets/`, and `ai-stack/` trees and can couple unrelated owners. Registry entries should name a stable module/owner scope and optionally map it to path sets.

**(c) Biome vs ESLint:** Biome for the current vanilla dashboard because CK needs one Nix-pinned formatter+linter with deterministic JSON and low operational weight. Keep repo-custom architectural checks as CheckSpecs. Revisit ESLint only if the dashboard adopts framework/plugin rules that Biome cannot cover; do not introduce both now.

Additional defects:

1. CK-1 requires registry-driven kernel entries before CK-2 introduces the schema and `aq check` runner (§5), creating a circular rollout dependency.
2. “Phase-0 registrations are GENERATED” (§3.2 lines 67–71) does not define generated source ownership, regeneration drift check, or how check IDs remain stable across Python/Bash projections.
3. “Zero checks defined outside the registry” (§7 lines 158–162) is not achievable until “live check” is formally defined; service health probes, integration tests, and external tool-native checks need an inventory rule, not merely relocation.
4. CK-1 is labeled T1 in §5 while §6 correctly says tier0 governance edits require T2 subject binding. The phase table must use T2 for the registry/runner/tier0 mutation portion.

### Subject 4 — Codex–Fable synthesis: 8/10 — APPROVE as parent architecture

The synthesis correctly separates product direction from trust substrate, treats projections as non-authoritative, and keeps authority selection open (`PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` §§2, 4–5). I approve Q1 with the Unified Plan’s projection and the revisions above.

Non-blocking clarification: the target diagram names Postgres (§7 line 185) while §4.1 and §5 leave per-authority versus Postgres/outbox adjudication open. Label Postgres in the diagram as a hypothesis until Q2 is decided. Also replace immediate decision §10.2’s one-sided “ratify Postgres/outbox” with the Q2 alternatives from the Unified Plan.

## Owner decision queue Q1–Q9

| Decision | Disposition | Reason |
|---|---|---|
| Q1 | **APPROVE** | Ratify the synthesis as parent architecture with the Unified Plan as a corrected projection, not a new authority. |
| Q2 | **REVISE** | Ratify the per-authority ADR decision for the first shadow vertical before B2; Postgres/outbox remains a testable hypothesis, not a default that may be decided after writes begin. |
| Q3 | **APPROVE** | Principal attestations, non-fail-open leases, and connected network profiles are the right direction; each enforcement surface still needs separately versioned contracts and failure tests. |
| Q4 | **APPROVE** | Convert the named-model behavior document into model-neutral, versioned canon policy. |
| Q5 | **APPROVE** | Roles remain model-neutral; eligibility must be measured, scoped by task class, expiring, and independently promoted. |
| Q6 | **APPROVE** | Keep `local-orchestrator` as the declared front door until evidence supports a named kernel revision; compatibility usage must be measured before retirement. |
| Q7 | **APPROVE** | Universal promotion gates are appropriate, provided datasets/scorers themselves have lineage, certification, rollback, and anti-gaming controls. |
| Q8 | **APPROVE** | Adjudicate all ten Cycle-0 authority rows before selecting or implementing B2; this is a prerequisite, not parallel cleanup. |
| Q9 | **REVISE** | Activate Track V only after VF/CK contract amendments, exact per-slice authorizations, and L2B-A/B closure or frozen non-overlap evidence. VF-1 begins warn/dry-run; VF-3 stays non-authoritative until record authority is named. |

## Amendments A1–A6

| Amendment | Score | Disposition | One-line reason |
|---|---:|---|---|
| A1 | 8/10 | **REVISE** | Pull stacking work into D/E, but Q10 must measure RAM/VRAM/latency on the Renoir ceiling before asserting one quant step funds both a resident model and speculative decoding. |
| A2 | 10/10 | **APPROVE** | Re-verifying actual F2.5 wiring before sequencing is mandatory; if dormant, pull-forward is justified because serialization directly constrains oracle throughput. |
| A3 | 7/10 | **REVISE** | Add the taxonomy, but manual pre-Cycle-5 routing mutation needs named authority, owner approval, evidence, rollback, expiry, and strict separation from model self-promotion. |
| A4 | 8/10 | **APPROVE** | Atomizer, context curator, and deterministic evidence clerk are useful only with typed, measurable handoffs; treat them as capabilities before creating permanent role identities. |
| A5 | 7/10 | **REVISE** | Multi-pass T2 review can improve coverage, but define pass independence, typed outputs, stop conditions, deduplication, and a governance-overhead budget before making six passes mandatory. |
| A6 | 9/10 | **APPROVE** | Failure capture needs a named Product-E consumer, provenance/privacy controls, dedupe, and an explicit promotion criterion so logs become training evidence rather than an unbounded queue. |

## Codex lane claims

Claims are sequential and subject to exact authorization; they do not interrupt L2B-A/L2B-B.

1. **Implementer:** CK compatibility/normalizer slice and focused-CI parity fixtures; then batched registry migration after independent review.
2. **Implementer:** VF-1 schema + warn/dry-run dispatch gate after L2B closure/non-overlap proof; VF-7 unwrapped evidence path as a separate bound slice.
3. **Implementer/reviewer:** VF-2 deterministic classifier and CK runner integration; independent review must be performed by another eligible lane for Codex-authored code.
4. **Reviewer/orchestrator:** VF-3 authority/schema design and incident fixture, but no authoritative writer implementation until Q2/Q8 and the verifier-record contract are resolved.
5. **Reviewer:** CK-3 Biome/treefmt adoption and per-module ratchet; implementation can be routed separately once the compatibility kernel is stable.

VERDICT subject-1: REQUEST_REVISION
VERDICT subject-2: REQUEST_REVISION
VERDICT subject-3: REQUEST_REVISION
VERDICT subject-4: APPROVE
VERDICT overall: REQUEST_REVISION
