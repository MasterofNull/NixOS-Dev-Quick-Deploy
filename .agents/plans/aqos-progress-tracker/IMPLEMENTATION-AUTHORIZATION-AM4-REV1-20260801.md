# AQ-OS Progress Tracker AM4 Revision 1 — Prepared Implementation Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-aqos-progress-tracker-am4-r1-20260801`  
Idempotency key: `aqos-progress-tracker:am4-r1:502cacd6:20260801`  
Base HEAD: `502cacd6ca3081ea7a1fce5bb15ad17affa6b687`

## Exact subject and predecessor disposition

- Design: `DESIGN-PACKET-AM4-REV1-20260801.md`
- Design SHA-256:
  `b020fd6f8630e9058d24b5e963c582f9aaf3c5afc38de0aa4ce1388f5a0b540a`
- AM3 authorization:
  `9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
  — consumed and non-replayable.
- `DESIGN-PACKET-AM4-20260801.md` — superseded after pre-authorization source
  drift and never activatable.

This record is only a prepared grant. Implementation requires a fresh
independent exact-subject PASS followed by an owner activation naming this
authorization SHA-256, the assigned implementer, the source-freeze/commit-owner
lease ID, and a bounded UTC window no longer than 30 minutes after first write.

## Exact source and candidate bindings

All source inputs must remain exact:

| Source | SHA-256 |
|---|---|
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `config/system-state-authorities.yaml` | `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a` |
| `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md` | `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a` |
| `.agent/memory/issues-backlog.md` | `8b42935c5a55bb303d2c5c112ecb50cf6aa4536f5c4b180fdd334605536d9aa8` |

The preserved AM3 candidate is bound as follows:

| Operation | Path | Pre-write SHA-256 |
|---|---|---|
| EDIT | `config/refactor-milestones.json` | `03bda508d7295ccfad00fbda183ba9ed886d753c42bdee37217cc09636dd84a4` |
| EDIT | `assets/aqos-progress-tracker.html` | `b10827de0b95d6ae1ce307ee25b2e010e0d160de1e260d6540d8723f2417f148` |
| NO EDIT | `scripts/testing/test-dashboard-program-progress.py` | `bd3ebbb8a76edfa5500271711825eddf459bdb11c8353c653b4d873930bcb1c3` |
| NO EDIT | `scripts/testing/harness_qa/phases/phase0.py` | `58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3` |
| NO EDIT | `scripts/ai/lib/refactor_status.py` | `b0fe4f8eac5f602d659b4a0c388e9685887dceb706022bf0def47426904f42b4` |

## Two-file correction ceiling

After exact activation, the assigned implementer may modify only:

1. `config/refactor-milestones.json`; and
2. `assets/aqos-progress-tracker.html`.

In each file, replace exactly one occurrence of
`4c03925f9de68d2617515f61b96184917f32a62fa23fbf1702346733c06bee8e`
with
`8b42935c5a55bb303d2c5c112ecb50cf6aa4536f5c4b180fdd334605536d9aa8`.
No other byte, path, mode, timestamp, status, issue text, count, schema, test,
projector, Phase-0, HTML, CSS, or JavaScript change is authorized.

## Lease, roles, and consumption

Proposed implementer:
`codex-subagent-tracker-am4-r1-repin-implementer`.  
Required independent reviewer:
`codex-subagent-tracker-am4-r1-independent-reviewer`, distinct from design
author and implementer. The implementer cannot self-accept, stage, or commit.

Activation requires one observable exclusive source-freeze/commit-owner lease
covering all five source paths, both EDIT paths, and repository commit/index
mutation. It must name the implementer as holder, forbid other writers and
commits, expire within the bounded activation window, and remain valid through
post-validation hash capture. Missing, expired, ambiguous, or overlapping lease
state is a typed stop.

This authorization is single-use if activated. It is consumed by the first
successful EDIT write or completed candidate report. Any interruption, drift,
overlap, failure, or `REQUEST_REVISION` requires a new numbered authorization.

## Required offline evidence

Before the first write: verify exact HEAD, design/authorization hashes, active
lease, all source and candidate hashes, empty staged index, no overlap, and one
old-digest occurrence per EDIT file. After the two scalar writes, run:

```text
python3 -m json.tool config/refactor-milestones.json
python3 scripts/testing/test-refactor-status.py
python3 scripts/testing/test-dashboard-program-progress.py --static-only
python3 -m py_compile scripts/ai/lib/refactor_status.py scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check -- config/refactor-milestones.json assets/aqos-progress-tracker.html scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py scripts/ai/lib/refactor_status.py
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
```

Recheck HEAD, lease, all source hashes, both post-write hashes, and all three
no-edit hashes after validation. Stop on any mismatch. The candidate report must
record exact commands/results, hashes, lease evidence, exclusions, and any
blocker for independent exact-byte review.

No stage, commit, deploy, runtime, provider/network, live traffic, service
restart, `aq-qa`, Nix, or live HTTP action is granted.

`RECORD: PREPARED_ONLY single-use AM4-R1 two-scalar re-pin authorization; exact review, lease, and owner activation required.`
