# AQ-OS Track S — Defensive Security Factory Program Plan

**Status:** PREPARED / NO LIVE ACTIVATION  
**Parent:** `.agent/PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md`

## Program gates

1. S0 contracts and candidate intake must pass independent architecture, security,
   SRE, privacy, and license review.
2. Existing admitted scanners are used before any new runtime is considered.
3. Active behavior remains impossible until S2 supplies a valid signed owned-target
   scope receipt from the existing `t3mp3st` scope authority and an independently
   tested target/egress guard. Track S creates no parallel receipt authority.
4. Findings cannot reach remediation, disclosure, or bounty state without typed
   evidence and independent review.
5. Every live component meets the Service Coverage contract.

## Candidate intake work

### Piyaz

- Pin a commit; inventory plugins, MCPs, hooks, network/API calls, auth, database
  writes, telemetry, and hosted data flow.
- Compare its task graph/claim/review invariants with AQ-OS AAF, PENDING/RESUME,
  round manifests, Agent Connection Reliability, and the human-readable progress tracker.
- Audit its vector, RAG, and DAG lifecycle patterns against AQ-OS collection ownership,
  provenance, retention, graph integrity, rebuild, drift, and garbage-collection contracts.
- Route accepted patterns to their owning AQ-OS tracks; Track S records intake evidence
  and security constraints but does not become an A2A, tracker, vector, RAG, or DAG authority.
- Prefer pattern extraction or an adapter over adding a second lifecycle authority.
- Freeze the exact source and license digests and maintain a clean-room boundary
  between upstream review notes and any independently implemented AQ-OS pattern.

### Sn1per

- Keep runtime denied and source outside the active workspace.
- Review only through a pinned, no-execute source snapshot plus SBOM/license scan.
- Treat `sudo install.sh`, privileged containers, exploit modes, update commands,
  target discovery, brute force, and external integrations as prohibited surfaces.
- Freeze the exact EULA digest and obtain an owner/legal disposition before any
  pattern use; do not treat this plan's summary as legal advice.

### RAPTOR loop hunt

- Pin source and inventory all skills, hooks, prompts, commands, subprocesses,
  network behavior, write surfaces, loop termination, and model/tool authority.
- Freeze and review its license; a missing/ambiguous license keeps the candidate
  quarantined.
- Extract defensive reasoning/checklist patterns into local, closed, reviewable
  skills; never import upstream prompts directly into a privileged agent context.
- Require bounded iterations, explicit target scope, resource budgets, evidence
  schemas, and deterministic stop conditions.

### BOD 26-04

- Freeze the directive and implementation-guidance versions used.
- Map public exposure, KEV, exploit automatability, technical impact, evidence
  preservation, remediation timing, and reporting into Track S contracts.
- Mark voluntary AQ-OS adoption separately from legal/FCEB applicability.
- Freeze source URL, retrieval time, content digest, scoring truth table,
  unknown-value behavior, deterministic tie-break, and evidence-preservation
  override before the resolver is implemented.

## Slice sequence

### S0-A — intake truth

Exact future implementation ceiling: three repository paths only:

1. CREATE `config/schemas/agent-capability-intake-candidates.schema.json`;
2. MODIFY `config/agent-capability-intake-candidates.json`;
3. MODIFY `scripts/testing/test-capability-intake.py`.

The schema must close every current registry boundary and enumerate categories,
maturity, priority, state, review status, install type, permission classes, risk
flags, and bounded strings/arrays without invalidating the 11 existing records.
Add Piyaz and RAPTOR as `proposed/source-audit-required`; add Sn1per as
`quarantined/no-runtime`. Metadata-only audit results must explicitly report
`incomplete` for source/license/SBOM/runtime claims because S0-A authorizes no clone,
download, install, or execution.

Acceptance requires: all 14 records schema-valid; unknown keys/types/enums rejected;
missing pin/license/SBOM/runtime evidence cannot produce acceptance; current 11
admission results do not silently change; public/active tool permissions stay denied;
focused tests include compatibility and negative vectors; `git diff --check` passes.
Rollback is removal of the three proposed records plus the exact schema/test changes
under a separately reviewed revert—not disabling or weakening validation.

### S0-B — defensive contracts

- Add the five closed schemas named by the PRD.
- Add golden accept/reject vectors, including public-target, redirect, DNS-rebind,
  expired-scope, destructive-mode, prompt-injection, and report-redaction cases.
- Add a pure BOD-style risk resolver.

### S1 — passive security pipeline

- First audit every already-enabled scanner against Service Coverage: real
  integration-path QA, visible dashboard state, bounded metrics, and rollback.
  Existing admission alone is not delivery evidence.
- Orchestrate existing scanners in isolated read-only jobs.
- Normalize/deduplicate findings; preserve scanner evidence and SBOM identity.
- Add `aq security scan/status/report` projections, Phase-0 checks, and Command
  Center cards.

### S2 — owned lab validation

- Disposable VM/container/network namespace only.
- Default-deny egress and exact target allowlist.
- Signed receipt, bounded rate/runtime/output, immutable evidence, kill switch,
  and no production credentials.

### S3 — tripwires and response

- Honeyfiles/tokens/services with no privilege and no production-auth validity;
  ingress-only bounded collectors with no callback path.
- AppArmor/audit/systemd/file-integrity/egress detections.
- Alert -> evidence -> isolate -> revoke -> reviewed remediation.
- Explicitly no hack-back, outbound beacon to attacker, or identity hunting.

### S4 — disclosure and rewards

- Program-policy registry, scope freeze, duplicate search, report templates,
  redaction, embargo, owner approval, and submission ledger.
- Private duplicate-search boundary, policy-change revalidation, immutable owner
  approval, authenticated embargo clock, and accidental-submission retraction.
- Track possible rewards without guaranteeing or autonomously claiming them.

### S5 — continuous risk remediation

- KEV/public-exposure/automatability/impact prioritization.
- Patch-in-lab, independent regression, phased deployment, rollback, and SLO audit.

## Immediate next gate

Prepare S0-A as a contract/config-only authorization with no source clone, package
install, network scan, active target, plugin enablement, external submission, or
runtime change. Independent flagship review must precede owner activation.
