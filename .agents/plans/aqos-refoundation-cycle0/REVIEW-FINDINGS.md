# AQ-OS Refoundation Cycle 0 — Adversarial Review Findings

**Package root under review now:**
`0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f`
**Review status:** Gemini reviewed predecessor root `2b905b24…` and Anthropic reviewed earlier
review-pin bytes; both returned `APPROVE_WITH_CHANGES`. This root incorporates their amendments, so
fresh `APPROVE` reviews are required and neither prior conditional verdict authorizes work.

## Review provenance

| Lane | Result | Quorum effect |
|---|---|---:|
| Architecture/parity expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Trust/evidence/security expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Execution/QA expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Original local/Qwen lane | failed after 2,233.4 s; empty output; transient switchboard refusal | zero approval weight; training/reliability evidence |
| Local/Qwen seeded retry | substantive F1–F7 review with preserved dissent | explicitly zero approval weight; lane-readiness evidence |
| Anthropic/Fable 5 | `APPROVE_WITH_CHANGES` on predecessor/review-pin bytes | independent findings; zero current approval weight |
| Antigravity/Gemini | `APPROVE_WITH_CHANGES` on root `2b905b24…` | independent findings; old conditional verdict never counts |
| Claude slot | Codex-orchestrator proxy | same lineage; zero diversity |

## Amendments applied from adversarial review

- Added full planning decision state transitions, cascades, assignment invariant, recovery record and a
  positive/cascade fixture in `STATE-CONTRACT.md`.
- Proposed exact safe owner defaults while leaving their acceptance explicitly blocking.
- Replaced ambiguous RFC 8785 preference with versioned dependency-free `aq-canonical-json-v1` after
  live Nix evaluation found no `python313Packages.jcs` attribute.
- Added a machine-readable evidence manifest and externally hashed package descriptor.
- Corrected evidence classes, exact timestamps and local terminal failure provenance.
- Added required-claim matrix and edge semantics for N/A, zero claims, optional-only, conflict,
  unauthorized producer, insufficient sample, proxy and automation.
- Changed C0.3 from forced singleton authority to honest `SINGLE | SPLIT_BRAIN | UNKNOWN | UNOWNED`
  discovery with blocking adjudication.
- Added external pattern, build/adopt, full strangler and consolidation/deletion comparisons.
- Froze the C0.2 current consumer surface and made expansion require plan amendment.
- Defined non-circular QA hashing, start-sequence pointer ordering, lock/fsync/CAS semantics, privacy,
  deterministic retention conflict behavior and live-writer exclusivity.
- Named Phase-0 check IDs, existing dashboard/report surfaces, alert/operator actions, deployment order,
  rollback order and reproducible performance measurement method.
- Tagged threats by delivery cycle, owner and restoration assertion so later destructive tests do not
  gate or run during Cycle 0.

## Remaining blocking findings

1. Owner governance policy is ratified by `OWNER-POLICY-RATIFICATION.md`/`d247f7f0`; that record
   explicitly leaves plan ratification and implementation authorization open.
2. Independent Anthropic/Gemini reviews supplied amendments, but the superseding package root needs
   fresh explicit `APPROVE` reviews; conditional verdicts carry zero approval weight.
3. Local lane failure must be formally closed/waived without becoming a vote.
4. Inter-slice contracts are specified but not acknowledged against exact hashes by implementer and
   independent reviewer.
5. File ownership/exclusive-work preflight for future C0 production surfaces is not established in the
   shared concurrent worktree.
6. Evidence thresholds, freshness windows, sample minima, telemetry roots and retention ownership need
   measured owner acceptance before C0.2 implementation.
7. The bounded writer/reader scan is complete and proves all ten broad domains split-brain; C0.3 must
   still adjudicate every target authority, owner and resolution deadline.
8. Existing dashboard governance surface for C0.1/C0.3 must be named during exact implementation scope;
   no new panel is authorized.
9. Package root records a dirty shared-tree commit; a later edit, owner decision or evidence append
   creates a new root and invalidates all reviews.

## Review verdict

`VERDICT: REQUEST_REVISION — the revised package closes the major semantic contradictions and is ready
for genuine independent review, but owner policy, model diversity, thresholds, inter-slice sign-off and
workspace ownership still block ratification and implementation.`
