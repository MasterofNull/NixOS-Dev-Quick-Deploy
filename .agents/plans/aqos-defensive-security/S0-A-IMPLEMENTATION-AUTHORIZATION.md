# Track S S0-A — Implementation Authorization

**Status:** PREPARED_ONLY / NOT ACTIVATED  
**Authorization class:** single-use, exact-subject, contract/config-only  
**Implementer:** UNASSIGNED  
**Activation window:** NONE  
**Live authority:** none

## 1. Frozen authorization subject

| Subject | SHA-256 / state |
|---|---|
| Exact repository HEAD | `107f7e8ab2452b4d89ff737b28966e35bf4f9e24` |
| Track S PRD | `68e3f33cf187b7b7cf797be788c24cd837010c50730842f630770598fa4fa491` |
| Track S program plan | `bb75f4d2a36f1bb6d397ee734668908091d5e4dbba07622d0415188623f01325` |
| S0-A design packet | `dd5fb5ce69ffc75ce9bd59f3935d366439e6326334a1b06c6ab5ee2b1ba1d813` |
| Registry baseline | `70d103d8be225b3cfc262a8c423b2dece3cda83fa4ca5efa2e98be91f67cc670` |
| Test baseline | `85dde9a6cfe2613e4425e8730e9cc6cfa6a631a1515eb82852b0fe2d63d57bfb` |
| Schema baseline | absent |

This authorization inherits the design packet's objective, candidate dispositions,
schema contract, acceptance criteria, focused validation, rollback, Service
Coverage truth, and explicit exclusions without broadening them.

## 2. Exact future implementation ceiling

Only an explicitly activated implementer may:

1. **CREATE**
   `config/schemas/agent-capability-intake-candidates.schema.json`
2. **MODIFY**
   `config/agent-capability-intake-candidates.json`
3. **MODIFY**
   `scripts/testing/test-capability-intake.py`

No fourth repository path is authorized. In particular, the capability-intake CLI,
the existing `t3mp3st` record/scope authority, dashboards, QA phases, policies,
collaboration state, documentation, Nix, runtime, reports, and caches are outside
the candidate inventory.

## 3. Required preflight

Before the first candidate write, the activated implementer must prove:

- `HEAD` exactly matches the frozen repository HEAD;
- both existing implementation files match their frozen SHA-256 values;
- the schema path remains absent;
- the PRD, program plan, and design packet match their frozen SHA-256 values;
- no staged, unstaged, untracked, delegated, or leased writer overlaps any of the
  three implementation paths;
- the assigned identity and activation window match the owner's exact activation;
- no previous write has consumed this authorization.

Any mismatch is a fail-closed stop. The implementer may report drift but may not
repair, rebase, merge, stash, reset, overwrite, or refreeze it under this grant.

## 4. Candidate constraints

The candidate must preserve all 11 existing registry records and their effective
admissions. The existing `t3mp3st` record remains byte-for-byte unchanged and stays
the sole scope validator/receipt authority for later Track S active-testing work.

The three additions are exactly:

- `piyaz-patterns` — `agent-system-pattern-reference`, `proposed`,
  `source-audit-required`; records cross-track A2A task/claim/review,
  human-readable tracker, and vector/RAG/DAG maintenance value without granting
  lifecycle, tracking, knowledge, or runtime authority.
- `sn1per-reference` — `security-workflow-reference`, `quarantined`,
  `no-runtime`; records no accepted source, EULA, legal, SBOM, or runtime evidence.
- `raptor-loop-hunt-reference` — `security-workflow-reference`, `proposed`,
  `source-audit-required`; records no accepted source, license, prompt, hook,
  command, loop, or runtime evidence.

Each has `review_status: incomplete`, disabled install metadata, no tools, no
network/filesystem/write/secret permission, and typed incomplete reasons. Missing
pin/license/SBOM/runtime evidence must prevent `low-risk` and
`accepted-with-mitigations`. No source or legal conclusion may be fabricated.

## 5. Activation and consumption

This document grants no authority until:

1. an independent reviewer returns `PASS` on the exact authorization subject; and
2. the owner activates the exact SHA-256 of this authorization, names one
   implementer, and supplies a UTC start/end window of at most 24 hours.

The activation must be materially equivalent to:

> Activate Track S S0-A authorization `<exact authorization SHA-256>`, assigning
> `<implementer identity>`, from `<UTC start>` through `<UTC end>`, against exact
> HEAD `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`. The exact three-file ceiling and
> all offline, metadata-only, single-use, overlap, drift, and no-runtime stop
> conditions remain unchanged.

The first candidate write atomically consumes the authorization. Failure,
interruption, timeout, identity change, window expiry, subject drift, overlap, or
partial output makes it non-replayable. Recovery requires an audit and fresh
hash-bound authorization; it cannot resume under this grant.

## 6. Authorized validation

Only these focused offline commands are authorized:

```bash
python3 -m json.tool config/schemas/agent-capability-intake-candidates.schema.json
python3 -m json.tool config/agent-capability-intake-candidates.json
python3 scripts/testing/test-capability-intake.py
scripts/ai/aq-capability-intake list --json
scripts/ai/aq-capability-intake audit --all --json
git diff --check -- \
  config/schemas/agent-capability-intake-candidates.schema.json \
  config/agent-capability-intake-candidates.json \
  scripts/testing/test-capability-intake.py
git status --short -- \
  config/schemas/agent-capability-intake-candidates.schema.json \
  config/agent-capability-intake-candidates.json \
  scripts/testing/test-capability-intake.py
```

The local list/audit projections are metadata checks only. Any attempt to access
the network, bootstrap a package, acquire source, execute a candidate, generate an
SBOM, or run a scanner is a stop condition. Broad Tier-0, live QA, deployment, and
provider checks remain unauthorized.

## 7. Candidate handoff and acceptance

After focused validation, the implementer must stop and report:

- exact hashes of all three candidate files;
- exact diff inventory;
- the 14-record schema result;
- the 11-record compatibility result;
- the three incomplete/non-accepted admission results;
- every validation command and result;
- any warning, failure, drift, or residual risk.

The implementer may not stage, commit, deploy, or accept its own work. An
independent flagship reviewer must inspect the exact candidate hashes, verify every
design acceptance criterion, and issue `PASS` before the orchestrator may prepare a
separate commit action.

## 8. Service Coverage and rollback

S0-A creates no live component and earns no Service Coverage claim. Existing
scanner admission remains distinct from the S1 integration-path QA, Command Center,
metrics, and rollback audit.

Rollback is not pre-authorized by this document. If needed, prepare an independent
exact revert that restores the frozen registry/test bytes and follows the
archive/reference SOP for the created schema. The revert must explicitly record
that it reopens the known missing-schema defect.

## 9. Stop conditions and exclusions

Stop on any unauthorized path, writer overlap, baseline drift, candidate source
access, network request, package/install action, source/license/SBOM/runtime
acceptance claim, permission expansion, existing-record change, `t3mp3st` change,
tool enablement, active/public target, exploit, external message, raw-evidence
handling, prompt import, runtime hook, process/service change, Nix operation,
dashboard/QA-phase edit, deployment, staging, or commit.

S0-B and S1-S5 remain unauthorized.
