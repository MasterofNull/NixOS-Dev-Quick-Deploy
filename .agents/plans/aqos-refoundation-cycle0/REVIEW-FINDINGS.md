# AQ-OS Refoundation Cycle 0 — Adversarial Review Findings

**Package root under review now:**
`2b905b244f97d0bbd1560d779e0e4cbdc7d7a923920e2821397c22d71c608a83`
**Review status:** no independent review yet targets this root. Reviews below targeted its predecessor and
are amendment evidence, not approval.

## Review provenance

| Lane | Result | Quorum effect |
|---|---|---:|
| Architecture/parity expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Trust/evidence/security expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Execution/QA expert workstream | `REQUEST_REVISION` | same Codex family; zero independent weight |
| Original local/Qwen lane | failed after 2,233.4 s; empty output; transient switchboard refusal | zero approval weight; training/reliability evidence |
| Antigravity/Gemini | request file exists; receipt/response unverified | zero approval weight |
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

1. Owner has not ratified the proposed authorization, quorum, waiver, proxy or critical-human policy.
2. No independent model-diverse reviewers have reviewed the current package-root hash.
3. Local lane failure and Antigravity non-response must be formally closed/waived without becoming votes.
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
