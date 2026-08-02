# AQ-OS Progress Tracker AM3 — Byte Recovery Revision 1

Status: `PREPARED_ONLY — INDEPENDENT REVIEW AND OWNER ACTIVATION REQUIRED`  
Base HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`  
Recovery kind: `monotonic reconstruction; not AM3 replay`

## 1. Incident and authority lineage

AM3 design SHA-256
`2b9c0424f3a9f5ab9774cf5c8868003e76ab0c155c2a7fe15bdb10b57a87ecd6`
and activated AM3 authorization SHA-256
`9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
produced an accepted-in-progress five-file candidate. AM3 was consumed on its
first successful write and remains non-replayable.

The shared worktree was subsequently reset while multiple lanes were active.
All five uncommitted AM3 candidate files were destructively returned to their
original predecessor bytes. This recovery does not pretend AM3 is unused and
does not infer acceptance from remembered prose. It authorizes a new bounded
two-stage reconstruction whose intermediate byte hashes are the exact observed
AM3 candidate hashes and whose final source projection is updated to the now
committed issues-backlog evidence.

The earlier AM4 re-pin packets assumed the AM3 candidate still existed and are
superseded for implementation mechanics. They must not be used to skip Stage A.
`DESIGN-PACKET-AM4-20260801.md`, `DESIGN-PACKET-AM4-REV1-20260801.md`,
and `IMPLEMENTATION-AUTHORIZATION-AM4-REV1-20260801.md` are stale audit
records and non-activatable. This revision is a fresh preparation against the
current stable HEAD; it does not inherit any prior activation.

## 2. Stable source and predecessor freeze

Preparation observed an empty staged index and these exact bytes:

### Frozen evidence sources

| Source | Required SHA-256 |
|---|---|
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `config/system-state-authorities.yaml` | `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a` |
| `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md` | `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a` |
| `.agent/memory/issues-backlog.md` | `814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8` |

### Current five-file predecessor ceiling

| Path | Required pre-recovery SHA-256 |
|---|---|
| `config/refactor-milestones.json` | `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe` |
| `assets/aqos-progress-tracker.html` | `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa` |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` |
| `scripts/ai/lib/refactor_status.py` | `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b` |

Any source, predecessor, HEAD, index, or ownership drift invalidates the packet.

## 3. Exact two-stage recovery

Only the five predecessor paths above may be edited. Use `apply_patch`; no bulk
formatter, generated repository file, move, replacement, or mode change exists.

### Stage A — exact AM3 byte reconstruction

Reapply the reviewed AM3 semantics from
`DESIGN-PACKET-AM3-20260801.md` and stop unless all five intermediate files have
these exact hashes:

| Path | Mandatory Stage-A SHA-256 |
|---|---|
| `config/refactor-milestones.json` | `03bda508d7295ccfad00fbda183ba9ed886d753c42bdee37217cc09636dd84a4` |
| `assets/aqos-progress-tracker.html` | `b10827de0b95d6ae1ce307ee25b2e010e0d160de1e260d6540d8723f2417f148` |
| `scripts/testing/test-dashboard-program-progress.py` | `bd3ebbb8a76edfa5500271711825eddf459bdb11c8353c653b4d873930bcb1c3` |
| `scripts/testing/harness_qa/phases/phase0.py` | `58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3` |
| `scripts/ai/lib/refactor_status.py` | `b0fe4f8eac5f602d659b4a0c388e9685887dceb706022bf0def47426904f42b4` |

Hash equality is the Stage-A oracle. Do not “improve” or reinterpret the bytes.
The Stage-A manifest/HTML intentionally contain the historical issues digest
`4c03925f9de68d2617515f61b96184917f32a62fa23fbf1702346733c06bee8e`,
so source reconciliation is expected to remain red until Stage B. Do not run or
report full acceptance between the stages.

### Stage B — current source re-pin

Immediately after all five Stage-A hashes match, modify only the manifest and
HTML. In each, replace the sole occurrence of the historical issues digest with
the current committed digest
`814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8`.
No other byte changes. The three code/test no-edit files must retain their exact
Stage-A hashes. The manifest and embedded HTML source arrays must normalize to
identical bytes.

The final manifest/HTML hashes cannot be inferred from predecessor hashes alone;
the implementer must capture them after the exact scalar substitutions, and an
independent reviewer must bind those final bytes. Acceptance is semantic plus
exact-hash evidence, never an unverified recollection.

## 4. Exclusive execution boundary

Owner activation is invalid without one observable exclusive lease held by
`codex-subagent-tracker-am3-recovery-r1-implementer`. The lease must cover:

- all five source inputs;
- all five candidate paths;
- the repository index/HEAD and commit-owner boundary; and
- the Tier-0/focused-test writer slot.

It must block every other worktree writer, issue-log writer, formatter, test
remediator, Tier-0 runner, stage/commit owner, reset/checkout, and batch release
for the bounded window. It must have a stable lease ID, canonical registry
evidence, and expiry no more than 45 minutes after first write. Recheck it before
Stage A, between stages, before validation, and after final hash capture. PULSE
may continue only if it does not mutate a protected source, candidate, HEAD, or
index. A mandatory new issue or external change aborts recovery and is recorded
after lease release.

## 5. Roles, validation, and report

Proposed implementer:
`codex-subagent-tracker-am3-recovery-r1-implementer`.  
Required independent reviewer:
`codex-subagent-tracker-am3-recovery-r1-independent-reviewer`, distinct from the
design author and implementer. The implementer cannot self-accept.

After Stage B, run only:

```text
python3 -m json.tool config/refactor-milestones.json
python3 scripts/testing/test-refactor-status.py
python3 scripts/testing/test-dashboard-program-progress.py --static-only
python3 -m py_compile scripts/ai/lib/refactor_status.py scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check -- config/refactor-milestones.json assets/aqos-progress-tracker.html scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py scripts/ai/lib/refactor_status.py
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
```

The final report must include: pre-recovery hashes; all five Stage-A hashes;
final five candidate hashes; all source hashes; lease checks; empty-index proof;
every command/result; exclusions; and any blocker. The static suite must prove
19-track parity, five active tracks, Track V blocked, zero pending owner
decisions, Critical+High counting, truthful C2/C5 deployment distinction, C3b
dormancy, disputed C0.3 settlement, LEC active, stale-finding removal, and exact
Phase-0 0.10.41–0.10.44 preservation.

A distinct reviewer must issue exact-byte `PASS` before any later release. A
failure or revision consumes the recovery authorization and requires a new one.

## 6. Exclusions and non-authority

No stage, commit, deploy, runtime, provider/network, live traffic, service
restart, live HTTP, `aq-qa`, Nix, reset, checkout, or edit outside the five-file
ceiling is authorized. This design itself grants no implementation or activation.

`RECORD: PREPARED_ONLY AM3 byte-recovery R1; consumed AM3 is not replayed; fresh owner activation required.`
