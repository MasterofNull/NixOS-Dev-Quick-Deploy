# L3-P0-AM1 Prepared Correction Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED; SINGLE USE AFTER FRESH OWNER ACT`  
Authorization ID: `auth-local-inference-l3-p0-am1-20260801`  
Bound HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Authority chain and identities

This authorization is a prepared candidate only. It binds AM1 correction design
SHA-256 `de3dd023e47e535cd53af8e25b1d69e30657b83b90caa2de477c09e7cc9b7da1`,
original L3-P0 design SHA-256
`9363c2aa9942d345cb58d3e9ee98162c15ca23226c248358229e110158405f23`, and
independent PASS SHA-256
`0282e12f7eff556c5d886269033b43070a3d2263d9e4e528a34d3d5300dd82dc`.
The prior activated authorization
`2d06c396cae2dfdbe2bbbb00d8879ae23df49b244e1cef623c1296b1aa85b47c` was
consumed by its first candidate write and is non-replayable. This grant does not
ratify that candidate or its unauthorized fixture location.

Proposed implementer: a future bounded implementer **other than**
`codex-subagent-local-inference-l3-p0-implementer`. Candidate acceptance must be
performed by a distinct independent flagship reviewer; neither implementer nor
this remediation author may self-accept. Only a separately authorized
orchestrator may stage or commit.

## Single-use ceiling and destructive precondition

If a fresh owner activates this exact authorization, its complete write/removal
ceiling is exactly: `scripts/ai/lib/local_inference_provenance.py`;
`config/schemas/local-inference-trusted-fact-envelope-v1.schema.json`;
`config/schemas/local-inference-producer-revision-set-v1.schema.json`;
`config/schemas/local-inference-shadow-request-projection-v1.schema.json`;
`config/schemas/local-inference-resolved-shadow-plan-v1.schema.json`;
`config/schemas/local-inference-shadow-observation-metadata-v1.schema.json`;
`config/schemas/local-inference-shadow-observation-v1.schema.json`;
`config/schemas/local-inference-trusted-fact-unavailable-v1.schema.json`;
`scripts/testing/test-local-inference-l3-p0.py`; NEW
`scripts/testing/fixtures/local-inference-l3-p0-golden.json`; and removal of
`config/testing/local-inference-l3-p0-golden.json`. The owner act must explicitly
say that the removal is authorized destructive cleanup/relocation of an untracked unauthorized file.
Absent that exact sentence, the implementer must stop before any write; no
implicit cleanup, `rm`, or relocation is granted.

The grant is consumed on the first successful ceiling write or completed exact
candidate report. Drift, failed validation, overlap, an eleventh path, a missing
destructive-cleanup statement, or REQUEST_REVISION consumes/voids the attempt and
requires a newly numbered authorization.

## Mandatory proof obligations

The future implementer must meet every AM1 correction requirement: required fact
types, digest-only values, producer revision-set enforcement, NFC deterministic
canonical JSON, recursive closed schemas and schema validation, complete
digest-bound observation fields, internal-only unavailable construction, and
exhaustive forbidden-capability/digest/metadata vectors. It must produce exact
post-write hashes, prove the old fixture is absent and replacement fixture is at
the authorized path, and run hermetic focused tests, Python syntax, schema parse,
`git diff --check`, and permitted static gates.

## Exclusions and stop conditions

The following no-edit anchors must rehash exactly before first write and before
candidate acceptance:

| No-edit path | SHA-256 |
|---|---|
| `scripts/ai/lib/local_inference_transport.py` | `e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405` |
| `scripts/testing/test-local-inference-l2b.py` | `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82` |
| `dashboard/backend/api/routes/aistack.py` | `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd` |
| `assets/dashboard.js` | `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be` |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` |

No staging, commit, runtime, live inference, provider, network, deployment,
restart, API, dashboard, AQ-QA/Phase-0, Nix, service, persistence, telemetry,
L2B, `delegate-to-local`, or aq-chat action is authorized. Stop on any need for
one. No owner activation is supplied by this document.

`RECORD: PREPARED_ONLY AM1 single-use correction authorization; no implementation or destructive cleanup authority until explicit owner activation.`
