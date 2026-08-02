# AQ-OS Progress Tracker AM4 Revision 1 — Stable Source Re-pin

Status: `PREPARED_ONLY — INDEPENDENT REVIEW AND OWNER ACTIVATION REQUIRED`  
Base HEAD: `502cacd6ca3081ea7a1fce5bb15ad17affa6b687`  
Supersedes: `DESIGN-PACKET-AM4-20260801.md` (stale before authorization; never activatable)

## 1. Recovery lineage and root cause

AM3 authorization
`9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
was activated and consumed by its first successful candidate write. It is
non-replayable. Its five-file candidate remains preserved exactly.

AM3 stopped when the orchestrator performed its mandatory issue-log write while
the tracker implementer was active. That changed the issues-backlog evidence
hash after AM3 preflight. The first AM4 design then stopped correctly when the
same operational source advanced a second time before authorization. External
commit `502cacd6ca3081ea7a1fce5bb15ad17affa6b687` finalized the concurrent
governance work and left `.agent/memory/issues-backlog.md` committed and clean at
`8b42935c5a55bb303d2c5c112ecb50cf6aa4536f5c4b180fdd334605536d9aa8`.

This is a coordination/provenance race, not a tracker semantic defect. AM4-R1
authorizes only a stable two-scalar re-pin after an exclusive source-freeze and
commit-owner lease exists. It does not replay or widen AM3.

## 2. Exact frozen sources

| Source path | Required SHA-256 |
|---|---|
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `config/system-state-authorities.yaml` | `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a` |
| `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md` | `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a` |
| `.agent/memory/issues-backlog.md` | `8b42935c5a55bb303d2c5c112ecb50cf6aa4536f5c4b180fdd334605536d9aa8` |

All five hashes and exact HEAD matched during preparation. Any later source or
HEAD drift invalidates these bytes; the implementer may not edit a source input
to make the candidate pass.

## 3. Preserved AM3 candidate and minimal correction

| AM4-R1 operation | Candidate path | Required pre-write SHA-256 | Exact permitted change |
|---|---|---|---|
| EDIT | `config/refactor-milestones.json` | `03bda508d7295ccfad00fbda183ba9ed886d753c42bdee37217cc09636dd84a4` | Replace its sole issues-backlog digest `4c03925f9de68d2617515f61b96184917f32a62fa23fbf1702346733c06bee8e` with `8b42935c5a55bb303d2c5c112ecb50cf6aa4536f5c4b180fdd334605536d9aa8`. |
| EDIT | `assets/aqos-progress-tracker.html` | `b10827de0b95d6ae1ce307ee25b2e010e0d160de1e260d6540d8723f2417f148` | Apply the identical one-digest substitution in embedded provenance. |
| NO EDIT | `scripts/testing/test-dashboard-program-progress.py` | `bd3ebbb8a76edfa5500271711825eddf459bdb11c8353c653b4d873930bcb1c3` | Preserved focused and negative-vector oracle. |
| NO EDIT | `scripts/testing/harness_qa/phases/phase0.py` | `58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3` | Preserved check 0.10.40 and byte-identical 0.10.41–0.10.44 semantics. |
| NO EDIT | `scripts/ai/lib/refactor_status.py` | `b0fe4f8eac5f602d659b4a0c388e9685887dceb706022bf0def47426904f42b4` | Preserved projector and Critical/High normalization. |

Each EDIT file must contain the old digest exactly once before mutation and the
new digest exactly once afterward. No timestamp, status, issue content, source
path/class, count, HTML, CSS, JavaScript, Python, Phase-0, mode, or other byte
may change. The three no-edit candidate files must retain their hashes. No third
editable path or generated repository file exists.

The existing projector suite passed 22/22 against the preserved AM3 candidate,
so no test-path correction is necessary. A later test failure is a stop, not
authority to add a path.

## 4. Mandatory source-freeze and commit-owner lease

Owner activation is invalid unless it names one active, exclusive, bounded UTC
lease whose holder is the AM4-R1 implementer and whose protected set contains:

- all five frozen source inputs above;
- both AM4-R1 EDIT paths;
- the repository commit/index mutation boundary.

The lease must exclude every other issue-log writer, orchestrator commit, batch
release, formatter, projector refresh, and tracker writer for the activation
window. It must be observable through the canonical collaboration/commit-owner
registry, have a stable lease ID and expiry no more than 30 minutes after first
write, and be rechecked immediately before both edits and after validation.
PULSE/report-only events may continue only if they do not mutate any protected
path or HEAD. A needed mandatory issue log during the lease aborts AM4-R1; the
issue is preserved after lease release and a new re-pin is prepared.

## 5. Roles and validation

Proposed implementer:
`codex-subagent-tracker-am4-r1-repin-implementer`.  
Required independent reviewer:
`codex-subagent-tracker-am4-r1-independent-reviewer`, distinct from the design
author and implementer. The implementer cannot self-accept, stage, or commit.

Preflight must verify exact HEAD, design/authorization hashes, lease identity
and coverage, all five source hashes, all five candidate hashes, empty staged
index, no overlap, and the exact digest occurrence counts. After the two scalar
changes, run only:

```text
python3 -m json.tool config/refactor-milestones.json
python3 scripts/testing/test-refactor-status.py
python3 scripts/testing/test-dashboard-program-progress.py --static-only
python3 -m py_compile scripts/ai/lib/refactor_status.py scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check -- config/refactor-milestones.json assets/aqos-progress-tracker.html scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py scripts/ai/lib/refactor_status.py
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
```

The static tracker suite supplies the live-shape oracle without HTTP: candidate
origin parsing, dashboard linkage/header shape, `PROJECTED_CURRENT_STATE`, source
hashes, normalized manifest/HTML equality, counts, negative vectors, and Phase-0
0.10.41–0.10.44 preservation. Live HTTP, `aq-qa`, service restart, Nix,
deployment, provider, and network actions are prohibited.

The exact candidate report must record post-write hashes, source/no-edit hashes,
lease checks, every command/result, and exclusions. A distinct flagship reviewer
must issue exact-byte `PASS` before a later separately authorized release.

## 6. Stop and non-authority

Stop on any HEAD, source, candidate, lease, index, overlap, occurrence-count,
normalization, test, diff, or Tier-0 drift. A stopped or revision-requested
AM4-R1 is consumed and requires a new numbered authorization.

This design grants no implementation, activation, staging, commit, deployment,
runtime, provider, network, live traffic, service restart, `aq-qa`, or live
dashboard probe authority.

`RECORD: PREPARED_ONLY AM4-R1 two-scalar source re-pin; prior AM4 design superseded; AM3 consumed and non-replayable.`
