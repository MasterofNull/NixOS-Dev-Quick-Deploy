# AQ-OS Progress Tracker AM3 Byte Recovery R1 — Prepared Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-aqos-progress-tracker-am3-byte-recovery-r1-20260801`  
Bound HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Exact subject and predecessor disposition

- Recovery design: `DESIGN-PACKET-AM3-BYTE-RECOVERY-R1-20260801.md`
- Recovery design SHA-256:
  `b58e641327d25dbdafbf97d6f79791dc2046c5b6ed1a132e9fa9c91c82d6c3be`
- Activated AM3 authorization SHA-256:
  `9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
  — consumed and non-replayable.
- Prior AM4 and AM4-R1 packets are stale, never activated, and non-activatable;
  they assumed the destructively lost AM3 candidate still existed.

This record grants nothing until a distinct independent reviewer issues PASS
against these exact bytes and the owner activates this exact authorization SHA.

## Frozen sources and five-file ceiling

Before the first write, rehash the five sources and five predecessors in the
recovery design. In particular, `.agent/memory/issues-backlog.md` must equal
`814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8`.
Only these five files may be edited:

1. `config/refactor-milestones.json` — predecessor `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe`;
2. `assets/aqos-progress-tracker.html` — predecessor `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa`;
3. `scripts/testing/test-dashboard-program-progress.py` — predecessor `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7`;
4. `scripts/testing/harness_qa/phases/phase0.py` — predecessor `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`;
5. `scripts/ai/lib/refactor_status.py` — predecessor `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b`.

Stage A must reproduce, in the same order, exact hashes
`03bda508d7295ccfad00fbda183ba9ed886d753c42bdee37217cc09636dd84a4`,
`b10827de0b95d6ae1ce307ee25b2e010e0d160de1e260d6540d8723f2417f148`,
`bd3ebbb8a76edfa5500271711825eddf459bdb11c8353c653b4d873930bcb1c3`,
`58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3`,
and `b0fe4f8eac5f602d659b4a0c388e9685887dceb706022bf0def47426904f42b4`.
Any mismatch stops recovery.

Stage B may then replace exactly one occurrence per manifest and HTML of
`4c03925f9de68d2617515f61b96184917f32a62fa23fbf1702346733c06bee8e`
with `814123b31f982c41a864500959e9489828e96f3d9105906de952d8cac05b67a8`.
The other three Stage-A files become no-edit anchors. Capture final hashes; do
not infer or predeclare them.

## Lease, roles, validation, and exclusions

Proposed implementer:
`codex-subagent-tracker-am3-recovery-r1-implementer`. Required independent
reviewer: `codex-subagent-tracker-am3-recovery-r1-independent-reviewer`, distinct
from the design author and implementer. The implementer cannot stage or commit.

Activation must name an observable exclusive source/worktree/commit-owner lease
lasting no more than 45 minutes after first write. It must cover all five source
inputs, all five candidate paths, index/HEAD/commit mutation, and the focused/
Tier-0 writer slot; prohibit every concurrent agent, test, formatter, issue-log
writer, reset, checkout, stage, commit, and batch release; and be checked before
Stage A, between stages, before validation, and after final hash capture. The
index must be empty and no overlap may exist at preflight and post-validation.

Run exactly the offline validation commands in recovery design section 5,
including static tracker tests, Python/JSON checks, diff-check, and the permitted
Tier-0 invocation. Record source, predecessor, Stage-A, final, no-edit, lease,
index, command, and result evidence. Any drift, overlap, extra path, failed test,
or inability to prove the process is a stop and consumes an activated grant.

No stage, commit, deploy, runtime, provider/network, live traffic, service
restart, live HTTP, `aq-qa`, Nix, reset, checkout, or edit outside the exact
five-file ceiling is authorized.

`RECORD: PREPARED_ONLY byte recovery; exact review, lease, and owner activation required.`
