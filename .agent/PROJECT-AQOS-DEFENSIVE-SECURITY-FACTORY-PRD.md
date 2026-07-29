# AQ-OS Defensive Security Factory PRD

**Status:** DRAFT / INTAKE-ONLY  
**Track:** S — cross-cutting defensive security, vulnerability response, and responsible disclosure  
**Authority:** owner-controlled, deny-by-default; no external target is in scope without a separate written scope receipt

## 1. Intent

Add a measured defensive-security factory to AQ-OS that can inventory, probe, test,
reproduce, remediate, verify, monitor, and responsibly report vulnerabilities in:

1. this repository and its dependencies;
2. the owner's locally hosted systems and packages;
3. disposable lab replicas of those systems; and
4. third-party assets only when an applicable bug-bounty or maintainer program
   supplies explicit written authorization and machine-verifiable scope.

The factory turns findings into fixes and durable regression controls. It does not
turn AQ-OS into an unconstrained offensive operator.

## 2. Non-negotiable boundary

- Default mode is passive/offline analysis.
- Active probes require a signed scope receipt naming exact targets, methods,
  time window, rate limits, data-handling rules, and stop contacts.
- Track S consumes the existing `t3mp3st` scope validator/receipt authority (or
  a separately reviewed successor); it must not create a second signer, target
  normalizer, receipt store, or active-testing gateway.
- The canonical receipt binds its schema/subject hash, signer trust root, nonce,
  audience, issuance/expiry, revocation epoch, normalized target set, ports and
  protocols. Verification rejects replay, clock skew, CNAME/IPv4/IPv6 expansion,
  redirect escape, DNS rebinding, shared CDN/cloud infrastructure, wildcard
  ownership, and any target that cannot be proven wholly inside the receipt.
- Public targets are denied unless a separate program-scope receipt proves
  authorization. DNS names must resolve inside the authorized set at execution
  time; redirects and newly resolved addresses are revalidated.
- Destructive exploitation, persistence, credential theft, lateral movement,
  denial of service, payload deployment, evasion, and data exfiltration are denied.
- No retaliation or "hack back." AQ-OS will not deploy a Trojan horse into an
  attacker-controlled system, identify people by intrusion, or probe infrastructure
  outside the owner's authority.
- Defensive deception is allowed only inside owned infrastructure: inert honey
  credentials, honeyfiles, canary services, decoy endpoints, and instrumented
  sandboxes that report solely to an owner-controlled collector. They grant no
  privilege and initiate no counter-connection.
- External disclosure and bounty submission require owner approval, the receiving
  program's rules, evidence redaction, and coordinated-disclosure handling.

## 3. Initial external-source disposition

| Source | Intended value | Initial state | Reason / required mitigation |
|---|---|---|---|
| `FrkAk/piyaz` | A2A task-graph/claim/review, human-readable project tracking, and vector/RAG/DAG maintenance patterns | `PROPOSED / PATTERN-ONLY` | Cross-track reference for Agent Connection Reliability, Unified Program tracking, and memory/knowledge maintenance. It overlaps AQ-OS AAF, progress tracking, and data authorities; AGPL and hosted/plugin surfaces require source, permission, data-flow, license, and architecture-parity review before any runtime use. |
| `1N3/Sn1per` | Attack-surface and validation workflow reference | `QUARANTINED / NO-RUNTIME` | Root install, privileged containers, active exploitation, 90+ integrations, 600+ exploits, and a custom EULA with material restrictions. Do not vendor or install it. Any pattern use requires a pinned EULA digest and owner/legal disposition; this PRD makes no legal conclusion. |
| `dinosn/raptor-loop-hunt` | Multi-altitude vulnerability-hunt workflow and review prompts | `PROPOSED / SOURCE-AUDIT` | Autonomous looping and agent/tool execution can amplify prompt injection, scope escape, and resource exhaustion. Admit only sanitized defensive workflow patterns after pinned source, explicit license disposition, hooks, commands, and tool permissions pass intake. |
| CISA BOD 26-04 | Risk-based remediation and evidence-preservation policy | `REQUIREMENTS-SOURCE` | Voluntarily adopt exposure, KEV, exploitation automatability, and technical impact as prioritization factors; preserve volatile evidence before remediation when compromise is plausible. |

Existing admitted scanners remain the preferred implementation substrate:
Semgrep MCP, OSV-Scanner, Trivy, and Syft/Grype. New tools must demonstrate a
non-duplicative capability or materially better evidence before promotion.

## 4. Canonical security pipeline

```text
asset/SBOM inventory
  -> signed scope + authority check
  -> passive/static scan
  -> normalize findings
  -> risk rank (exposure + KEV + automatability + impact + confidence)
  -> reproduce in disposable owned lab
  -> preserve evidence
  -> remediate in source/config/package
  -> independent verification + negative controls
  -> regression tripwire
  -> dashboard/aq-qa evidence
  -> coordinated disclosure / optional bounty claim
```

No model output directly mutates severity, scope, policy, prompts, or promotion
state. Findings and proposed corrections pass typed schemas, deterministic
checks, independent review, and an owner-controlled release gate.

## 5. Contracts and SSOTs

- `security-scope-receipt.v1`: exact target identities, ownership basis, allowed
  techniques, rate/resource budget, start/expiry, approver, and exclusions.
- `security-finding.v1`: scanner, source digest, asset/SBOM identity, CVE/CWE,
  evidence digest, confidence, exposure, KEV, automatability, impact, and status.
- `security-remediation.v1`: fix commit, affected packages, rollback, tests,
  residual risk, reviewer, and deployment state.
- `security-disclosure.v1`: maintainer/program, policy URL/digest, permitted
  evidence, embargo, communication state, reward eligibility, and payment state.
- `security-tripwire.v1`: owned sensor, event class, privacy policy, retention,
  response playbook, and current health.
- Candidate and tool admission remains authoritative in
  `config/agent-capability-intake-candidates.json`.
- Port and service settings remain in `nix/modules/core/options.nix`; environment
  names remain in `config/env-contract.yaml`.

All schemas are closed, versioned, size-bounded, and privacy-redacted. Raw exploit
payloads, secrets, personal data, and attacker-controlled prose are not stored in
agent memory or committed reports.

Raw evidence, when necessary, goes only to an encrypted quarantine store with a
separate access authority, content digest, trusted collection time, chain-of-custody
events, retention/expiry, deletion approval, and legal-hold override. Derived
reports are redacted and content-bound to the raw evidence digest. Models receive
only the minimum sanitized projection; raw evidence never enters prompts, Git,
hot/warm memory, dashboards, or bounty submissions by default.

## 6. Risk prioritization

The default queue uses a deterministic lexicographic policy:

1. confirmed or suspected active exploitation / CISA KEV;
2. public or externally reachable exposure;
3. exploitation automatability;
4. technical and business impact;
5. evidence confidence and asset criticality;
6. compensating controls and safe remediation availability;
7. stable asset identity followed by finding digest as the tie-break.

CVSS may be retained as evidence but is not the sole ordering authority. Unknown
exposure, KEV, automatability, or impact maps to the more urgent review class but
never authorizes active testing. When compromise is plausible, evidence-preservation
urgency overrides patch order until the bounded volatile-evidence capture completes
or an owner records why capture is unsafe.

## 7. Defensive tripwires and response

Owned-system sensors may include:

- AppArmor/seccomp denial and execution-policy telemetry;
- systemd/audit/journal process, privilege, and persistence events;
- dependency/SBOM drift and newly reachable service detection;
- file-integrity checks on security policy, agent prompts, hooks, and tool manifests;
- inert honey credentials and honeyfiles with zero real authority;
- decoy localhost/private services that record bounded metadata;
- egress, DNS, authentication, and unexpected tool-call anomaly detection.

The automated response ceiling is: alert, preserve volatile evidence, isolate the
owned execution cell, revoke leases/secrets, block the local route, and prepare a
reviewed incident report. It may not deploy code to or interrogate the apparent
source.

Synthetic credentials must be cryptographically outside every production trust
root and rejected by real authentication even if copied verbatim. Collectors are
owner-controlled ingress-only endpoints with fixed schemas, byte/rate limits,
short retention, no dynamic content execution, and no callback/counter-connection.
Canaries record only bounded event metadata and cannot become command channels.

## 8. Responsible disclosure and bounty handling

- Verify the maintainer's `SECURITY.md` or bounty program before testing or contact.
- Freeze the policy URL and scope at test time; stop if scope is ambiguous.
- Duplicate search uses only the program's approved private mechanism; finding
  details are never leaked into public search/issues before disclosure.
- A policy or scope change after testing freezes submission until the owner
  revalidates it; embargo clocks come only from the frozen program policy or an
  authenticated maintainer message.
- Reproduce minimally, redact secrets and unrelated personal data, and provide a
  remediation-quality report with affected versions, impact, evidence, fix, and
  verification.
- Do not publicly disclose before the program/maintainer timeline permits.
- Track reward eligibility and submission status, but never optimize severity,
  duplicate reports, or withhold a safety-critical fix to increase payment.
- Payments, tax/identity forms, legal terms, and external account actions remain
  owner-only. AQ-OS cannot promise compensation.
- Every submission requires an immutable owner approval receipt. Accidental or
  malformed submissions trigger a bounded retraction/contact playbook and preserve
  the original evidence rather than silently rewriting history.

## 9. Service Coverage and success metrics

Every enabled scanner, scope gate, remediation queue, and tripwire ships with:

- an integration-path `aq-qa` check;
- a visible Command Center status/card;
- structured low-cardinality metrics; and
- a rollback/disable path.

Primary measures:

- asset/SBOM coverage and freshness;
- scan success/failure and finding age;
- KEV/public-exposure time-to-triage;
- time-to-evidence-preservation, fix, independent verification, and deployment;
- false-positive/duplicate rate;
- regression-tripwire coverage;
- scope-denial and attempted-scope-escape counts;
- disclosure acceptance and reward state (without personal/payment data).

## 10. Delivery slices

| Slice | Deliverable | Live authority |
|---|---|---|
| S0 | Candidate registry entries, missing intake schema restoration, defensive-boundary contracts, risk policy, golden vectors | None |
| S1 | Passive repo/package pipeline using existing Semgrep/OSV/Trivy/Syft-Grype, normalized findings, Phase-0 and dashboard | Read-only repo/package data |
| S2 | Disposable owned-target lab, signed scope receipts, egress/target allowlist, resource/rate budgets | Lab-only, owner activated |
| S3 | Tripwire/canary sensors, evidence preservation, isolation/revocation playbooks | Owned-system defensive response only |
| S4 | Maintainer disclosure and bounty workflow, policy freeze, redaction, owner approval | No autonomous external submission |
| S5 | BOD 26-04-aligned prioritization, KEV/exposure feeds, remediation SLOs, audits | Advisory until separately activated |

Each slice is independently planned, hash-bound, reviewed, monitored, and accepted.
No source download, installation, active scan, external message, or account action is
authorized by this PRD.

S0 metadata audits cannot claim source, license, dependency, or runtime acceptance
without a pinned source acquisition in a later separately authorized intake slice.
They remain `proposed`/`quarantined` with typed incomplete reasons.
