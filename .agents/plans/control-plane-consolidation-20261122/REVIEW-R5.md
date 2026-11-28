# Revision 5 consolidation record

Status: rev 5 DESIGN.md consolidated from three independent drafts; buy-in pending (table at the end is intentionally empty). This file is the consolidation record only; the design is `DESIGN.md`. It ships inside the S1 code PR with the amendment (no docs-only PR).

## Base and provenance

- Rev 4 base: `origin/feat/control-plane-consolidation-prd` tip `af2a99023` ("freeze control-plane consolidation revision four"): DESIGN.md sha256 `290911f40484267560d103b51d89df26607ef5c85a30dfb6b0cb29e2513b9a8f`, tracker.json sha256 `eb0433e15bbb1d552e03b757e4ca325e09ef9a5ec25f0738147c922cc586b7f1`, REVIEW-R4.md sha256 `23720b584d0a2ef92a5336ea72ceab956ee10682646ca963bc2861bebd95bfa5`. These match the final digest in `REVIEW-R4.md:40`.
- Branch note. The local branch `feat/control-plane-consolidation-prd` is at `676d8b301` (rev 3) and is checked out in `.claude/worktrees/agent-ab5b97e0a0cbd2ec8` with an uncommitted rev 4 working copy (DESIGN sha `3b344fdf...`, an earlier digest, whose tracker carries a `pct_hint` field that `scripts/governance/tier0.d/check-anti-fabrication.sh` forbids). `git worktree add` on that branch name therefore failed. This work is in a detached worktree at `af2a99023`, so the staged diff is rev 5 against the frozen rev 4. The branch is 49 commits behind `origin/main`: rebase before the S1 code PR.
- Evidence files are not tracked (`.agents/delegation/outputs/` is an outputs directory). S1 copies them to `docs/harness-first/evidence/2026-11-27-arch-rev5-phase0/`.

## Input drafts

All under `.agents/delegation/outputs/arch-consolidation-rev5/`.

| Input | sha256 |
|---|---|
| `PRD-DRAFT-claude.md` | `4658d9ae1900d6ee10b0379ae71a1ef567a78cc5ee1e0889a4eaad62c786286b` |
| `PRD-DRAFT-codex.md` | `8433a326da16c9a0b34e38aaaaf04ead7a20962dcc424a28cfbdf065ad58ad3e` |
| `PRD-DRAFT-gemini.md` | `e211fc8381d6421b6fca56fe2c85aee840afb8fb385df79e39a9ad773db47e92` |
| `draft-brief.md` | `84d26a1e00596c3f27c3b314dab21f19443851478bd1c6a11279910c6efc8116` |
| `review-codex.out` (final review at lines 1349-1433) | `807fce9d879074b4adb677ecde3815265da2fee83429bbe109d3eb0686b6037d` |
| `review-gemini.out` | `de05b8ef008f47b4a5e2da277f0b53167d80d9d7468d79ff1b47631946a69d8e` |
| `delta.md` | `c8e31166779e25f9e8fe33f4af6e6f5cedaf962da08a2aed09d030d4cbcf2c04` |
| `census-refresh.md` | `c3c098ea608c24ae46e26d39586f97df4dbb8e8640725f447b6fa75e21e90f52` |
| `candidates.md` | `3167def18c06e005a58c085700b58b48fdff61424ecbee37ad7ad596e96a0fac` |
| `c1-c4-audit.md` | `d5f4b3f9154e1e2d2643f0a8c360ff6046fb81e3cbff9e26732beea334010a89` |
| `upstream-candidates.md` | `0b21b988fd0ab2f4176777008c88fbe1bcadfe7fbcf995c2cfa07eb6c957f76a` |

The local Qwen review (`review-local.out`) was power-gate DEFERRED and produced no review; local input is advisory in any case.

## Method

The Claude draft is the structural base (it follows the brief's 14-section order and is the most complete on matrix, contracts and acceptance); Codex supplied the trust-preserving rules, the counting rule and the MVP-scope reporting; Gemini supplied the lite security floor, the S10 premise check, the explicit C3 and C5 policy wording and the dynamic-call split. Where drafts differed only in wording the clearer text was taken. No scope was added beyond the three drafts and the brief. Facts were not re-run beyond the spot checks listed under "Facts verified". Every claim keeps its citation tag ([V] verified here, [C] carried).

## Disagreement table

"agree" means the draft takes the position in the Resolution column.

| # | Topic | Claude | Codex | Gemini | Resolution | Reason |
|---|---|---|---|---|---|---|
| 1 | D-R5-3 Rust guard and dynamic calls (each draft's section 14) | Rust in S1 with a minimal token scanner; any dynamic construct fails unless annotated `# contract: <id>` or excepted | A regex-only import guard does not implement D-R5-3; dynamic and non-import transports need declared edges plus runtime admission | Rust in S1 but static only; true dynamic-call blocking is runtime admission at S2-S11, not static heuristics | Rust `contracts`/`boundaries` in S1; scanner is token-level (no flow analysis); every dynamic construct fails unless annotated with a contract id whose owner enforces runtime admission, or excepted; annotated sites are never claimed proven | Union satisfies the approved decision (covers dynamic calls) without S1 scope bloat; the three positions are compatible once the annotation names a runtime owner |
| 2 | Python checker vs Rust guard | Python `--matrix` is a prototype; archive after Rust parity; DO rows become YAML rows checked by the same binary | Retain Python where useful | Keeps `check-state-authorities.py` plus new Rust in tier0 | Both coexist with disjoint jobs: Python = who writes (rev 4 DO rows), Rust = who calls and counts; port writer guards only on a trigger with parity tests | Porting writer guards is extra S1 scope; the Language-by-Role canon allows ports only on a trigger |
| 3 | Overlap and orphan counts | 28-row seed; verified overlap 7 (up to 16), verified orphan 6; refuses 0/0 | Counting rule; totals UNVERIFIED; "report the three documented recovery gaps, total unknown" | 19 rows; overlap 15, orphan 7 as a provisional floor | 28-row seed with Codex's counting rule; ranges reported; Gemini's 15/7 treated as a floor on a different decomposition until the mapping ships; no 0/0 until a tool computes it | Brief and both reviewers forbid claiming 0/0; the numbers are not comparable across decompositions |
| 4 | Target totals at MVP exit | overlap 0, orphan 0, unverified 0 at S12 | MVP reports its bounded set and the remaining post-MVP rows; no whole-roadmap zero before cutovers | "reduced to the post-MVP follow-on set only" | MVP-scope rows 0/0 and zero UQ rows at S12; post-MVP rows (D05 bots, D13-D16, D18, D19) listed with slice; whole-roadmap 0/0 after S10 | Post-MVP slices cannot have cut over at S12; Claude's literal target would be unsatisfiable |
| 5 | D-R5-4 queue timing and unit | `aq-land-queue` is the executor behind the existing durable unit; activate only after S2; if two programs, archive one in S1b | Activate `aq-land-queue` using S2 admission and existing durability; retire seqland in the same PR | Fold into `aq-land-runner.service`; do NOT merge `aq-land-queue` ahead of S2 as a "temporary improvement" | `aq-land-queue` is the sole queue implementation, run by `aq-land-runner.service`; it lands in the S1b PR, not earlier; `seqland*` retire in that PR | One queue, one unit; merging it earlier is a dormant (Rule 23) unguarded second writer with no reservation or fencing |
| 6 | Offline review journey and the second local model (Claude s14.4; Codex s14.6) | Drop a second local model as reviewer; J7 gives a reduced-assurance record and no receipt | A waiver is not equivalent assurance, never a receipt | J-OFF-2: "local second-model OR owner-waiver review" | J7: local-model review is advisory evidence; every local-only landing needs the D-R5-1 owner waiver; record stamped `local-only-waiver`; no receipt; a second local model never counts as independent review of a trust-critical change | D-R5-1 requires a waiver bound to the candidate; Claude's "reduced-assurance record without a waiver" would be an unbound path |
| 7 | Slice placement of C2, C1 and `lite` work | S1d (C gates, C2 cleanup) and S13 (`lite`) as new slices before S12 | Scaffolding in S1; complete `lite` profile and offline bundle inside S3 | C1/C2 checks in S1; C2 cleanup inside S3; `lite` as S4b | S1d (C1/C2/C3/C5 gates, closure cleanup, add-on, retirements) after S1; S13 (`lite`, runbook) after S3 and S1d; S3 stays routing only (plus the local default model) | One slice, one concern (Rule 1); S3 is the routing owner; S13 depends on the local default model fix in S3 |
| 8 | Slice for recovery owners (D09-D11) | none: assigned in the matrix, no slice | "Assign and test" with no slice | folded into S4 (approval, intent recovery) | New S4a after S1b (approval recovery reads the reservation log); S4 stays per-model availability | Orphan = 0 needs a slice; S4 is DO-4 only |
| 9 | S10 entry condition (Gemini s14.4; Claude carried census row) | not addressed beyond census note | "A later 'frozen' label is not clearance by itself" | Rev 4 premise is stale after #878; gate on reconciling `aq-baseline` instead | S10 entry condition: re-check the merged frozen PRD against the two REVISE verdicts; proceed only when independent review confirms each is resolved | Neither "still REVISE" nor "already resolved" is established; both are UNVERIFIED |
| 10 | Upstream attribution guard (strip vs reject) | hook rejects trailers; `dev submit` rescans; tier0 refuses | must not strip attribution to conceal provenance | hook "strips and blocks" trailers | Reject, never strip; rewriting a commit message is an owner act | Stripping conceals provenance and can evade an upstream AI policy (`ai_policy` is unknown) |
| 11 | Upstream register fields, lifecycle and direction | brief fields plus `decision/decided_by/decided_on`; REGISTER authoritative for third-party items; WR carries `upstream_id` | owner-owned lifecycle; many extra fields; WR section projected | status `inventory..retired`; `decision` fields; WR references ID | Brief fields plus decision fields, `upstream_pin`, `ai_policy_checked_on`, `workaround_id`; status `inventory, drafted, owner_cleared, submitted, merged, retired` plus `deferred`/`rejected`; direction: register owns external lifecycle, WR owns local symptom and mitigation and projects status | Smallest set that carries the brief's fields and Codex's lifecycle states |
| 12 | `lite` budgets | peak <= 8 GiB; idle <= 2.5; model+KV <= 4.5; GPU <= 2 GiB; closure <= 12; TTFT <= 20 s; >= 5 tok/s | peak <= 12 GiB; GPU <= 4 GiB; model <= 4; embeddings <= 2; closure <= 12; bundle <= 40; p95 TTFT <= 15 s; activation <= 30 min | peak <= 8.0 GB; model+embed <= 5 GB; closure <= 6 GB; <= 12 layers; guard <= 2 s | One merged table, all UNVERIFIED: peak 8 GiB (two of three agree; leaves 8 GiB for OS), GPU 2 GiB (the carve-out comes from system RAM) plus <= 12 layers, closure 12 GiB (tighten after measurement), TTFT p95 15 s, bundle 40 GiB, activation 30 min, guard 2 s | Take the value two drafts agree on; otherwise the safer, with the reason recorded; owner ratifies in D14 |
| 13 | RAM assertion | tiered, not specified | profile- and model-aware | `>= 8 GB` for `lite` | Function of model estimate plus overhead plus OS reserve; the claimed minimum is 16 GiB (the measured machine); lower is unsupported and warns | An 8 GB claim would cover a machine nobody measured |
| 14 | `lite` security floor (Gemini s14.3; Codex s14.4) | define the minimal auth set first | do not disable identity indiscriminately; capability-level dependency tests | loopback bearer token, 0600, generated at first boot | S13 defines the minimal auth set first; default is Gemini's loopback bearer token when the identity-kernel quartet is off; features disabled, authorization never bypassed | Compatible positions; the token is the concrete default |
| 15 | C3 reading for candidates whose nixpkgs pin trails upstream | PASS (pinned) with pin currency noted | not rated per candidate | NOT PASS for nh, colmena, devenv | C3 = reproducibly pinned; staleness is pin currency; nh's bump is a precondition of the S5 spike; LiteLLM's vulnerable pin is a security-gate failure | The brief defines C3 as pinning, not freshness |
| 16 | Candidate verdict wording | OpenClaw REFERENCE-ONLY, devenv REFERENCE-ONLY, LiteLLM KEEP-CUSTOM | LiteLLM deferred; OpenClaw reference-only | LiteLLM "rejected" in the ADR title, KEEP-CUSTOM in the table | OpenClaw and devenv REFERENCE-ONLY; LiteLLM KEEP-CUSTOM; others as rev 4 | Brief mandates OpenClaw REFERENCE-ONLY; rev 4 owner decision D4 is KEEP-CUSTOM |
| 17 | ADR list | 15 ADRs | 11 (ADR-R5-01..11) | 10 | Claude's 15 (one per adopt/build decision, one per approved D-R5 decision, the licence policy) | Brief: one ADR per adopt/build decision; separate ADRs for devenv and deploy-rs match its candidate list |
| 18 | Context changes | K3 gains contract/gate governance; K4 gains secrets and upstream lifecycle; coordinator owns recovery | K1-K5 unchanged; refinement inside | Upstream lifecycle in K4 and owner approval in K3; `harness-contracts` in K3 | Claude's changes, stated with their orphan justification; no sixth context | Every change closes a named ownerless decision |
| 19 | Rollback (Codex s14.1) | reverting S1 removes the checks; moved readers keep shims | rollback must not restore a bypass, revive grants, lower epochs or replay uncertain operations | atomic PR revert; shims until parity | Both: PR revert for guards and Nix; for S2/S1b/S4a rollback restores the previous implementation behind the same trust boundary or HOLDS | Reverting trust code must not reopen a bypass |
| 20 | Owner host and C2 (Claude s14.5) | owner's daily lanes are the add-on; "C2 holds for the supported install only" | optional add-on is a separately evaluated installation | remote CLIs outside the supported closure | Same position in DESIGN; the owner's host classification is open question 3 | Needs an owner statement |
| 21 | Rev 4 D0 grants (Claude s14.7) | D0 stale: 23 of 25 renewed, Gemini binding revoked; re-route per Rule 18 | D0 "DONE" is wrong against rev 4's six-role scope | open question: who holds binding acceptance | Rev 4 D0 amended; open question 1 asks who holds binding acceptance | A grant decision is an owner act |
| 22 | A9 runtime lease enforcement (Claude s14.6) | keep UNVERIFIED; add D21 | do not activate inactive schemas | live-verified in S2/S12 | D21 UQ; proven in S12 | Rev 4 already marks it unverified |
| 23 | Waiver lifetime and where it is decided | default 24 h, cap 7 days; question 4 | bound to expiry, no values | owner-signed, expiring | Default 24 h, cap 7 days, adjustable at S2 review; not an owner question | A tunable default, not an owner decision |
| 24 | Slice naming, local-queue and registry model-id prerequisite | S1a/S1c/S1d/S13 suffixes; S4 consumes the uncommitted registry `model_id` change | keeps rev 4 numbers | S4b for lite; S1 absorbs C checks and register | Keep `S1` as the guard (no S1a); add S1c, S1d, S4a, S13; S4 lists the `model_id` landing as a prerequisite | `S1` matches D-R5-3's wording "contract guard in S1" |
| 25 | Summary location | `docs/architecture/ARCHITECTURE-SUMMARY.md` in S1 | one-page summary inline in the draft | same path as Claude | Plan-dir `ARCHITECTURE-SUMMARY.md` now for reviewers; S1 moves it to `docs/architecture/` | Reviewers need it before S1 exists |
| 26 | Mermaid style | cross-context edges labelled with contract names; dotted guard edges | adds a `contracts/` node | subgraphs with components | Claude's labelled edges; the `contracts/` node is described in prose | Simplest diagram that names each contract |

## Corrections from the Phase 0 delta reviews, applied

From `review-codex.out` and `review-gemini.out` (both mark the delta's "9 overlaps / 3 orphans" as a floor, not a total):

1. `config/schemas/` has 64 tracked files, not 59 (Gemini); 71 `*.schema.json` repo-wide. [V by `git ls-files config/schemas | wc -l`]
2. `check-state-authorities.py` is also referenced by `config/validation-check-registry.json:1044`, `scripts/ai/_aq-qa-bash:1676`, `scripts/testing/harness_qa/phases/phase0.py:3057` (Gemini), but still no tier0 or GitHub gate.
3. `.upstream/` is already gitignored at `.gitignore:167` (Gemini). [V]
4. The census's "D0 DONE" is wrong against rev 4's six-role scope: #871 revoked Gemini binding-acceptance (Codex, Gemini).
5. `lib.fakeHash` in `nix/pkgs/pi-agent.nix` proves a placeholder hash, not "never built" (Codex).
6. nixpkgs availability alone does not make our packaging redundant (Codex); a functional comparison precedes retirement.
7. `CONFIG_SCHEMA_REGISTRY` must be derived or an explicit schema lookup, not a second ownership map; dangling, duplicate and incompatible-version failures required (both).
8. Missing decision types: approval issuance/revocation/recovery, checkpoint and intent recovery, reservation/retry/reconciliation, contract-version compatibility, capability lease/execution cell/revocation epoch, secrets/SOPS, upstream lifecycle, intent-lock/session continuity, CI/tier0 gate ownership (both): all in the 28-row matrix.
9. D-R5-2 and D-R5-3: the reviewers' DISAGREE and AGREE-WITH-CHANGES were resolved by the owner's approval; the changes (build and runtime closure, no exception list, Rust in S1) are in the design.
10. Still missing in the delta, now designed: offline journeys, negative tests proving a candidate cannot weaken its checker, full call-kind coverage, C3/C5 evidence with unresolved = not PASS, exhaustive upstream discovery with a stated limit, the fleet-vs-student acceptance boundary, the offline runbook, the attribution guard, the binary-invocation vs linking policy, the baseline-branch disposition (rev 5 amends rev 4 on its branch).
11. The Claude and Gemini drafts state these corrections explicitly and the Codex draft applies them implicitly; rev 5 states each once, in the claim table and the policies.

## Facts verified in this consolidation ([V]: read at base `af2a99023` and re-read against `origin/main` `3be232b6c`, 2026-11-27; both agree)

`crates/contract-validator/src/{main.rs,scope_gate.rs}` and the four subcommands (`main.rs:71-74`); `check-owned-scope.sh:11-14` exits 0 without `OWNED_PATHS`; `contracts/` holds `config` and `events`; `config/schemas` 64 files; `docs/architecture/adr` absent; `scripts/upstream/` has `dev` and `track`; `.gitignore:167`; `nodejs` at `nix/data/profile-system-packages.nix` (lines 7, 96, 112, 128); `config/model-coordinator.json:480` = `claude-reasoning`; `contracts/events/envelope.py` `SCHEMA_VERSION = 1` and `extra="forbid"`; `nix/modules/roles/ai-stack.nix:1010` asserts `>= 12`; `ai-dev.nix:54-71` flags; `review-disposition.yml` runs under `pull_request_target` (`:3,17`); `rg -l state-authorities scripts/governance .github` returns only the checker; `scripts/governance/tier0.d/check-anti-fabrication.sh` forbids `pct_hint`. Not re-run: line citations into `aq-land`, `aq-review-receipt`, `runtime_controls.py`, `nix/home/base.nix`, census and candidate facts, and everything tagged [C].

## Brief requirements not fully satisfied in this pass

- ADR files, the contract schemas, the Rust subcommands, the matrix tool and the upstream register are DESIGNED, not created; they ship with S1, S1c and the later slices (the brief's own rule: no docs-only PR for code-bearing deliverables, and this task stages text only).
- `ARCHITECTURE-SUMMARY.md` is in the plan directory; the brief's `docs/architecture/` location is reached by S1.
- The Mermaid diagram was not rendered by a tool here (no renderer run); syntax follows the flowchart subset used by the Claude draft.
- Counts are ranges from a seed, not tool output; measurement fields (budgets) are UNVERIFIED by design.

## Open questions for the owner (max 4; each with a recommended default)

1. Who holds binding acceptance for S1-S12 now that Gemini's binding-acceptance grant is revoked (#871)? Context: rev 4 D0 required six roles; 23 of 25 grants were renewed to 2027-01-09 in a different scope. Recommended default: the registry's current grants decide per slice; a non-author Codex or Claude lane holds binding acceptance; Gemini is not re-evidenced before S1; exact grant IDs are shown before any change. (DESIGN D11)
2. Confirm the C5 reading: invoking an unmodified EUPL-1.2 or MPL-2.0 binary (nh, deploy-rs) is acceptable under `LICENSE` plus `COMMERCIAL-LICENSE`; linking, vendoring or modifying needs an owner-signed waiver. Recommended default: as written. (DESIGN D12)
3. Is the owner's own `ai-dev` host a supported install (add-on OFF) or a developer-fleet host? Recommended default: the owner's host keeps the remote-lanes add-on ON and is exempt from the C2 closure test; `lite` and add-on-OFF `ai-dev` carry the C1-C5 checks. (DESIGN D13)
4. Which real 16 GB machine and which pinned model of at most 4 GiB define C4 certification, and are the provisional budgets ratified before S13 starts? Recommended default: the owner names the machine; budgets as listed in DESIGN, ratified at S0 and revised only with owner approval after measurement. (DESIGN D14)

Not asked because decided or resolved on evidence: D-R5-1..6 (approved 2026-11-27); waiver lifetime (default 24 h, cap 7 days, S2 review); `herdr.nix` C3 handling (S1d decides: flake input or excluded from the supported closure); `opencode`/`models-dev` placement (add-on via nixpkgs, ADR 0014); lite persistence backend and auth floor (S13 spike); S10 premise (entry-condition check).

## Buy-in round 1 (Gemini, 2026-11-27)

Gemini verdict: REVISE. Reviewed DESIGN.md sha256 `6e75de60c80163b95096c241ba41051dd915f3b1c4f14b1ce983f7d6c97d07cd` (output `buyin-gemini.out`). Codex: not run (provider cooldown). Local: not run (power-gated, cpu 84C). Revised DESIGN.md sha256: `a6aa55bb4484841f8700c1334ed8555ea1579a2f67fe3f54dfacb3c7c5563029` (needs re-review).

| Sev | Finding | Fix (DESIGN.md section) |
|---|---|---|
| P1 | Privileged-context RCE: `contracts-boundaries` under `pull_request_target` built and ran the candidate's checker | Invariant added in "Contract design and the Rust contract guard" (gate wiring): the privileged job uses only the base-ref checker and reads the candidate as data; candidate code runs only in a separate unprivileged `pull_request` job (contents: read, no secrets). N2 split accordingly; new negative test N8 (canary build script must leave no sentinel; lint fails a `pull_request_target` job that builds the PR head). Acceptance A3 and S1 exit say N1-N8 |
| P1 | MVP DAG cycle: S1d exit needed S3 and S13 artefacts | S1d scoped to add-on-OFF `ai-dev` and static scans, `model-coordinator.json:480` a dated baselined exception until S3; `lite` C1/C2/C3/C5 and J6 moved to the S13 exit. DAG stated and checked in "Execution order": S0<-; S1<-S0; S1c, S1d, S2<-S1; S1b<-S2; S4, S4a<-S1b; S3<-S4; S13<-S3,S1d; S13b<-S13; S12<-all; acyclic; tracker deps match |
| P2 | C2 used `/run/current-system` | "C1-C5 policies" C2 check and acceptance row C2 use `nix path-info -r <built profile outPath>` plus `nix-store -qR $(nix-instantiate <toplevel>)`; the `lite` closure budget measures the built outPath |
| P2 | Supported set could shrink silently | "C1-C5 policies": a Node-pulling member is disabled by default or moved to an opt-in add-on flag, or the owner explicitly drops `ai-dev` from the set; never silent, never empty before S13 |
| P2 | Waiver bound to GitHub repo id and PR | "Local-only landing": `mode` (`github` or `local-no-github`), local repo identity, GitHub `repo_id` and `pr` nullable when local; cross-mode consumption refused. Candidate glossary row updated |
| P2 | [V] provenance inconsistent (rev3 hash, "on origin/main") | Header defines [V] as read at base `af2a99023` and re-read against `origin/main` `3be232b6c`; Problem addendum says which items were re-read. I re-read the Problem-addendum facts and the envelope against `origin/main` now; unread claims remain [C]. This file's "Facts verified" heading aligned |
| P3 | Owner-key provisioning missing from S2 | S2 slice row: owner key provisioning is a prerequisite for S2 exit (S1c needs it too) |
| P3 | D21 has no implementing slice if found off | D21 probe in S13 exit; contingent S13b enables and validates it or records a dated owner deferral; S12 depends on S13b; matrix row D21 and tracker updated |
| P3 | REVIEW-R5 resolutions flagged | Gemini found them sound; no change |

Gemini's answers to the open questions: D11 AGREE (current registry grants per slice, non-author Codex or Claude holds binding acceptance, exact grant IDs shown before any change); D12 AGREE (unmodified EUPL-1.2/MPL-2.0 binary invocation acceptable; linking, vendoring or modifying needs an owner-signed waiver); D13 AGREE (owner host keeps the add-on ON and is exempt from C2; `lite` and add-on-OFF `ai-dev` carry C1-C5); D14 AGREE (owner designates a real 16 GB machine and a pinned model of at most 4 GiB; ratify budgets at S0, revise only with owner approval after measurement). Gemini's top risk, recorded: the branch is 49 commits behind `origin/main` while unguarded writers land, and Node pulled transitively by `ai-dev` members or a failed Postgres/Qdrant-free spike could stall MVP exit; rebase and owner-key provisioning gate the trust slices.

## Buy-in round 2 (2026-11-27)

Reviewed DESIGN.md sha256 `a6aa55bb4484841f8700c1334ed8555ea1579a2f67fe3f54dfacb3c7c5563029` (outputs `buyin2-gemini.out`, `buyin2-codex.out`). Revised DESIGN.md sha256 after this round: `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76`.

Gemini: PLAN_READY. All eight round-1 findings confirmed fixed. Two P3 notes, applied: D9 omitted S13b (now listed as "S13b (contingent)"); the owner-key issue note in the tracker now reads "S2 and S1c activation prerequisite". It also noted its local `sha256sum` could not run and it read the on-disk file.

Codex: REVISE. Round-1 findings (privileged RCE, DAG cycle, C2 target and supported-set shrinkage, waiver mode, provenance, owner key and D21) confirmed fixed; REVIEW-R5 disagreement resolutions accepted, none rejected. New findings:

| Sev | Finding | Fix (DESIGN.md section and tracker) |
|---|---|---|
| P1 | "Fail on any DNS or socket attempt" also rejects the loopback coordinator, switchboard and llama.cpp path J6 needs | "Offline journeys and installer runbook": J6 and the air-gapped VM test fail on external connections, external DNS lookups and network fetches; declared loopback and Unix-socket IPC is allowed and required, with an explicit allowlist of those endpoints. Acceptance row J6-J8 and the "False offline assurance" risk reworded to match |
| P2 | S1d still said "each supported profile" including `lite`, which arrives in S13; the tracker kept the wording | S1d validation is explicitly add-on-OFF `ai-dev` only in "Execution order" and the C2 policy; every `lite` closure and offline check is validated at S13. Tracker S1d `validation_goal` and `goal` reworded |
| P2 | Prose required S1c before S13 but the DAG and tracker omitted it | S1c added to S13 dependencies in the enumerated DAG, the S13 slice row and `tracker.json`; DAG restated acyclic: S0<-; S1<-S0; S1c, S1d, S2<-S1; S1b<-S2; S4, S4a<-S1b; S3<-S4; S13<-S3,S1d,S1c; S13b<-S13; S12<-all |
| P3 | Retain round-1 fixes; keep owner-host exemption distinct from supported-install compliance | Retained; no change |

Local: not run, power-gated.

D11-D14: AGREE from both Codex and Gemini. Codex notes: D11 check current per-slice grants, use an eligible non-author binding reviewer and record exact grant IDs; D12 unmodified binary invocation default, linking, vendoring or modification needs the owner waiver; D13 owner-host add-on ON is exempt from C2 while `lite` and add-on-OFF `ai-dev` keep C1-C5; D14 designate real 16 GB hardware and a pinned model of at most 4 GiB, ratify budgets at S0, owner approval for measured revisions. Gemini's notes are in round 1 and are consistent.

## Buy-in round 3 (2026-11-27)

Reviewed DESIGN.md sha256 `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76` (outputs `buyin3-codex.out`, `buyin3-gemini.out`). DESIGN.md is not changed by this round; the items below are recorded as FOLLOWUPS, not design edits.

- Codex: PLAN_READY_WITH_FOLLOWUPS. Round-2 findings all closed (local IPC allowed in J6; S1d scoped to add-on-OFF `ai-dev`; S13 depends on S1c; D9 includes S13b; both owner-key prerequisites in the tracker). Brief requirements and D-R5-1..6 covered; disagreement resolutions accepted except the numerical presentation in resolution 3. Top risk: declared boundaries and static checks could look complete before runtime admission and recovery are proven; S12 must require real refusal, crash and replay evidence.
- Gemini: PLAN_READY. Round-2 fixes confirmed; all 26 resolutions sound. Top risk: the branch is 49 commits behind `origin/main` while unguarded writers land, and two unverified prerequisites (owner-key provisioning gating S2 and S1c; Postgres/Qdrant-free persistence and transitive Node closures in `ai-dev`/`lite`) could stall S1d, S2 and S13.
- Local: not run, power-gated in all three rounds (cpu 84C). Not agreement.
- D11-D14: AGREE from Codex and Gemini (notes as in rounds 1 and 2).

FOLLOWUPS (not applied to the design text now):

| # | From | Followup | Owner slice |
|---|---|---|---|
| F1 | Codex P2 | The "overlap 7-16" range in DESIGN.md "Decision ownership matrix" and the "at least 7 overlaps, up to 16" wording in `ARCHITECTURE-SUMMARY.md` count ROWS. The defined metric is the sum of excess independent writers. Report two separate metrics: overlapping-row count, and writer total (sum of max(0, writers - 1)). Leave the writer total unknown, and drop 16 as an upper bound, until the S1 tool computes it; fix both documents | S1 (tool output and the amendment shipped with it) |
| F2 | Codex top risk | S12 acceptance must require real refusal, crash and replay evidence for each admission and recovery path, not declared boundaries or static checks alone | S12 acceptance (rows Q1, J1-J5) |
| F3 | Gemini P3 | `DESIGN.md` "Review r5 disposition" still says no lane has reviewed it: update with the buy-in record at the S0 freeze | S0 |
| F4 | Gemini P3 | Tracker issue entry mentions only round 1: refresh or close it at the S0 freeze | S0 |
| F5 | Gemini P3 | If S13b closes by a dated owner deferral for D21, state that S12 treats D21 as probed (non-UQ) under a dated deferral, not as live-enforced | S0/S1 (S13b row or S12 exit) |

Status: committed with the S1 code PR per the no-docs-only rule; local catch-up queued.

## Buy-in

Reviews come next. Reviewers compute `sha256sum` of `DESIGN.md` and `tracker.json` and record them here.

| lane | verdict | reviewed DESIGN.md sha256 | notes |
|---|---|---|---|
| codex | PLAN_READY_WITH_FOLLOWUPS (round 3) | `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76` | round 3 PLAN_READY_WITH_FOLLOWUPS (F1, F2); rounds 1 not run (cooldown), 2 REVISE applied; D11-D14 AGREE |
| gemini | PLAN_READY (round 3; round 2 PLAN_READY, round 1 REVISE) | `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76` | P3 followups F3-F5; D11-D14 AGREE |
| local | not run | | power-gated in all three rounds (cpu 84C); not agreement |
| claude-author | | | |

## S0 freeze record (2026-11-27)

Frozen subject (verified with `sha256sum` when this record was written; REVIEW-R4.md is the rev 4 text from `af2a99023`, unchanged):

| file | sha256 |
|---|---|
| `DESIGN.md` | `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76` |
| `tracker.json` | `ac7d28ade1e41ff2c7f1cd04892cb7259aa890e311aec83ff3314e5354e4ee23` |

Both match the hashes the Codex round 3 and Gemini round 3 buy-in rows above bind to. This section is the only edit made to REVIEW-R5.md at S0, and it is outside the bound files.

### Owner answers, 2026-11-27 ("defaults")

| Id | Answer recorded |
|---|---|
| D11 | Binding acceptance comes from the lane-eligibility registry, per slice. A non-author Codex or Claude lane holds it, and the grant ID is recorded with the acceptance (grant IDs below). |
| D12 | Invoking an unmodified EUPL or MPL binary is allowed. Linking, vendoring or modifying needs an owner-signed waiver. |
| D13 | The owner's ai-dev host keeps the remote-lanes add-on and is exempt from C2. The `lite` profile and ai-dev with the add-on OFF carry C1-C5. |
| D14 | The owner names the 16 GB machine and a pinned model of at most 4 GiB. Budgets are ratified at S0. The owner approves any revision of them. |

Budgets are ratified as written in DESIGN.md section "`lite` profile (rev5)"; the machine and the pinned model are still to be named by the owner before S13 measures anything.

### D-R5-1..6, approved 2026-11-27

Approved as written in DESIGN.md (rows D-R5-1 to D-R5-6 of the "Binding owner decisions" table): local-only landing waiver (D-R5-1); C2 for the supported install with a remote-lanes add-on (D-R5-2); Rust contract guard in S1 (D-R5-3); `aq-land-queue` as the sole queue, activated only after S2 (D-R5-4); upstream register (D-R5-5); `lite` profile (D-R5-6).

### Followups, to be applied in the next re-reviewed amendment

Not applied now, so the buy-in hash stays valid.

| # | Status |
|---|---|
| F1 | Tool side shipped in S1A: `harness-contracts decisions --count` reports overlapping rows and the excess-writer total separately and prints the writer total as unknown. The wording fix in DESIGN.md "Decision ownership matrix" and in `ARCHITECTURE-SUMMARY.md` is part of the amendment. |
| F2 | S12 acceptance wording (refusal, crash and replay evidence per admission and recovery path): amendment. |
| F3 | Replace the "Review r5 disposition" text that says no lane has reviewed rev 5 with the buy-in record: amendment. |
| F4 | Refresh or close the tracker issue entry that mentions only round 1: amendment (tracker.json is bound, so this waits for the re-reviewed amendment). |
| F5 | If S13b closes by a dated owner deferral for D21, S12 treats D21 as probed (non-UQ) under that deferral, not as live-enforced: amendment. |

### S1 author substitution (Rule 18)

The S1 plan reserves Codex as author for the Rust crate and CI. Codex was usage-limited twice on 2026-11-27, so S1 is authored by Claude Sonnet (explicit `sonnet` override, headless implementer). The reason is availability, not a capability gap. The S1 reviewer must be a non-author lane chosen from the registry at review time: Codex when available, else Gemini (reviewer), else Opus (same vendor, different model: last resort, flagged). Sonnet holds a reviewer grant but may not review this slice (never self-review). The evidence document for S1 repeats this record.

### Lane-grant reconciliation (rev 4 D0 is stale)

Read from `config/lane-eligibility-registry.json` (schema_version 1, default TTL 45 days) on 2026-11-27; the registry was not changed. The registry carries no separate grant-ID field, so a grant ID here is `<lane>/<role>@<measured_at>`. Every grant below cites the same evidence: `.agents/plans/unified-program/LANE-GRANT-RENEWAL-OWNER-RATIFICATION-20261125.md` (owner-ratified renewal 2026-11-25, chat door).

| Role | Lane | Grant ID | Expires |
|---|---|---|---|
| reviewer | codex | `codex/reviewer@2026-11-25T09:36:45.093599Z` | 2027-01-09 |
| reviewer | gemini | `gemini/reviewer@2026-11-25T09:36:45.522531Z` | 2027-01-09 |
| reviewer | opus | `opus/reviewer@2026-11-25T09:36:46.174473Z` | 2027-01-09 |
| reviewer | sonnet | `sonnet/reviewer@2026-11-25T09:36:46.364768Z` | 2027-01-09 |
| binding-acceptance | codex | `codex/binding-acceptance@2026-11-25T09:36:44.898125Z` | 2027-01-09 |
| binding-acceptance | opus | `opus/binding-acceptance@2026-11-25T09:36:45.981481Z` | 2027-01-09 |
| binding-acceptance | local | `local/binding-acceptance@2026-11-25T09:36:45.707681Z` | 2027-01-09 |

Differences from rev 4 D0 and from the DESIGN.md lane notes:

- Gemini holds `reviewer` but no `binding-acceptance` (consistent with the #871 revocation of Gemini's orchestrator and binding-acceptance grants); `antigravity` is retired with its implementer block kept.
- Sonnet holds `reviewer` but no `binding-acceptance`, so under D11 the Claude binding-acceptance lane is Opus.
- `local` is registered for `binding-acceptance` (and `architect`, `implementer`, `rsi`) but has no `reviewer` grant. DESIGN.md says local is never trust-critical; D11 ("non-author Codex/Claude lane") means the registry entry for local is not used for binding acceptance on this program. Follow-up for the orchestrator: decide whether to withdraw it (registry change, not made here).
- `codex` also holds architect, implementer, orchestrator and rsi; `gemini` holds architect, research and rsi; `opus` holds architect, implementer, orchestrator and rsi; `sonnet` holds implementer and rsi.

### Freeze status

S1c (upstream register), S1d (C1/C2/C3/C5 gates and the Node-free supported install) and S13 (`lite` profile and offline installer runbook) are frozen in scope as written in DESIGN.md. Their entry conditions stay as designed: S1c and S1d depend on S1, S13 depends on the D14 machine and pinned-model answer. PLAN_READY_WITH_FOLLOWUPS stands for the bound DESIGN.md and tracker.json.

## Amendment rev5.1 (S1, 2026-11-27)

Rev 5.1 amends the reviewed `DESIGN.md` and `tracker.json` once, as the S0 freeze record planned ("Followups, to be applied in the next re-reviewed amendment"). It ships in the S1 code PR and needs re-review against the new hashes below. Scope is the followups F1, F3, F4, F5 and path hygiene only; no design decision, slice, owner decision or acceptance criterion changed. F2 (S12 acceptance wording) is not applied here: it stays an S12 followup.

| File | Old sha256 (rev 5, reviewed in round 3) | New sha256 (rev 5.1) |
|---|---|---|
| `DESIGN.md` | `8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76` | `c759dbda5250205e7784e641fbad095364bf48f1c5873ea7052fb788604e3694` |
| `tracker.json` | `ac7d28ade1e41ff2c7f1cd04892cb7259aa890e311aec83ff3314e5354e4ee23` | `e1048557770a912fa321df1e7b5830616ad1444cfc4e79b1d290662f5eb98746` |

Every change:

1. F1, `DESIGN.md` "Decision ownership matrix", counting rule: "overlap = sum over decisions of max(0, ...)" now names that sum the writer total and says the number of overlapping rows is a separate metric.
2. F1, same section, "Reported as": replaced "overlap at least 7 verified (up to 16 if ...)" with two separate metrics: overlapping rows (7 verified, 4 carried, 5 unverified) and the writer total (unknown until every row has a verified writer list; 17 rows lack one; no upper bound; the "up to 16" is dropped). The orphan sentence is unchanged. The same wording fix is in `docs/architecture/ARCHITECTURE-SUMMARY.md`, which is outside the bound files.
3. F3, `DESIGN.md` "Review r5 disposition": replaced "Buy-in is pending: no lane has yet reviewed this DESIGN.md" with the buy-in record (Codex PLAN_READY_WITH_FOLLOWUPS and Gemini PLAN_READY at the old sha, local not run, D11-D14 "defaults", D-R5-1 to D-R5-6 approved) and a pointer to this section.
4. F4, `tracker.json`: the issue entry that mentioned only Gemini round 1 now records rounds 1-3 and says the rev 5.1 amendment needs re-review. No other tracker field changed (items, deps, phases and detection are byte-identical).
5. F5, `DESIGN.md` S13b row: added "If S13b closes by a dated owner deferral, S12 treats D21 as probed (non-UQ) under that dated deferral, not as live-enforced."
6. Path hygiene for `scripts/governance/tier0.d/check-plan-paths.py` (54 findings before this change; the checker is unchanged and now passes on all five staged plan files). By kind:
   - P0/<file>.md for the five Phase 0 evidence files became `docs/harness-first/evidence/2026-11-27-arch-rev5-phase0/<file>.md` (they now exist there).
   - P0/review-codex.out and P0/review-gemini.out became `.agents/delegation/outputs/arch-consolidation-rev5/review-codex.out` and `.../review-gemini.out` (untracked outputs, not copied).
   - Multi-value `:line` suffixes the checker cannot strip (config/ci-checks.json:2125,2237, nix/data/profile-system-packages.nix:7,96,112,128, nix/home/base.nix:1616-1634,1956,2155, and the two :17,34 and :25,58 suffixes on the evidence files) became a bare path plus "(lines ...)"; the same `profile-system-packages` change is in this file.
   - Relative `tier0.d/...` tokens became `scripts/governance/tier0.d/...` (`check-contracts.sh`, `check-anti-fabrication.sh`, `check-upstream-register.sh`; the last also marked "(new)").
   - Not-yet-existing future paths are marked with the checker's `(new)` convention: `scripts/upstream/REGISTER.json` (six lines), `contracts/upstream/register/v1.schema.json`, `docs/operations/OFFLINE-INSTALL.md`, `scripts/governance/tier0.d/check-upstream-register.sh`.
   - The "Problem addendum" mention track/REGISTER.json is corrected: the register is `scripts/upstream/REGISTER.json` (new); a register under a `track/` directory is impossible because `scripts/upstream/track` is a file.
7. Beyond the bound files: `ARCHITECTURE-SUMMARY.md` in this directory is now a pointer to `docs/architecture/ARCHITECTURE-SUMMARY.md`; `.plan-classification.json` was added so `test-plans-index.py` classifies this plan directory; the `scripts/governance/tier0.d/check-anti-fabrication.sh` path in this file was made repo-relative.

## Buy-in on rev5.1 (amendment)

| Lane | Verdict | Reviewed DESIGN.md sha256 | Notes |
| --- | --- | --- | --- |
| codex | PLAN_READY_WITH_FOLLOWUPS | c759dbda5250205e7784e641fbad095364bf48f1c5873ea7052fb788604e3694 | Changes stay within F1/F3/F4/F5 and citation hygiene; F1 correct. P3: review outputs are untracked local files, so preserve them as durable evidence. |
| gemini | PLAN_READY | c759dbda5250205e7784e641fbad095364bf48f1c5873ea7052fb788604e3694 | No findings. Same top risk about untracked review outputs. |
| local | not run | n/a | Power-gated (CPU >= 80C) in every round; not agreement; catch-up queued. |

Disposition of the shared P3: the reviewer replies (delta reviews and buy-in rounds 1, 2, 3 and rev5.1) are copied verbatim, from the Verdict line on, to `docs/harness-first/evidence/2026-11-27-arch-rev5-phase0/reviews/`. DESIGN.md citations still name the original output paths, so the bound hash is unchanged. Repointing them to the evidence copies is follow-up F6, for the next re-reviewed amendment.
