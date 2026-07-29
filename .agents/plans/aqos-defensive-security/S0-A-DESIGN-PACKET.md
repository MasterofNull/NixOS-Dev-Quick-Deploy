# Track S S0-A — Capability Intake Truth Design Packet

**Status:** PREPARED_ONLY / REQUIRES INDEPENDENT REVIEW  
**Slice:** S0-A  
**Role:** bounded implementer followed by an independent flagship reviewer  
**Live authority:** none

## 1. Objective

Restore the missing closed schema for the existing capability-intake registry and
add three disabled, metadata-only reference candidates without installing,
executing, downloading, scanning, or promoting any external capability.

S0-A is registry truth and validation only. It does not implement the Track S
security pipeline, active testing, source audit, scope receipts, Service Coverage,
disclosure, or runtime routing.

## 2. Frozen subject

| Subject | SHA-256 / state |
|---|---|
| Exact repository HEAD | `107f7e8ab2452b4d89ff737b28966e35bf4f9e24` |
| `.agent/PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md` | `68e3f33cf187b7b7cf797be788c24cd837010c50730842f630770598fa4fa491` |
| `.agents/plans/aqos-defensive-security/PROGRAM-PLAN.md` | `bb75f4d2a36f1bb6d397ee734668908091d5e4dbba07622d0415188623f01325` |
| `config/agent-capability-intake-candidates.json` | `70d103d8be225b3cfc262a8c423b2dece3cda83fa4ca5efa2e98be91f67cc670` |
| `scripts/testing/test-capability-intake.py` | `85dde9a6cfe2613e4425e8730e9cc6cfa6a631a1515eb82852b0fe2d63d57bfb` |
| `config/schemas/agent-capability-intake-candidates.schema.json` | absent |

Any HEAD, parent-document, baseline-byte, schema-existence, inventory, or writer
drift stops the slice and requires a fresh design/refreeze.

## 3. Exact implementation ceiling

An activated implementer may touch exactly these three repository paths:

1. **CREATE**
   `config/schemas/agent-capability-intake-candidates.schema.json`
2. **MODIFY**
   `config/agent-capability-intake-candidates.json`
3. **MODIFY**
   `scripts/testing/test-capability-intake.py`

No generated report, cache, temporary fixture, collaboration record, dashboard,
Phase-0, CLI, policy, Nix, runtime, source snapshot, archive, or documentation path
belongs to the implementation candidate. Test-created cache data must be cleaned by
the existing test lifecycle and is not candidate inventory.

## 4. Schema contract

The new schema is the closed Draft 2020-12 contract referenced by the registry's
existing `$schema` path. It must:

- close the root, policy, candidate, install, permission, tool-schema, and nested
  object boundaries with `additionalProperties: false` wherever the registry owns
  the vocabulary;
- validate all 11 baseline records without changing their bytes or effective
  admission;
- require stable candidate identity and bound every string and array;
- enumerate the complete baseline-plus-S0-A values for category, maturity,
  priority, state, review status, install type, network/filesystem/write/secret
  permission classes, and declared risk flags;
- preserve the existing `t3mp3st` record, state, mitigations, permissions, tool
  allowlist, source pin, and canonical scope-authority role byte-for-byte;
- reject unknown keys, wrong types, duplicate candidate IDs, malformed URLs,
  unbounded tool names, and undeclared permission/risk values;
- distinguish a candidate's declared `review_status: incomplete` from the existing
  audit CLI's derived `admission` result.

S0-A does not change `scripts/ai/aq-capability-intake`. For the new records,
`review_status: incomplete` is the typed metadata result. The current audit CLI may
derive `needs-review`, `review-recommended`, or `blocked`, but must never derive
`low-risk` or `accepted-with-mitigations`.

## 5. Exact candidate dispositions

All three records have:

- `maturity: third-party-reference`;
- `review_status: incomplete`;
- `install.type: disabled-external-repo`;
- `install.command: disabled-until-intake`;
- empty install args and tool allowlist;
- `permissions.network: false`, `filesystem: none`, `writes: false`,
  `secrets: false`;
- no source hash or accepted source/license/SBOM/runtime evidence;
- typed incomplete/blocked reasons naming the absent evidence;
- no authority over A2A, project tracking, vector/RAG/DAG state, scanning,
  scope receipts, execution, or external communication.

| ID | Source | Category | State | Disposition |
|---|---|---|---|---|
| `piyaz-patterns` | `https://github.com/FrkAk/piyaz` | `agent-system-pattern-reference` | `proposed` | `source-audit-required`; cross-track reference for A2A task/claim/review, human-readable tracking, and vector/RAG/DAG maintenance patterns. It may inform Agent Connection Reliability, Unified Program tracking, and memory/knowledge maintenance only after clean-room source/license/data-flow review. It creates no lifecycle or data authority. |
| `sn1per-reference` | `https://github.com/1N3/Sn1per` | `security-workflow-reference` | `quarantined` | `no-runtime`; pinned source/EULA digest, legal disposition, SBOM, and runtime review are absent. No vendor, install, execution, or pattern use is admitted. |
| `raptor-loop-hunt-reference` | `https://github.com/dinosn/raptor-loop-hunt` | `security-workflow-reference` | `proposed` | `source-audit-required`; source/license, hook, command, loop-bound, prompt-injection, and runtime evidence are absent. No prompt or executable workflow is imported. |

Risk declarations must remain descriptive and non-accepting. At minimum they cover
AGPL/license uncertainty and authority duplication for Piyaz; custom-EULA,
privileged install, active exploitation, and external integration for Sn1per; and
autonomous-loop, prompt-injection, scope-escape, tool-execution, and resource
exhaustion for RAPTOR.

## 6. Acceptance criteria

The candidate passes S0-A acceptance only when all are true:

1. The exact three-file inventory is the complete candidate diff.
2. The registry contains 14 unique candidates and validates against its referenced
   schema.
3. The 11 baseline candidate objects are byte-semantic equivalent to the frozen
   baseline and retain their pre-slice audit admissions.
4. The `t3mp3st` record and canonical scope-authority behavior are unchanged.
5. Every owned schema object is closed; focused negative vectors reject unknown
   keys, wrong types/enums, malformed permissions, duplicate IDs, and unbounded
   values.
6. Each new candidate is metadata-only, disabled, `incomplete`, and incapable of
   reaching `low-risk` or `accepted-with-mitigations`.
7. No test performs network access, source acquisition, installation, package
   bootstrap, scanner execution, active probing, or runtime/deployment changes.
8. Focused offline validations pass exactly as named below.
9. An independent reviewer verifies the exact candidate bytes and returns `PASS`;
   implementer self-acceptance is prohibited.

## 7. Focused offline validation

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

The list/audit commands are local registry projections, not capability source
audits or security scans. Any command that attempts network or package bootstrap
must be stopped rather than retried.

## 8. Service Coverage truth

S0-A creates no service, endpoint, scanner execution path, route, daemon, metric, or
live configuration. It therefore adds no `aq-qa` integration check or dashboard
panel and makes no Service Coverage claim.

S1 remains blocked until it audits each already-enabled Semgrep, OSV-Scanner, Trivy,
and Syft/Grype path for a real integration-path `aq-qa` check, visible Command
Center state, bounded metrics, and rollback. Existing admission is not Service
Coverage evidence.

## 9. Rollback

Because S0-A has no runtime adoption, rollback is an independently reviewed exact
revert of the candidate commit:

- restore the registry and test to their frozen pre-slice bytes;
- remove the created schema through the repository's archive/reference SOP rather
  than an ad hoc destructive command;
- record that rollback deliberately reopens the pre-existing missing-schema defect;
- rerun the focused pre-slice test and verify that no runtime state changed.

Rollback cannot weaken schema validation while retaining the three new records.

## 10. Explicit exclusions

No clone, download, network access, package install, source audit, SBOM generation,
security scan, active target, exploit, external message, plugin/MCP enablement,
scope-authority change, raw-evidence handling, prompt import, runtime hook, process,
Nix evaluation/build, deployment, traffic, dashboard, Phase-0, broad Tier-0,
staging, or commit is authorized by this design packet.
