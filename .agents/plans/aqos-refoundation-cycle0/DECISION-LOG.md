# AQ-OS Refoundation Cycle 0 — Decision Log

**Status:** DRAFT; entries are proposed dispositions pending review of exact artifact hashes.

| ID | Disposition | Decision and rationale |
|---|---|---|
| D-001 | Accept | AQ-OS is a local-first NixOS control plane for bounded, replayable, operator-governed agent work—not a chatbot, AGI persona, script collection or microservice showcase. |
| D-002 | Accept | Cycle 0 repairs truth only and contains exactly C0.1 consensus/review truth, C0.2 evidence/effectiveness truth and C0.3 authority/retirement inventory. |
| D-003 | Accept | `direction_ratified`, `plan_ratified` and `implementation_authorized` are separate subject-hash-bound decisions; no state implies the next. |
| D-004 | Accept | Keep the four-plane model as an operator explanation, while durable lifecycle truth belongs to one control-plane authority. |
| D-005 | Accept | Target a modular monolith plus isolated workers before considering a microservice fleet. |
| D-006 | Hypothesis | Existing Postgres plus transactional outbox is the leading Cycle 1 authority, pending C0.3 restore, resource, failure, migration and ownership evidence. |
| D-007 | Accept | Redis is ephemeral/rebuildable coordination and Qdrant is a semantic projection. Neither is workflow/evidence authority. |
| D-008 | Accept | Switchboard owns model execution; the control plane owns policy and workflow. Direct generation paths are measured retirement candidates. |
| D-009 | Accept | Hashes prove byte integrity only. Producer attribution and authorization are distinct; Cycle 0 may honestly use `ORCHESTRATOR_ATTESTED`, never pretend shared HMAC is independent identity. |
| D-010 | Accept | Immutable QA run artifacts are C0.2 evidence; the `latest` pointer and dashboard are projections. C0.3 must ratify final authority/retention ownership. |
| D-011 | Accept | Compatibility expires after two defined clean release cycles or 90 days, whichever comes first, unless an evidence-backed owned exception has an expiry. |
| D-012 | Reject | Exactly-once claims, lane-status consensus, prose-derived approval, self-review quorum, mutable shared latest artifacts and missing-data passes. |
| D-013 | Reject | New config, CLI, document, service or feature that has no consolidation/retirement effect. |
| D-014 | Defer | Postgres runtime migration, new broker, NATS, Temporal, SPIFFE/SPIRE, object-store daemon, SPA rewrite, resident-model changes, multi-node/fleet and portability claims. |
| D-015 | Defer | F2.5 activation, learning-loop industrialization, payload consolidation and one-API migration until Cycle 0 makes their evidence and authority trustworthy. |
| D-016 | Accept | Cycle 0 canonical structured bytes use versioned restricted `aq-canonical-json-v1`; RFC 8785 is deferred because the live Nix package lookup found no `python313Packages.jcs` attribute. |
| D-017 | Accept | C0.3 records observed `SINGLE`, `SPLIT_BRAIN`, `UNKNOWN` or `UNOWNED` authority honestly; it may not invent a provisional singleton to satisfy validation. |
| D-018 | Proposed owner default | Implementation authorization is owner-only; waiver supplies no approval weight; quorum requires two model families and two execution principals with assurance ≥`ORCHESTRATOR_ATTESTED`, all required lanes terminal and no eligible reject. |
| D-019 | Accept | QA artifact digest is external pointer/sidecar metadata over immutable canonical payload bytes; `latest` ordering uses a lock-protected start sequence allocated by the QA evidence producer, not completion time. |
| D-020 | Accept | Read-only C0.3 research confirms all ten broad lifecycle domains are currently `SPLIT_BRAIN`; target singleton selection remains an adjudicated implementation output, not a discovery precondition. |
| D-021 | Accept | The owner-requested actual authority and exact consolidation candidate deliverables are satisfied for planning by `CURRENT-AUTHORITY-INVENTORY.md`; registry enforcement, owners and deadlines remain C0.3 acceptance work. |

## Minority objections and resolutions

1. **Immutable QA artifacts may create authority before C0.3.** Proposed resolution: an invocation's
   producer-owned immutable artifact is evidence; shared pointers and displays are explicitly
   projections. C0.3 ratifies final ownership before Cycle 1.
2. **A fixed shim deadline may force unsafe removal.** Proposed resolution: allow only explicit,
   expiring, evidence-backed exceptions with owner and reviewed renewal.
3. **Requiring every configured lane may block progress during provider failure.** Unresolved: formal
   closure/waiver policy must preserve model diversity and expose the waiver; absence cannot become a
   vote.
4. **A restricted Cycle 0 canonical encoder is less interoperable than RFC 8785.** Resolution: version
   `aq-canonical-json-v1`, forbid floats/non-ASCII keys, ship cross-language golden vectors, and revisit
   RFC 8785 only through a new subject/schema revision.
5. **The clean-sheet target may over-centralize Postgres.** Unresolved: C0.3 must compare operational
   recovery and resource cost with simpler single-host alternatives; semantic projections must remain
   disposable regardless.

## Owner/governance questions

- Who can issue or delegate `implementation_authorized`?
- What independent model-family minimum and required-lane roster applies?
- Does a formally unavailable lane require owner waiver, and when does that force a new round?
- Is a second human required for critical override, promotion or privileged execution?
- What privacy classification, retention owner and GC policy apply to evidence artifacts?
- What measured freshness, denominator and SLO thresholds replace current inherited defaults?
- Which concurrent work currently owns C0 file surfaces?

## Ratification record

No ratification is recorded. The current machine `CONSENSUS_LOCKED` state is known-invalid evidence.
Ratification must reference the exact PRD, plan, threat register and evidence-manifest hashes after all
blocking amendments are resolved.

`VERDICT: REQUEST_REVISION — core decisions converge, but authorization policy, quorum/waiver policy,
identity assurance and evidence retention remain owner-level decisions.`
