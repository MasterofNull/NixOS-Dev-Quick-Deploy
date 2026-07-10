# AQ-OS Refoundation Threat Register

**Status:** DRAFT; controls are requirements, not claims of current enforcement  
**Rule:** a policy document alone is not a control. Every row needs prevention, detection,
intervention and an executable recovery test.

| Threat | Prevention | Detection | Operator/system intervention | Recovery test |
|---|---|---|---|---|
| Reward corruption | Certified isolated scorer; hidden golden data; infra abstention; deduped samples; lineage-gated promotion | Certification state, duplicate rate, error class and score/distribution drift | Freeze promotion; quarantine run, scorer and dataset | Inject readable golden data, duplicates, timeouts and inverted scorer; promotion blocks and last model remains active |
| False consensus | Exact subject hashes; eligible typed contributions; independent-lineage quorum; no self-review or status-derived approval | Invariant validator; human/machine hash mismatch; abstain-only and proxy-quorum alerts | Mark `CORRUPT`, suspend authorization, reopen/adjudicate | Replay current false lock plus all-reject, empty, self-review, proxy-family and late-reject fixtures |
| Split-brain authority | One authority per object; one writer; all projections carry source revision/hash | Compare authoritative and projection revisions/content hashes | Freeze non-authoritative writers; rebuild projections | Corrupt Redis/Qdrant/Markdown/cache in isolation; restart and rebuild identical state from authority |
| Capability escalation | Deny-by-default scoped leases checked at orchestration and tool execution; short expiry; distinct principals | Denied-action audit, toolset delta, stale lease and unknown producer | Revoke lease/identity; terminate task; isolate sandbox | Strip a tool, then attempt reacquisition, direct-executor bypass and expired lease use; all denied and attributed |
| Prompt/data exfiltration | Data classification; remote-boundary redaction; untrusted retrieval; attributed egress allowlist | Canary/secret scans, destination identity and unattributed-egress alert | Cancel call; revoke route/lease; quarantine trace | Inject a secret and tool prompt through retrieval; no remote payload/egress contains it and evidence remains local |
| Autonomous backlog amplification | Bounded queues, producer quotas, admission/backpressure and review/WIP budgets | Queue depth/age, producer-consumer ratio, oldest approval and cancellation lag | Pause producers; shed low priority; protect interactive capacity | Flood isolated queue above consumer capacity; bound holds, excess is rejected/backpressured, drain has no duplicates |
| Metric gaming / green theater | Typed evidence algebra; outcome-linked denominators; versioned semantics | Zero denominator, missing/stale source, adoption/outcome divergence and partial composites | Block pass/automation; display stable reason and remediation | Feed 100% adoption with no outcome, missing trace, stale QA and presence-only health; outcome is `BLOCKED`, never pass |
| Resource collapse | Admission by host budget; concurrency/memory/thermal ceilings; priorities and shedding order | RAM/APU/thermal/latency/queue pressure by workload class | Cancel eval/index first; throttle background; preserve operator path | Co-run inference/eval/index/trace in constrained test; verify declared shedding and interactive recovery |
| Strangler abandonment | Every shim has owner, use/divergence metrics, deadline, removal condition and expiring exception | Old/new traffic, divergence, deadline breach and zero-use duration | Block new callers; disable old writes; escalate expiry | After defined clean cycles, disable shim and prove no consumers; injected legacy call fails explicitly and is measured |
| Operator bottleneck or bypass | Risk-tiered bounded approvals, expiry/delegation and non-bypassable privileged gates | Approval age, override attempts and approver concentration | Reassign/expire/escalate; pause privileged queue | Remove primary operator: low-risk delegated work continues, high-risk work blocks, bypass is rejected |
| Supply-chain compromise | Pinned hashes/signatures/SBOM, deny-by-default intake and provenance for models/skills/MCP/flake/generated artifacts | Verification mismatch, unpinned input and unexpected artifact hash | Quarantine; revoke capability; return to last admitted version | Substitute modified GGUF, skill, flake or generated artifact; admission fails and known-good restore verifies |
| Portability theater | Claims tied to declared hardware classes and continuously tested benchmark targets | Coverage matrix, missing-target age and benchmark/config drift | Downgrade claim; block release label or unsupported activation | Release without second-target evidence cannot claim portability; restored evidence reproduces benchmark |

## Cross-cutting invariants

- Every alert links the immutable run/evidence ID and stable reason code; no free-form error text is a
  metric label.
- Every intervention is observable, attributable, bounded and reversible where safety permits.
- Recovery tests run against isolated stores or disposable fixtures. They cannot modify production
  PULSE/RESUME, registries, QA pointers, Redis, Qdrant or Postgres.
- A successful availability check cannot satisfy effectiveness, safety, trust or durability claims.
- A degraded or blocked state is a valid operational mode; silent fallback is not.

## Delivery and recovery ownership

Only rows tagged C0 gate Cycle 0. Later tests are design requirements and must not be run destructively
against the live host during this cycle.

| Threat | Control owner | Delivery | Recovery objective and pass assertion |
|---|---|---|---|
| Reward corruption | eval/learning owner | Cycle 3 | Within one promotion window, restore last admitted model/scorer, quarantine poisoned lineage and rerun a clean certified eval |
| False consensus | collaboration decision owner | **C0.1** | Within 15 minutes, preserve corrupt bytes, reconstruct new revision, obtain fresh reviews/authorization and prove assignment works once |
| Split-brain authority | architecture/state owner | **C0.3 discovery; Cycle 1 recovery** | C0 reports every claim honestly; Cycle 1 rebuilds projections from selected authority with equal hashes |
| Capability escalation | security/policy owner | Cycle 2 | Revoke identity/lease within 60 seconds, terminate task, restore clean sandbox and prove bypass remains denied |
| Prompt/data exfiltration | privacy/security owner | Cycle 2 | Quarantine trace, rotate exposed secret, sanitize evidence and prove canary no longer crosses boundary |
| Backlog amplification | scheduler/queue owner | Cycle 3 | Resume from checkpoint, drain within declared SLO, preserve interactive reserve and execute no duplicate |
| Metric gaming/green theater | evidence/report owner | **C0.2** | Replace invalid evidence with a verified run and observe `BLOCKED → PASS/FAIL` deterministically without manual score edits |
| Resource collapse | SRE/capacity owner | Cycle 3 | Disposable cgroup load sheds in declared order and interactive p95 returns to budget within 5 minutes |
| Strangler abandonment | migration owner | **C0.3 contract; later removals** | Restore from a failed shim disable, then remove only after clean-cycle evidence with no hidden caller |
| Operator bottleneck/bypass | owner/governance | Cycle 2 | Restore delegated approval authority from audited policy while privileged work remains blocked until valid approval |
| Supply-chain compromise | platform/security owner | Cycle 2/5 | Quarantine input, restore last admitted artifact and reproduce provenance/health without trusting the substitute |
| Portability theater | release owner | Cycle 5 | Roll back unsupported activation, restore declared host profile and reproduce its benchmark before restoring claim |

Threat evidence IDs are assigned when executable fixtures land. Missing evidence IDs mean
`research_required`, never passing controls.

## Deferred decisions

- Per-workload cryptographic identity mechanism; Cycle 0 uses truthful
  `ORCHESTRATOR_ATTESTED` attribution and rejects `UNVERIFIED` quorum.
- Exact metric windows, sample minima, freshness limits, host resource ceilings and retention values;
  these require baselines rather than inherited defaults.
- Critical human-override policy and whether a second human is required.
- Nix packaging and resource comparison for RFC 8785 support, CAS implementation and Cycle 1 storage.

`VERDICT: REQUEST_REVISION — the threat controls are falsifiable, but identity, thresholds, retention
and critical human-override policy require ratification before implementation.`
