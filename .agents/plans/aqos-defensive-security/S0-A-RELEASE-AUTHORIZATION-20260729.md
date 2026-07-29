# Track S S0-A — Commit-Train Release Authorization

Status: **PREPARED_ONLY — OWNER ACTIVATION REQUIRED**
Prepared: 2026-07-29
Exact HEAD: `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`
Release operator: `codex-orchestrator`
Independent acceptance: Codex AM1 `PASS`; Claude Opus `CONFIRM-PASS`

## Purpose

End the repository-wide commit freeze for the already accepted S0-A metadata slice
without granting runtime, deployment, network, scanner, or external-target authority.
The expired implementation grants remain consumed/non-replayable. This is a new,
single-use release-only grant for exact-byte validation, staging, and one atomic commit.

## Exact release inventory

| SHA-256 | Path |
|---|---|
| `68e3f33cf187b7b7cf797be788c24cd837010c50730842f630770598fa4fa491` | `.agent/PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md` |
| `bb75f4d2a36f1bb6d397ee734668908091d5e4dbba07622d0415188623f01325` | `.agents/plans/aqos-defensive-security/PROGRAM-PLAN.md` |
| `73c3aebe1320cdc1a9ec1620cbc92844aff8cf6f577951ff93356bcc65b60737` | `.agents/plans/aqos-defensive-security/S0-A-ACTIVATION-RECEIPTS.md` |
| `86e3dcd11846ef95b3f105e84d109ba405c957b2a0060bd4bf029db5452c28bc` | `.agents/plans/aqos-defensive-security/S0-A-CLAUDE-CONFIRMATORY-REVIEW.md` |
| `7f91aaf6bfc6208e2fe1cb25f3715a38cab1bea3c6a7cb7840eb8cd4318c0224` | `.agents/plans/aqos-defensive-security/S0-A-AM1-ACTIVATION.md` |
| `4d7586338fbef5aff080b56dff7e6a8a5ef4ccd64fbcd90fbff2a9f95d0b9dbc` | `.agents/plans/aqos-defensive-security/S0-A-AM1-CANDIDATE-REVISION.md` |
| `2485397005ee2483e33e87c9cb43c816010f2073545cea50dbe2e92e06df1cbb` | `.agents/plans/aqos-defensive-security/S0-A-CANDIDATE-ACCEPTANCE.md` |
| `dd5fb5ce69ffc75ce9bd59f3935d366439e6326334a1b06c6ab5ee2b1ba1d813` | `.agents/plans/aqos-defensive-security/S0-A-DESIGN-PACKET.md` |
| `b66f176bdea6b5bae55f14d69e6ea1bae19657d6bae85002cb44d2c8baaa683c` | `.agents/plans/aqos-defensive-security/S0-A-IMPLEMENTATION-AUTHORIZATION-AM1.md` |
| `04cb48b411aacdf2572805d46a2bcd3b47729c108fa3677749c2eaceccd781ed` | `.agents/plans/aqos-defensive-security/S0-A-IMPLEMENTATION-AUTHORIZATION.md` |
| `80e7dc5ab77d16b23bca0374976f783bfaec4e3c3c0ec0981b886a9d6b1995da` | `.agents/plans/aqos-defensive-security/antigravity-track-s-review.md` |
| `d080957ba3da3282f424d6351496146cccbf664ee1d1fe3c10139313adf87c78` | `config/schemas/agent-capability-intake-candidates.schema.json` |
| `ab5d56ac93bceb1991470c96c429a6ec86554ed5865bfaab5bcf6110ae0ae1fb` | `config/agent-capability-intake-candidates.json` |
| `cdf59fc53a5c569bd9fa5945eec34fec07aefa71fdda0c1783b9a1bc78242f83` | `scripts/ai/aq-capability-intake` |
| `cd4aaebf4d21ff570f3ab5433fef0d56575e9ad975af9b810214502884f7259c` | `scripts/testing/test-capability-intake.py` |

This authorization document is included as release evidence in the same commit after
its own activated SHA-256 is verified.

## Authorized release operations

After exact owner activation naming this document's SHA-256 and a UTC window no longer
than 24 hours:

1. verify HEAD, every table hash, and absence of an overlapping writer;
2. normalize the mixed index without changing working-tree bytes;
3. stage exactly the inventory plus this authorization;
4. run the focused offline capability-intake suite and Tier-0 pre-commit gate against
   the exact staged subject;
5. inspect the staged diff and commit once with the full evidence contract;
6. mark this grant consumed in the commit body/handoff.

## Stop conditions

Stop on any hash/HEAD drift, seventeenth path, failed validation, overlapping active
writer, altered registry semantics, network/install/scan/runtime activity, deployment,
push, or attempt to include unrelated staged/unstaged/runtime files.

No push, deployment, external disclosure, scanner activation, capability admission, or
later Track S slice is authorized.
