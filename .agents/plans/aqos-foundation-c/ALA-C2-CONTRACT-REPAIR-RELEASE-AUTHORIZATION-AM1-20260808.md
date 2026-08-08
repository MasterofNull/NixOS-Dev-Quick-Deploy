---
title: "Foundation C — ALA→C2 contract repair release AM1"
slice: "ALA-C2-R1-RELEASE-AM1"
date: "2026-08-08"
status: "PREPARED_ONLY — NOT ACTIVE"
kind: "single-use hash-bound release recovery authorization template"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# Prepared release AM1

Parent release authorization `8d238f5734d9bd2ba8e29bf946425d097f476510104aca955c6f42cb4fa54a4f`
was activated, staged its exact seventeen paths, and stopped without commit when protected Tier-0's global
frontmatter check rejected three unrelated untracked TEG draft documents. Its focused-CI evidence is
`/var/lib/ai-stack/hybrid/telemetry/latest-focused-ci.json` at SHA-256
`d81d94444f0b20f892306423b367045310659686396ed65c34d484b2edba40b6`. Parent authority is consumed and
non-replayable.

This AM1 is inert until the owner activates its exact SHA-256, assigns `codex-orchestrator`, and binds the
same exact HEAD. It permits one narrowly reviewed foreign-doc hygiene correction solely to make the normal
global hook runnable, then releases the accepted ALA→C2 package. It does not accept the TEG design, resolve
its five outstanding `REQUEST_REVISION` blockers, authorize TEG implementation, or add any TEG subject to
the release commit.

## Existing protected index and release ceiling

The protected index must contain exactly the seventeen paths and staged blobs frozen by parent
`8d238f57...`; no unstaged drift may exist on them. AM1 itself is the only additional staged path, yielding
an exact eighteen-path commit ceiling. All sixteen parent subject hashes and parent authorization hash
remain exactly as recorded there; this AM1's activated self-hash binds path eighteen.

## Permitted non-staged foreign correction

Only the YAML frontmatter of these three untracked foreign documents may be replaced with the independently
reviewed temporary bytes. Bodies after the closing YAML delimiter must remain byte-identical. These paths
must remain unstaged and absent from the release commit.

| Foreign path | Current SHA-256 | Reviewed target SHA-256 |
|---|---|---|
| `.agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md` | `ca855c967d1874a6f0ff3c16d48525ea8353981b557e0da81617f4ef16b9316c` | `97982f9fee0e4b2718c71284929347e83aa930c898c14131a0cd392708a2f896` |
| `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` | `54b8e0705530548f5365963ea06801a50e097d359a290228094545ec410fdd87` | `e90d880c755be8b4eab4bf736ec6d158c1bb465f665dd5bcc7692540d443091f` |
| `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-REVIEW-20260808.md` | `c75feea4e3bc0c5c3c9443fed517cbd1fa902cb2a217b624cbff4e33e4db9556` | `c40cb135124fc88ae580421554e33cb1917eea526bc4c2372e1474024822cc09` |

Temporary candidate root:
`/tmp/ala-c2-release-frontmatter-am1-20260808`; manifest file SHA-256
`2a54ae14f320f3c919139b3958f02c8af836080eefed87fb8ef4ef6704f91777`; independent review SHA-256
`5c27b01aac64752d6ec56b5b5a26cff495f6f25eae48a5fea5e7be2bb295b001` with `VERDICT: PASS`.

Apply exactly the reviewed bytes with no reinterpretation. Verify target hashes, body equality, and
`python3 scripts/governance/check-doc-frontmatter.py --all` PASS. Then regenerate the canonical foreign
porcelain/path/hash snapshot with `/tmp/ala-c2-r1-release-20260808/foreign_snapshot.py` at exact SHA-256
`f5388adb759ffc8bf207246b73d4068c889200e20e47beade7b80ca3da534c5d`. The equality payload intentionally
excludes repository HEAD because a successful release changes HEAD; record precommit and postcommit HEAD
separately in release evidence, outside the byte-equality subject. This AM1 procedure excludes the
complete exact eighteen-path release ceiling—including this still-untracked AM1 path—before staging;
therefore AM1 cannot enter the foreign baseline as `??` and disappear after commit. Generate the new
snapshot after the three TEG corrections and before staging AM1, freeze its SHA-256, and use that new
snapshot as the sole pre/post foreign preservation subject. The prior snapshot
`fc639f45077c9324b9e1589f6108130b0fd074891958fc250ef21ef13bef880a` is historical pre-failure evidence,
not the post-correction comparison baseline.

## Release mechanics and stops

Stage only this AM1 path in addition to the already exact seventeen parent paths. Verify eighteen total,
all eighteen authorized, zero TEG paths staged, and zero unstaged drift on the eighteen. Rerun focused
offline validation and protected Tier-0; run the ordinary commit with normal hooks and no `--no-verify`.
Create one atomic WORKFLOW-CANON Step-8 commit, then verify the commit diff contains exactly eighteen paths.
Regenerate the foreign snapshot and require byte-for-byte equality with the post-correction precommit
snapshot. Preserve all unrelated bytes.

Stop on any HEAD, index, parent subject, AM1, temp manifest, TEG current/target/body, foreign snapshot,
validation, hook, or overlap drift; any nineteenth staged/committed path; or any TEG path staged. No
deployment, rebuild, runtime/service/socket/provider/network action, live traffic, flag flip, C2/C6/TEG
activation, push, destructive Git, reset/checkout, amend, or history rewrite is permitted.

`RECORD: PREPARED_ONLY. No TEG edit, additional staging, or commit authority until exact-hash owner activation.`
